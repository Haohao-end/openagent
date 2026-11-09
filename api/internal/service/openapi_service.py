import json
from dataclasses import dataclass
from threading import Thread
from typing import Generator

from flask import current_app, has_app_context
from injector import inject
from langchain_core.messages import HumanMessage

from internal.core.agent.agents import FunctionCallAgent, ReACTAgent
from internal.core.agent.entities.agent_entity import AgentConfig
from internal.core.agent.entities.queue_entity import QueueEvent
from internal.core.memory import TokenBufferMemory
from internal.entity.app_entity import AppStatus
from internal.entity.conversation_entity import InvokeFrom, MessageStatus
from internal.entity.dataset_entity import RetrievalSource
from internal.exception import NotFoundException, ForbiddenException
from internal.lib.helper import build_input_parts, build_output_payload
from internal.model import Account, EndUser, Conversation, Message
from internal.schema.openapi_schema import OpenAPIChatReq
from pkg.response import Response
from pkg.sqlalchemy import SQLAlchemy
from .app_config_service import AppConfigService
from .app_config_service import call_config_loader
from .app_service import AppService
from .base_service import BaseService
from .conversation_service import ConversationService
from .language_model_service import LanguageModelService
from .retrieval_service import RetrievalService
from ..core.language_model.entities.model_entity import ModelFeature


