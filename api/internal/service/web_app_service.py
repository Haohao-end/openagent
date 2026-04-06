import json
from typing import Generator, Any
from uuid import UUID
from flask import current_app
from injector import inject
from langchain_core.messages import HumanMessage
from sqlalchemy import desc
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from internal.entity.app_entity import AppStatus
from internal.model import App, Account, Conversation, Message
from internal.exception import NotFoundException, ForbiddenException
from dataclasses import dataclass
from internal.schema.web_app_schema import WebAppChatReq
from internal.core.agent.agents import FunctionCallAgent, ReACTAgent, AgentQueueManager
from internal.core.agent.entities.agent_entity import AgentConfig
from internal.core.agent.entities.queue_entity import QueueEvent
from internal.core.language_model.entities.model_entity import ModelFeature
from internal.core.memory import TokenBufferMemory
from internal.entity.conversation_entity import InvokeFrom, MessageStatus
from internal.entity.dataset_entity import RetrievalSource
from .app_config_service import AppConfigService
from .conversation_service import ConversationService
from .language_model_service import LanguageModelService
from .retrieval_service import RetrievalService


@inject
@dataclass
class WebAppService(BaseService):
    """WebApp服务"""
    db: SQLAlchemy
    app_config_service: AppConfigService
    conversation_service: ConversationService
    language_model_service: LanguageModelService
    retrieval_service: RetrievalService

    def get_web_app(self, token: str) -> App:
        """根据传递的token获取WebApp实例"""
        # 1.在数据库中查询token对应的应用
        app = self.db.session.query(App).filter(
            App.token == token
        ).one_or_none()

        if not app or app.status != AppStatus.PUBLISHED.value:
            raise NotFoundException("该WebApp不存在 请核实后重试")

        # 2.返回查询的应用
        return app

    def get_web_app_info(self, token: str) -> dict[str, Any]:
        """根据传递的token获取WebApp信息"""
        # 1.获取App基础信息
        app = self.get_web_app(token)

        # 2.根据App基础信息构建LLM
        app_config = self.app_config_service.get_app_config(app)
        llm = self.language_model_service.load_language_model(app_config.get("model_config", {}))

        # 3.提取信息并返回
        return {
            "id": str(app.id),
            "icon": app.icon,
            "name": app.name,
            "description": app.description,
            "app_config": {
                "opening_statement": app_config.get("opening_statement"),
                "opening_questions": app_config.get("opening_questions"),
                "suggested_after_answer": app_config.get("suggested_after_answer"),
                "features": llm.features,
                "text_to_speech": app_config.get("text_to_speech"),
                "speech_to_text": app_config.get("speech_to_text"),
            }
        }

    def web_app_chat(self, token: str, req: WebAppChatReq, account: Account) -> Generator:
        """根据传递的token凭证+请求与指定的WebApp进行对话"""
        # 1.获取WebApp应用并校验应用是否发布
        app = self.get_web_app(token)

        # 2.检测是否传递了会话id，如果传递了需要校验会话的归属信息
        if req.conversation_id.data:
            conversation = self.get(Conversation, req.conversation_id.data)
            if (
                    not conversation
                    or conversation.app_id != app.id
                    or conversation.invoke_from != InvokeFrom.WEB_APP.value
                    or conversation.created_by != account.id
                    or conversation.is_deleted is True
            ):
                raise ForbiddenException("该会话不存在，或者不属于当前应用/用户/调用方式")
        else:
            # 3.如果没传递conversation_id表示新会话，这时候需要创建一个会话
            conversation = self.create(Conversation, **{
                "app_id": app.id,
                "name": "New Conversation",
                "invoke_from": InvokeFrom.WEB_APP.value,
                "created_by": account.id,
            })

        # 4.获取校验后的运行时配置
        app_config = self.app_config_service.get_app_config(app)

        # 5.新建一条消息记录
        message = self.create(
            Message,
            app_id=app.id,
            conversation_id=conversation.id,
            invoke_from=InvokeFrom.WEB_APP,
            created_by=account.id,
            query=req.query.data,
            image_urls=req.image_urls.data,
            status=MessageStatus.NORMAL,
        )

        # 6.从语言模型管理器中加载大语言模型
        llm = self.language_model_service.load_language_model(app_config.get("model_config", {}))

        # 7.实例化TokenBufferMemory用于提取短期记忆
        token_buffer_memory = TokenBufferMemory(
            db=self.db,
            conversation=conversation,
            model_instance=llm,
        )
        history = token_buffer_memory.get_history_prompt_messages(
            message_limit=app_config["dialog_round"],
        )

        # 8.将草稿配置中的tools转换成LangChain工具
        tools = self.app_config_service.get_langchain_tools_by_tools_config(app_config["tools"])

        # 9.检测是否关联了知识库
        if app_config["datasets"]:
            # 10.构建LangChain知识库检索工具
            dataset_retrieval = self.retrieval_service.create_langchain_tool_from_search(
                flask_app=current_app._get_current_object(),
                dataset_ids=[dataset["id"] for dataset in app_config["datasets"]],
                account_id=account.id,
                retrieval_source=RetrievalSource.APP.value,
                **app_config["retrieval_config"],
            )
            tools.append(dataset_retrieval)

        # 11.检测是否关联工作流，如果关联了工作流则将工作流构建成工具添加到tools中
        if app_config["workflows"]:
            workflow_tools = self.app_config_service.get_langchain_tools_by_workflow_ids(
                [workflow["id"] for workflow in app_config["workflows"]]
            )
            tools.extend(workflow_tools)

        # 12.根据LLM是否支持tool_call决定使用不同的Agent
        agent_class = FunctionCallAgent if ModelFeature.TOOL_CALL.value in llm.features else ReACTAgent
        agent = agent_class(
            llm=llm,
            agent_config=AgentConfig(
                user_id=account.id,
                invoke_from=InvokeFrom.WEB_APP.value,
                preset_prompt=app_config["preset_prompt"],
                enable_long_term_memory=app_config["long_term_memory"]["enable"],
                tools=tools,
                review_config=app_config["review_config"],
            ),
        )

        # 13.定义字典存储推理过程，并调用智能体获取消息
        agent_thoughts = {}
        for agent_thought in agent.stream({
            "messages": [llm.convert_to_human_message(req.query.data, req.image_urls.data)],
            "history": history,
            "long_term_memory": conversation.summary,
        }):
            # 14.提取thought以及answer
            event_id = str(agent_thought.id)

            # 15.将数据填充到agent_thought，便于存储到数据库服务中
            if agent_thought.event != QueueEvent.PING.value:
                # 16.除了agent_message数据为叠加，其他均为覆盖
                if agent_thought.event == QueueEvent.AGENT_MESSAGE.value:
                    if event_id not in agent_thoughts:
                        # 17.初始化智能体消息事件
                        agent_thoughts[event_id] = agent_thought
                    else:
                        # 18.叠加智能体消息
                        agent_thoughts[event_id] = agent_thoughts[event_id].model_copy(update={
                            "thought": agent_thoughts[event_id].thought + agent_thought.thought,
                            # 消息相关数据
                            "message": agent_thought.message,
                            "message_token_count": agent_thought.message_token_count,
                            "message_unit_price": agent_thought.message_unit_price,
                            "message_price_unit": agent_thought.message_price_unit,
                            # 答案相关数据
                            "answer": agent_thoughts[event_id].answer + agent_thought.answer,
                            "answer_token_count": agent_thought.answer_token_count,
                            "answer_unit_price": agent_thought.answer_unit_price,
                            "answer_price_unit": agent_thought.answer_price_unit,
                            # Agent推理统计相关
                            "total_token_count": agent_thought.total_token_count,
                            "total_price": agent_thought.total_price,
                            "latency": agent_thought.latency,
                        })
                else:
                    # 19.处理其他类型事件的消息
                    agent_thoughts[event_id] = agent_thought
            data = {
                **agent_thought.model_dump(include={
                    "event", "thought", "observation", "tool", "tool_input", "answer",
                    "total_token_count", "total_price", "latency",
                }),
                "id": event_id,
                "conversation_id": str(conversation.id),
                "message_id": str(message.id),
                "task_id": str(agent_thought.task_id),
            }
            yield f"event: {agent_thought.event.value}\ndata:{json.dumps(data)}\n\n"

        # 20.将消息以及推理过程添加到数据库（同步方式）
        self.conversation_service.save_agent_thoughts(
            account_id=account.id,
            app_id=app.id,
            app_config=app_config,
            conversation_id=conversation.id,
            message_id=message.id,
            agent_thoughts=[agent_thought for agent_thought in agent_thoughts.values()],
        )

    def stop_web_app_chat(self, token: str, task_id: UUID, account: Account):
        """根据传递的token+task_id停止与指定WebApp对话"""
        # 1.获取WebApp应用并校验应用是否发布
        self.get_web_app(token)

        # 2.调用智能体队列管理器停止特定服务
        AgentQueueManager.set_stop_flag(task_id, InvokeFrom.WEB_APP.value, account.id)

    def get_conversations(
            self,
            token: str,
            is_pinned: bool,
            account: Account,
            current_page: int = 1,
            page_size: int = 20,
    ) -> list[Conversation]:
        """根据传递的token+is_pinned+account获取指定账号在该WebApp下的会话列表信息"""
        # 1.获取WebApp应用并校验应用是否发布
        app = self.get_web_app(token)

        safe_current_page = max(1, int(current_page or 1))
        safe_page_size = max(1, min(int(page_size or 20), 100))
        offset = (safe_current_page - 1) * safe_page_size

        # 2.筛选过滤并查询数据
        conversations = self.db.session.query(Conversation).filter(
            Conversation.app_id == app.id,
            Conversation.created_by == account.id,
            Conversation.invoke_from == InvokeFrom.WEB_APP.value,
            Conversation.is_pinned == is_pinned,
            Conversation.is_deleted == False
        ).order_by(desc("created_at")).offset(offset).limit(safe_page_size).all()

        return conversations
