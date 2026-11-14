import json
import logging
from typing import Generator, Any
from uuid import UUID, uuid4
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
from internal.core.agent.entities.queue_entity import QueueEvent
from internal.core.agent.trace_context import AgentTraceContext
from internal.core.agent.usage_utils import summarize_agent_thoughts
from internal.core.language_model.entities.model_entity import ModelFeature
from internal.core.memory import TokenBufferMemory
from internal.entity.conversation_entity import InvokeFrom, MessageStatus
from internal.entity.dataset_entity import RetrievalSource
from .app_config_service import AppConfigService, call_config_loader
from .app_service import AppService
from .conversation_service import ConversationService
from .language_model_service import LanguageModelService
from .retrieval_service import RetrievalService
from internal.core.agent.agents import AgentQueueManager


@inject
@dataclass
class WebAppService(BaseService):
    """WebApp服务"""
    db: SQLAlchemy
    app_config_service: AppConfigService
    conversation_service: ConversationService
    language_model_service: LanguageModelService
    retrieval_service: RetrievalService
    app_service: AppService | None = None

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
        app_config = call_config_loader(
            self.app_config_service.get_app_config,
            app,
            persist_changes=False,
        )
        if hasattr(self.language_model_service, "describe_runtime_capabilities"):
            capabilities = self.language_model_service.describe_runtime_capabilities(
                app_config.get("model_config", {}),
                entrypoint=LanguageModelService.ENTRYPOINT_WEB_APP,
            )
        else:
            llm = self.language_model_service.load_language_model(app_config.get("model_config", {}))
            capabilities = {
                "features": list(getattr(llm, "features", []) or []),
                "image_input": {
                    "enabled": ModelFeature.IMAGE_INPUT.value in list(getattr(llm, "features", []) or []),
                },
            }

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
                "features": capabilities.get("features", []),
                "capabilities": capabilities,
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
        app_config = call_config_loader(
            self.app_config_service.get_app_config,
            app,
            persist_changes=False,
        )

        # 5.在落库前解析运行时模型能力，避免带图请求被静默降级
        if hasattr(self.language_model_service, "resolve_runtime_language_model"):
            model_resolution = self.language_model_service.resolve_runtime_language_model(
                app_config.get("model_config", {}),
                image_urls=req.image_urls.data,
                entrypoint=LanguageModelService.ENTRYPOINT_WEB_APP,
            )
            llm = model_resolution.llm
            app_config["capabilities"] = model_resolution.capabilities
        else:
            llm = self.language_model_service.load_language_model(app_config.get("model_config", {}))

        # 6.新建一条消息记录
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

        # 7.实例化TokenBufferMemory用于提取短期记忆
        token_buffer_memory = TokenBufferMemory(
            db=self.db,
            conversation=conversation,
            model_instance=llm,
        )
        history = token_buffer_memory.get_history_prompt_messages(
            message_limit=app_config["dialog_round"],
        )

        # 8.根据应用配置构建运行时工具
        tools = AppService._build_runtime_tools_for_config(
            app_config_service=self.app_config_service,
            retrieval_service=self.retrieval_service,
            app_service=self.app_service,
            account=account,
            draft_app_config=app_config,
            flask_app=current_app._get_current_object(),
            runtime_context=None,
        )

        # 9.复用运行时Agent工厂，确保已发布WebApp与调试态应用共用深度思考链路
        runtime_flask_app = current_app._get_current_object()
        agent = AppService._create_runtime_agent(
            llm=llm,
            account=account,
            draft_app_config=app_config,
            tools=tools,
            enable_deep_thinking=bool(req.enable_deep_thinking.data),
            flask_app=runtime_flask_app,
            invoke_from=InvokeFrom.WEB_APP.value,
        )

        # 13.定义字典存储推理过程，并调用智能体获取消息
        agent_thoughts = {}

        def save_agent_thoughts():
            self.conversation_service.save_agent_thoughts(
                account_id=account.id,
                app_id=app.id,
                app_config=app_config,
                conversation_id=conversation.id,
                message_id=message.id,
                agent_thoughts=list(agent_thoughts.values()),
            )

        task_id = uuid4()
        agent_state = {
            "messages": [llm.convert_to_human_message(req.query.data, req.image_urls.data)],
            "history": history,
            "long_term_memory": conversation.summary,
        }
        trace_context = None
        queue_manager = getattr(agent, "agent_queue_manager", None)
        if queue_manager is not None:
            trace_context = AgentTraceContext(queue_manager, task_id)
            agent_state["task_id"] = task_id

        stream = None
        try:
            stream = (
                agent.stream(agent_state, config=trace_context.runnable_config)
                if trace_context is not None
                else agent.stream(agent_state)
            )
            for agent_thought in stream:
                if agent_thought.event == QueueEvent.CALLABLE_TRACE:
                    try:
                        yield f"event: callable_trace\ndata:{agent_thought.observation}\n\n"
                    except GeneratorExit:
                        try:
                            save_agent_thoughts()
                        except Exception as error:  # noqa: BLE001
                            logging.getLogger(__name__).error(
                                "保存WebApp推理过程失败: error_type=%s", type(error).__name__
                            )
                        raise
                    continue

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
                usage_summary = summarize_agent_thoughts(agent_thoughts.values())
                data = {
                    **agent_thought.model_dump(include={
                        "event", "thought", "observation", "tool", "tool_input", "answer",
                        "total_token_count", "total_price", "latency",
                    }),
                    "aggregate_total_token_count": usage_summary.total_token_count,
                    "aggregate_total_price": usage_summary.total_price,
                    "aggregate_latency": usage_summary.latency,
                    "id": event_id,
                    "conversation_id": str(conversation.id),
                    "message_id": str(message.id),
                    "task_id": str(agent_thought.task_id),
                }
                try:
                    yield f"event: {agent_thought.event.value}\ndata:{json.dumps(data)}\n\n"
                except GeneratorExit:
                    try:
                        save_agent_thoughts()
                    except Exception as error:  # noqa: BLE001
                        logging.getLogger(__name__).error(
                            "保存WebApp推理过程失败: error_type=%s", type(error).__name__
                        )
                    raise
        finally:
            close_stream = getattr(stream, "close", None)
            try:
                if callable(close_stream):
                    close_stream()
            finally:
                if trace_context is not None:
                    trace_context.close()

        # 20.将消息以及推理过程添加到数据库（同步方式）
        save_agent_thoughts()

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
        ).order_by(desc(Conversation.created_at), desc(Conversation.id)).offset(offset).limit(safe_page_size).all()

        return conversations