@inject
@dataclass
class OpenAPIService(BaseService):
    """开放API服务"""
    db: SQLAlchemy
    app_service: AppService
    retrieval_service: RetrievalService
    app_config_service: AppConfigService
    conversation_service: ConversationService
    language_model_service: LanguageModelService

    def chat(self, req: OpenAPIChatReq, account: Account):
        """根据传递的请求+账号信息发起聊天对话，返回数据为块内容或者生成器"""
        # 1.判断当前应用是否属于当前账号
        app = self.app_service.get_app(req.app_id.data, account)

        # 2.判断当前应用是否已发布
        if app.status != AppStatus.PUBLISHED.value:
            raise NotFoundException("该应用不存在或未发布，请核实后重试")

        # 3.判断是否传递了终端用户id，如果传递了则检测终端用户关联的应用
        if req.end_user_id.data:
            end_user = self.get(EndUser, req.end_user_id.data)
            if not end_user or end_user.app_id != app.id:
                raise ForbiddenException("当前账号不存在或不属于该应用，请核实后重试")
        else:
            # 4.如果不存在则创建一个终端用户
            end_user = self.create(
                EndUser,
                **{"tenant_id": account.id, "app_id": app.id},
            )

        # 5.检测是否传递了会话id，如果传递了需要检测会话的归属信息
        if req.conversation_id.data:
            conversation = self.get(Conversation, req.conversation_id.data)
            if (
                    not conversation
                    or conversation.app_id != app.id
                    or conversation.invoke_from != InvokeFrom.SERVICE_API.value
                    or conversation.created_by != end_user.id
            ):
                raise ForbiddenException("该会话不存在，或者不属于该应用/终端用户/调用方式")
        else:
            # 6.如果不存在则创建会话信息
            conversation = self.create(Conversation, **{
                "app_id": app.id,
                "name": "New Conversation",
                "invoke_from": InvokeFrom.SERVICE_API.value,
                "created_by": end_user.id,
            })

        # 7.获取校验后的运行时配置
        app_config = call_config_loader(
            self.app_config_service.get_app_config,
            app,
            persist_changes=False,
        )

        # 8.在落库前解析运行时模型能力，避免带图请求被静默降级
        if hasattr(self.language_model_service, "resolve_runtime_language_model"):
            model_resolution = self.language_model_service.resolve_runtime_language_model(
                app_config.get("model_config", {}),
                image_urls=req.image_urls.data,
                entrypoint=LanguageModelService.ENTRYPOINT_OPENAPI,
            )
            llm = model_resolution.llm
            app_config["capabilities"] = model_resolution.capabilities
        else:
            model_resolution = None
            llm = self.language_model_service.load_language_model(app_config.get("model_config", {}))

        # 9.新建一条消息记录
        message = self.create(Message, **{
            "app_id": app.id,
            "conversation_id": conversation.id,
            "invoke_from": InvokeFrom.SERVICE_API,
            "created_by": end_user.id,
            "query": req.query.data,
            "image_urls": req.image_urls.data,
            "status": MessageStatus.NORMAL,
        })

        # 10.实例化TokenBufferMemory用于提取短期记忆
        token_buffer_memory = TokenBufferMemory(
            db=self.db,
            conversation=conversation,
            model_instance=llm,
        )
        history = token_buffer_memory.get_history_prompt_messages(
            message_limit=app_config["dialog_round"],
        )

        # 11.根据应用配置构建运行时工具
        tools = AppService._build_runtime_tools_for_config(
            app_config_service=self.app_config_service,
            retrieval_service=self.retrieval_service,
            app_service=self.app_service,
            account=account,
            draft_app_config=app_config,
            flask_app=current_app._get_current_object() if has_app_context() else None,
        )

        # 12.根据LLM是否支持tool_call决定使用不同的Agent
        agent_class = FunctionCallAgent if ModelFeature.TOOL_CALL.value in llm.features else ReACTAgent
        agent_binding_prompt_appendix = AppService._build_agent_binding_prompt_appendix(
            app_config.get("agent_bindings", [])
        )
        preset_prompt = app_config["preset_prompt"]
        prompt_parts = [preset_prompt.strip()]
        if agent_binding_prompt_appendix:
            prompt_parts.append(agent_binding_prompt_appendix.strip())
        preset_prompt = "\n\n".join(part for part in prompt_parts if part)
        agent = agent_class(
            llm=llm,
            agent_config=AgentConfig(
                user_id=account.id,
                invoke_from=InvokeFrom.DEBUGGER.value,
                preset_prompt=preset_prompt,
                enable_long_term_memory=app_config["long_term_memory"]["enable"],
                language_model_service=self.language_model_service,
                tools=tools,
                review_config=app_config["review_config"],
            ),
        )

        # 15.定义智能体状态基础数据
        agent_state = {
            "messages": [llm.convert_to_human_message(req.query.data, req.image_urls.data)],
            "history": history,
            "long_term_memory": conversation.summary,
        }

        # 16.根据stream类型差异执行不同的代码
        if req.stream.data is True:
            agent_thoughts_dict = {}

            # 在进入生成器之前提取所有需要的 ID，避免 DetachedInstanceError
            end_user_id = str(end_user.id)
            conversation_id = str(conversation.id)
            message_id = str(message.id)
            account_id = account.id
            app_id = app.id

            def handle_stream() -> Generator:
                """流式事件处理器，在Python只要在函数内部使用了yield关键字，那么这个函数的返回值类型肯定是生成器"""

                def save_agent_thoughts():
                    self.conversation_service.save_agent_thoughts(
                        account_id=account_id,
                        app_id=app_id,
                        app_config=app_config,
                        conversation_id=conversation_id,
                        message_id=message_id,
                        agent_thoughts=list(agent_thoughts_dict.values()),
                    )

                for agent_thought in agent.stream(agent_state):
                    # 提取thought以及answer
                    event_id = str(agent_thought.id)

                    # 将数据填充到agent_thought，便于存储到数据库服务中
                    if agent_thought.event != QueueEvent.PING.value:
                        # 除了agent_message数据为叠加，其他均为覆盖
                        if agent_thought.event == QueueEvent.AGENT_MESSAGE.value:
                            if event_id not in agent_thoughts_dict:
                                # 初始化智能体消息事件
                                agent_thoughts_dict[event_id] = agent_thought
                            else:
                                # 叠加智能体消息
                                agent_thoughts_dict[event_id] = agent_thoughts_dict[event_id].model_copy(update={
                                    "thought": agent_thoughts_dict[event_id].thought + agent_thought.thought,
                                    "answer": agent_thoughts_dict[event_id].answer + agent_thought.answer,
                                    "latency": agent_thought.latency,
                                })
                        else:
                            # 处理其他类型事件的消息
                            agent_thoughts_dict[event_id] = agent_thought
                    data = {
                        **agent_thought.model_dump(include={
                            "event", "thought", "observation", "tool", "tool_input", "answer", "latency",
                        }),
                        "id": event_id,
                        "end_user_id": end_user_id,
                        "conversation_id": conversation_id,
                        "message_id": message_id,
                        "task_id": str(agent_thought.task_id),
                    }
                    try:
                        yield f"event: {agent_thought.event.value}\ndata:{json.dumps(data)}\n\n"
                    except GeneratorExit:
                        save_agent_thoughts()
                        raise

                # 22.将消息以及推理过程添加到数据库
                save_agent_thoughts()

            return handle_stream()

        # 17.块内容输出
        agent_result = agent.invoke(agent_state)

        # 18.将消息以及推理过程添加到数据库
        self.conversation_service.save_agent_thoughts(
            account_id=account.id,
            app_id=app.id,
            app_config=app_config,
            conversation_id=conversation.id,
            message_id=message.id,
            agent_thoughts=agent_result.agent_thoughts,
        )
        output_payload = build_output_payload(agent_result.answer, agent_result.agent_thoughts)

        return Response(data={
            "id": str(message.id),
            "end_user_id": str(end_user.id),
            "conversation_id": str(conversation.id),
            "query": req.query.data,
            "image_urls": req.image_urls.data,
            "input_parts": build_input_parts(req.query.data, req.image_urls.data),
            "answer": agent_result.answer,
            "answer_parts": output_payload["answer_parts"],
            "artifacts": output_payload["artifacts"],
            "capabilities": model_resolution.capabilities if model_resolution else {},
            "total_token_count": 0,
            "latency": agent_result.latency,
            "agent_thoughts": [{
                "id": str(agent_thought.id),
                "event": agent_thought.event,
                "thought": agent_thought.thought,
                "observation": agent_thought.observation,
                "tool": agent_thought.tool,
                "tool_input": agent_thought.tool_input,
                "latency": agent_thought.latency,
                "created_at": 0,
            } for agent_thought in agent_result.agent_thoughts]
        })
