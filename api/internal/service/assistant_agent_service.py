import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Generator
from uuid import UUID

from flask import current_app
from injector import inject
from redis import Redis
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    trim_messages,
)
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc
from sqlalchemy.orm import selectinload

from internal.core.agent.agents import A2AFunctionCallAgent, AgentQueueManager
from internal.core.agent.entities.agent_entity import AgentConfig
from internal.core.agent.entities.queue_entity import QueueEvent
from internal.entity.assistant_agent_entity import ASSISTANT_AGENT_DISPLAY_NAME
from internal.core.language_model.entities.model_entity import ModelFeature
from internal.core.language_model.providers.deepseek.chat import Chat as DeepSeekChat
from internal.core.memory import TokenBufferMemory
from internal.entity.conversation_entity import InvokeFrom, MessageStatus
from internal.lib.helper import datetime_to_timestamp
from internal.model import Account, Conversation, Message
from internal.schema.assistant_agent_schema import (
    AssistantAgentChat,
    GetAssistantAgentConversationsReq,
    GetAssistantAgentMessagesWithPageReq,
)
from internal.task.app_task import auto_create_app
from internal.exception import NotFoundException
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy

from .base_service import BaseService
from .conversation_service import ConversationService
from .faiss_service import FaissService
from .public_agent_a2a_service import PublicAgentA2AService
from .public_agent_registry_service import PublicAgentRegistryService

ASSISTANT_AGENT_MARKDOWN_PRESET_PROMPT = """请遵守以下回复规范：
1. 默认使用Markdown格式输出，优先使用标题、列表、表格、引用和代码块来组织信息。
2. 涉及代码、命令、配置、SQL、JSON、YAML时，必须使用带语言标识的Markdown代码块。
3. 如果没有明确结构化内容需求，也请保持清晰的Markdown排版，不要输出纯大段文本。
4. 当需要调用工具时，优先调用工具；拿到结果后再按上述Markdown规范整理答案。
5. 当用户明确要求“使用/调用/交给某个智能体回答”，或问题明显更适合由某个已发布公共Agent处理时，必须优先调用 `route_public_agents` 工具。
6. `route_public_agents` 会自动完成“检索已有公共Agent + 调用对应Agent + 返回结果”，因此当用户直接要答案时，优先使用它，而不是只返回候选列表。
7. `create_app` 仅用于用户明确要求“我想要/帮我生成/创建/新建/生成/搭建一个新的Agent或应用”等类型的问题时，普通问答场景禁止调用。
8. 如果用户说“请使用xx智能体回答”“让xxAgent来回答”“帮我解决xx”“帮我解决xx等垂直问题”等这是调用已有Agent，不是创建新Agent，禁止调用 `create_app`。
9. 当“调用已有Agent”和“创建新Agent”存在歧义时，默认先调用 `route_public_agents`，不要擅自创建新应用。
""".strip()


@inject
@dataclass
class AssistantAgentService(BaseService):
    """辅助智能体服务"""

    db: SQLAlchemy
    faiss_service: FaissService
    conversation_service: ConversationService
    redis_client: Redis
    public_agent_a2a_service: PublicAgentA2AService | None = None
    public_agent_registry_service: PublicAgentRegistryService | None = None

    @classmethod
    def _resolve_conversation_id(cls, conversation_id: str) -> UUID | None:
        """将会话id字符串解析成UUID，不存在时返回None"""
        normalized = str(conversation_id or "").strip()
        if not normalized:
            return None
        return UUID(normalized)

    def _resolve_assistant_agent_conversation(
        self,
        account: Account,
        conversation_id: UUID | None = None,
        sync_active: bool = False,
    ) -> Conversation:
        """解析并返回辅助Agent会话，必要时同步账号当前会话指针"""
        if conversation_id is None:
            return account.assistant_agent_conversation

        conversation = self.get(Conversation, conversation_id)
        if (
            not conversation
            or conversation.created_by != account.id
            or conversation.is_deleted
            or conversation.invoke_from != InvokeFrom.ASSISTANT_AGENT.value
        ):
            raise NotFoundException(f"该{ASSISTANT_AGENT_DISPLAY_NAME}会话不存在或已被删除，请核实后重试")

        if sync_active and account.assistant_agent_conversation_id != conversation.id:
            self.update(account, assistant_agent_conversation_id=conversation.id)

        return conversation

    def chat(self, req: AssistantAgentChat, account: Account) -> Generator:
        """传递query与账号实现与辅助Agent进行会话"""
        # 1.获取辅助Agent对应的id
        assistant_agent_id = current_app.config.get("ASSISTANT_AGENT_ID")

        # 2.获取当前会话信息（支持按conversation_id切换）
        conversation = self._resolve_assistant_agent_conversation(
            account=account,
            conversation_id=self._resolve_conversation_id(req.conversation_id.data),
            sync_active=True,
        )

        # 3.新建一条消息记录
        message = self.create(
            Message,
            app_id=assistant_agent_id,
            conversation_id=conversation.id,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            created_by=account.id,
            query=req.query.data,
            image_urls=req.image_urls.data,
            status=MessageStatus.NORMAL.value,
        )

        # 4.使用DeepSeek模型作为辅助Agent的LLM大脑
        llm = DeepSeekChat(
            model="deepseek-chat",
            temperature=0.8,
            features=[
                ModelFeature.TOOL_CALL.value,
                ModelFeature.AGENT_THOUGHT.value,
            ],
            metadata={},
        )

        # 5.实例化TokenBufferMemory用于提取短期记忆
        token_buffer_memory = TokenBufferMemory(
            db=self.db,
            conversation=conversation,
            model_instance=llm,
        )
        history = token_buffer_memory.get_history_prompt_messages(message_limit=3)

        # 6.将草稿配置中的tools转换成LangChain工具
        search_public_agents_tool = (
            self.public_agent_registry_service.convert_public_agent_search_to_tool()
            if self.public_agent_registry_service
            else self.faiss_service.convert_faiss_to_tool()
        )
        tools = []
        if self.public_agent_a2a_service:
            tools.append(self.public_agent_a2a_service.convert_public_agent_route_to_tool(account.id))
        tools.extend([
            search_public_agents_tool,
            self.convert_create_app_to_tool(account.id),
        ])

        # 7.构建辅助Agent专用智能体，避免工具调用前的过渡文案直接暴露给用户
        agent = A2AFunctionCallAgent(
            llm=llm,
            agent_config=AgentConfig(
                user_id=account.id,
                invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
                preset_prompt=ASSISTANT_AGENT_MARKDOWN_PRESET_PROMPT,
                enable_long_term_memory=True,
                tools=tools,
            ),
        )

        agent_thoughts = {}
        for agent_thought in agent.stream(
            {
                "messages": [
                    llm.convert_to_human_message(req.query.data, req.image_urls.data)
                ],
                "history": history,
                "long_term_memory": conversation.summary,
            }
        ):
            # 8.提取thought以及answer
            event_id = str(agent_thought.id)

            # 9.将数据填充到agent_thought，便于存储到数据库服务中
            if agent_thought.event != QueueEvent.PING.value:
                # 10.除了agent_message数据为叠加，其他均为覆盖
                if agent_thought.event == QueueEvent.AGENT_MESSAGE.value:
                    if event_id not in agent_thoughts:
                        # 11.初始化智能体消息事件
                        agent_thoughts[event_id] = agent_thought
                    else:
                        # 12.叠加智能体消息
                        agent_thoughts[event_id] = agent_thoughts[event_id].model_copy(
                            update={
                                "thought": agent_thoughts[event_id].thought
                                + agent_thought.thought,
                                # 消息相关数据
                                "message": agent_thought.message,
                                "message_token_count": agent_thought.message_token_count,
                                "message_unit_price": agent_thought.message_unit_price,
                                "message_price_unit": agent_thought.message_price_unit,
                                # 答案相关字段
                                "answer": agent_thoughts[event_id].answer
                                + agent_thought.answer,
                                "answer_token_count": agent_thought.answer_token_count,
                                "answer_unit_price": agent_thought.answer_unit_price,
                                "answer_price_unit": agent_thought.answer_price_unit,
                                # Agent推理统计相关
                                "total_token_count": agent_thought.total_token_count,
                                "total_price": agent_thought.total_price,
                                "latency": agent_thought.latency,
                            }
                        )
                else:
                    # 13.处理其他类型事件的消息
                    agent_thoughts[event_id] = agent_thought
            data = {
                **agent_thought.model_dump(
                    include={
                        "event",
                        "thought",
                        "observation",
                        "tool",
                        "tool_input",
                        "answer",
                        "latency",
                        "total_token_count",
                    }
                ),
                "id": event_id,
                "conversation_id": str(conversation.id),
                "message_id": str(message.id),
                "task_id": str(agent_thought.task_id),
            }
            yield f"event: {agent_thought.event.value}\ndata:{json.dumps(data)}\n\n"

        # 14.将消息以及推理过程添加到数据库
        self.conversation_service.save_agent_thoughts(
            account_id=account.id,
            app_id=assistant_agent_id,
            app_config={
                "long_term_memory": {"enable": True},
            },
            conversation_id=conversation.id,
            message_id=message.id,
            agent_thoughts=[agent_thought for agent_thought in agent_thoughts.values()],
        )

    def generate_introduction(self, account: Account) -> Generator[str, None, None]:
        """流式生成首页辅助Agent个性化介绍（支持缓存优化）"""
        # 1.按账号全局查询最近5条有效对话消息（覆盖辅助Agent和其他Agent）
        latest_messages = (
            self.db.session.query(Message)
            .filter(
                Message.created_by == account.id,
                Message.status.in_(
                    [MessageStatus.STOP.value, MessageStatus.NORMAL.value]
                ),
                Message.query != "",
                Message.answer != "",
                ~Message.is_deleted,
            )
            .order_by(desc(Message.created_at))
            .limit(5)
            .all()
        )
        suggested_questions_message_id = (
            str(latest_messages[0].id) if len(latest_messages) > 0 else ""
        )

        # 2.查询账号维度最近会话摘要，增强跨会话语义理解
        summary_rows = (
            self.db.session.query(Conversation.summary)
            .filter(
                Conversation.created_by == account.id,
                Conversation.summary != "",
                ~Conversation.is_deleted,
            )
            .order_by(desc(Conversation.updated_at))
            .limit(3)
            .all()
        )
        summary_parts = [
            row[0].strip() for row in summary_rows if row and row[0] and row[0].strip()
        ]
        summary = "\n\n".join(summary_parts).strip()
        display_name = (account.name or "").strip() or "朋友"

        # 3.判断是否首次使用（无历史消息且无历史摘要）
        if len(latest_messages) == 0 and summary == "":
            data = {
                "content": "",
                "is_first_time": True,
                "message_id": "",
                "suggested_questions_message_id": "",
            }
            yield f"event: intro_done\ndata:{json.dumps(data)}\n\n"
            return

        # 4.生成消息指纹并尝试从缓存获取
        message_ids = [str(msg.id) for msg in latest_messages]
        fingerprint = self._generate_message_fingerprint(message_ids, summary)
        cached_data = self._get_cached_introduction(account.id, fingerprint)

        # 5.如果缓存命中，直接返回缓存内容（模拟流式输出）
        if cached_data:
            logging.info(
                f"辅助Agent介绍命中缓存，账号ID: {account.id}, 指纹: {fingerprint}"
            )
            # 模拟流式输出缓存内容，提升用户体验
            cached_introduction = cached_data.get("introduction", "")
            chunk_size = 20  # 每次输出20个字符
            for i in range(0, len(cached_introduction), chunk_size):
                chunk = cached_introduction[i : i + chunk_size]
                data = {"content": chunk}
                yield f"event: intro_chunk\ndata:{json.dumps(data)}\n\n"

            # 输出完成事件
            done_data = {
                "content": cached_introduction,
                "is_first_time": False,
                "message_id": cached_data.get("suggested_questions_message_id", ""),
                "suggested_questions_message_id": cached_data.get(
                    "suggested_questions_message_id", ""
                ),
            }
            yield f"event: intro_done\ndata:{json.dumps(done_data)}\n\n"
            return

        # 6.缓存未命中，调用LLM生成新内容
        logging.info(
            f"辅助Agent介绍缓存未命中，调用LLM生成，账号ID: {account.id}, 指纹: {fingerprint}"
        )

        # 7.准备DeepSeek模型并构建提示消息
        llm = DeepSeekChat(
            model="deepseek-chat",
            temperature=0.7,
            features=[ModelFeature.TOOL_CALL.value, ModelFeature.AGENT_THOUGHT.value],
            metadata={},
        )

        prompt_messages = self._build_introduction_prompt_messages(
            account=account,
            summary=summary,
            messages=list(reversed(latest_messages)),
        )

        # 8.对提示消息做截断，防止上下文过长导致高耗时与高消耗
        max_token_limit = 1800
        try:
            prompt_messages = trim_messages(
                messages=prompt_messages,
                max_tokens=max_token_limit,
                token_counter=llm,
                strategy="last",
                start_on="human",
                end_on="ai",
            )
        except Exception:
            logging.exception(
                "辅助Agent介绍提示词trim_messages失败，将退化为原始消息继续生成"
            )

        # 9.流式生成并持续返回前端
        introduction = ""
        try:
            for chunk in llm.stream(prompt_messages):
                chunk_content = self._extract_chunk_content(
                    chunk.content if hasattr(chunk, "content") else chunk
                )
                if not chunk_content:
                    continue

                introduction += chunk_content
                data = {"content": chunk_content}
                yield f"event: intro_chunk\ndata:{json.dumps(data)}\n\n"
        except Exception:
            logging.exception("辅助Agent介绍流式生成失败")
            error_data = {"observation": "个性化介绍生成失败，请稍后重试"}
            yield f"event: error\ndata:{json.dumps(error_data)}\n\n"
            return

        # 10.输出完成事件
        formatted_introduction = self._ensure_introduction_markdown(
            introduction=introduction.strip(),
            display_name=display_name,
        )
        done_data = {
            "content": formatted_introduction,
            "is_first_time": False,
            "message_id": suggested_questions_message_id,
            "suggested_questions_message_id": suggested_questions_message_id,
        }
        yield f"event: intro_done\ndata:{json.dumps(done_data)}\n\n"

        # 11.将生成的内容缓存到Redis（TTL: 1小时）
        cache_data = {
            "introduction": formatted_introduction,
            "suggested_questions_message_id": suggested_questions_message_id,
            "generated_at": datetime.now(UTC).isoformat(),
        }
        self._set_cached_introduction(account.id, fingerprint, cache_data, ttl=3600)

    @classmethod
    def stop_chat(cls, task_id: UUID, account: Account) -> None:
        """根据传递的任务id+账号停止某次响应会话"""
        AgentQueueManager.set_stop_flag(
            task_id, InvokeFrom.ASSISTANT_AGENT.value, account.id
        )

    def get_conversation_messages_with_page(
        self, req: GetAssistantAgentMessagesWithPageReq, account: Account
    ) -> tuple[list[Message], Paginator]:
        """根据传递的请求+账号获取与辅助Agent对话的消息分页列表"""
        # 1.获取会话信息（支持按conversation_id切换）
        conversation = self._resolve_assistant_agent_conversation(
            account=account,
            conversation_id=self._resolve_conversation_id(req.conversation_id.data),
            sync_active=False,
        )

        # 2. 构建分页器并构建过滤条件
        paginator = Paginator(db=self.db, req=req)
        filters = [
            Message.conversation_id == conversation.id,
            Message.status.in_([MessageStatus.STOP.value, MessageStatus.NORMAL.value]),
            Message.query != "",  # 只过滤用户提问不为空的消息，允许答案为空（正在生成中）
            ~Message.is_deleted,
        ]

        if req.created_at.data:
            # 3. 将时间戳转换成 DateTime
            created_at_datetime = datetime.fromtimestamp(req.created_at.data, UTC)
            filters.append(Message.created_at <= created_at_datetime)

        # 4. 分页查询 ID 列表
        paginated_ids = paginator.paginate(
            self.db.session.query(Message.id)
            .filter(*filters)
            .order_by(desc(Message.created_at))
        )

        # 5. 加载完整的消息及其关联数据，避免 N+1 查询
        if not paginated_ids:
            return [], paginator

        # Extract IDs from paginated_ids (handle Row objects from SQLAlchemy)
        id_list = []
        for item in paginated_ids:
            # Row objects can be indexed like tuples
            if hasattr(item, '__getitem__'):
                id_list.append(item[0])
            else:
                id_list.append(item)

        messages = (
            self.db.session.query(Message)
            .options(selectinload(Message.agent_thoughts))
            .filter(Message.id.in_(id_list))
            .order_by(desc(Message.created_at))
            .all()
        )

        return messages, paginator

    def get_conversations(
        self,
        req: GetAssistantAgentConversationsReq,
        account: Account,
    ) -> list[dict]:
        """获取当前账号的辅助Agent最近会话列表"""
        assistant_agent_id = current_app.config.get("ASSISTANT_AGENT_ID")
        limit = req.limit.data or 20
        active_conversation_id = account.assistant_agent_conversation_id

        has_valid_message = (
            self.db.session.query(Message.id)
            .filter(
                and_(
                    Message.conversation_id == Conversation.id,
                    Message.status.in_(
                        [MessageStatus.STOP.value, MessageStatus.NORMAL.value]
                    ),
                    Message.query != "",  # 只过滤用户提问不为空的消息
                    ~Message.is_deleted,
                )
            )
            .exists()
        )

        conversations = (
            self.db.session.query(Conversation)
            .filter(
                Conversation.app_id == assistant_agent_id,
                Conversation.created_by == account.id,
                Conversation.invoke_from == InvokeFrom.ASSISTANT_AGENT.value,
                ~Conversation.is_deleted,
                has_valid_message,
            )
            .order_by(desc(Conversation.updated_at))
            .limit(limit)
            .all()
        )

        return [
            {
                "id": conversation.id,
                "name": conversation.name,
                "is_active": conversation.id == active_conversation_id,
                "updated_at": datetime_to_timestamp(conversation.updated_at),
                "created_at": datetime_to_timestamp(conversation.created_at),
            }
            for conversation in conversations
        ]

    def delete_conversation(self, account: Account) -> None:
        """根据传递的账号，清空辅助Agent智能体会话消息列表"""
        # 清空会话时同时清除缓存
        self._clear_introduction_cache(account.id)
        self.update(account, assistant_agent_conversation_id=None)

    def _generate_introduction_cache_key(self, account_id: UUID, fingerprint: str) -> str:
        """生成介绍内容的缓存键"""
        return f"assistant_agent:introduction:{account_id}:{fingerprint}"

    def _generate_message_fingerprint(
        self, message_ids: list[str], summary: str
    ) -> str:
        """生成消息指纹，用于检测内容是否变化"""
        # 将消息ID列表和摘要内容组合后生成MD5哈希
        content = f"{','.join(message_ids)}:{summary}"
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def _get_cached_introduction(
        self, account_id: UUID, fingerprint: str
    ) -> dict | None:
        """从Redis获取缓存的介绍内容"""
        cache_key = self._generate_introduction_cache_key(account_id, fingerprint)
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception:
            logging.exception("获取辅助Agent介绍缓存失败")
        return None

    def _set_cached_introduction(
        self, account_id: UUID, fingerprint: str, data: dict, ttl: int = 3600
    ) -> None:
        """将介绍内容缓存到Redis"""
        cache_key = self._generate_introduction_cache_key(account_id, fingerprint)
        try:
            self.redis_client.setex(
                cache_key,
                ttl,
                json.dumps(data, ensure_ascii=False),
            )
        except Exception:
            logging.exception("设置辅助Agent介绍缓存失败")

    def _clear_introduction_cache(self, account_id: UUID) -> None:
        """清除指定账号的所有介绍缓存"""
        try:
            # 使用模式匹配删除该账号的所有缓存
            pattern = f"assistant_agent:introduction:{account_id}:*"
            cursor = 0
            while True:
                cursor, keys = self.redis_client.scan(
                    cursor=cursor, match=pattern, count=100
                )
                if keys:
                    self.redis_client.delete(*keys)
                if cursor == 0:
                    break
        except Exception:
            logging.exception("清除辅助Agent介绍缓存失败")

    @classmethod
    def _build_introduction_prompt_messages(
        cls,
        account: Account,
        summary: str,
        messages: list[Message],
    ) -> list:
        """构建个性化介绍提示消息列表"""
        user_name = (account.name or "").strip()
        display_name = user_name if user_name else "朋友"
        prompt_messages = [
            SystemMessage(
                content=f"""
你是LLMOps平台中的"{ASSISTANT_AGENT_DISPLAY_NAME}"，你的输出将直接展示在首页开场介绍中。
请基于用户历史信息生成一段"个性化欢迎介绍"，要求如下：
1. 开头必须包含问候语：Hi，{display_name}
2. 先识别该用户近期意图与关注方向，再给出针对性引导；不要编造不存在的信息。
3. 明确说明你支持基于用户输入进行 function call，自动调用工具并帮助生成垂直Agent的后端能力代码与应用配置。
4. 内容要兼顾"欢迎介绍 + 下一步建议"，可给2~4条简短建议。
5. 语气专业、自然、简洁，长度控制在120~260字，输出必须是Markdown格式。
6. 建议使用二级或三级标题 + 2~4条列表项，让排版更清晰；不要输出JSON。
7. 输出语言尽量与用户最近提问语言保持一致；如果无法判断则使用中文。
""".strip()
            )
        ]

        # 把会话摘要作为一组人类/AI消息注入，便于trim_messages按照轮次裁剪
        if summary:
            prompt_messages.extend(
                [
                    HumanMessage(content=f"用户历史会话摘要如下：\n{summary}"),
                    AIMessage(
                        content="我已读取用户历史摘要，将结合摘要输出个性化介绍。"
                    ),
                ]
            )

        # 最近消息作为上下文输入
        for item in messages:
            query = (item.query or "").strip()
            answer = (item.answer or "").strip()
            if query:
                prompt_messages.append(HumanMessage(content=query))
            if answer:
                prompt_messages.append(AIMessage(content=answer))

        return prompt_messages

    @classmethod
    def _extract_chunk_content(cls, chunk_content: object) -> str:
        """统一解析DeepSeek流式chunk内容，兼容字符串与分块结构"""
        if chunk_content is None:
            return ""

        if isinstance(chunk_content, str):
            return chunk_content

        if isinstance(chunk_content, dict):
            return str(chunk_content.get("text", ""))

        if isinstance(chunk_content, list):
            texts = []
            for item in chunk_content:
                if isinstance(item, str):
                    texts.append(item)
                elif isinstance(item, dict):
                    texts.append(str(item.get("text", "")))
                else:
                    texts.append(str(item))
            return "".join(texts)

        return str(chunk_content)

    @classmethod
    def _contains_markdown_syntax(cls, content: str) -> bool:
        """检测内容是否已经包含明显Markdown结构"""
        if "```" in content:
            return True

        markdown_pattern = re.compile(
            r"(^|\n)\s*(#{1,6}\s|[-*+]\s|\d+\.\s|>\s|\|.+\|)"
        )
        inline_pattern = re.compile(r"`[^`]+`")
        return bool(markdown_pattern.search(content) or inline_pattern.search(content))

    @classmethod
    def _ensure_introduction_markdown(cls, introduction: str, display_name: str) -> str:
        """将介绍内容兜底格式化为Markdown，避免纯文本展示"""
        normalized = (introduction or "").strip()
        if not normalized:
            return (
                f"### Hi，{display_name}\n\n"
                "- 我可以帮你快速创建专属 AI 应用。\n"
                "- 你可以直接告诉我你的目标、行业和功能需求。"
            )

        if cls._contains_markdown_syntax(normalized):
            return normalized

        lines = [line.strip() for line in normalized.splitlines() if line.strip()]
        sentence_parts: list[str] = []
        for line in lines:
            sentence_parts.extend(
                [part.strip() for part in re.split(r"[。！？!?]\s*", line) if part.strip()]
            )

        if not sentence_parts:
            return f"### Hi，{display_name}\n\n{normalized}"

        title = f"### Hi，{display_name}"
        summary = sentence_parts[0]
        suggestions = sentence_parts[1:4]

        markdown_lines = [title, "", summary]
        if suggestions:
            markdown_lines.extend(["", "#### 建议下一步"])
            markdown_lines.extend([f"- {item}" for item in suggestions])

        return "\n".join(markdown_lines)

    @classmethod
    def convert_create_app_to_tool(cls, account_id: UUID) -> BaseTool:
        """定义自动创建Agent应用LangChain工具"""

        class CreateAppInput(BaseModel):
            """创建Agent/应用输入结构"""

            name: str = Field(
                description="需要创建的Agent/应用名称，长度不超过50个字符"
            )
            description: str = Field(
                description="需要创建的Agent/应用描述，请详细概括该应用的功能"
            )

        @tool("create_app", args_schema=CreateAppInput)
        def create_app(name: str, description: str) -> str:
            """仅当用户明确要求你创建/新建/生成/搭建一个新的Agent或应用时，才调用此工具。不要将其用于普通问答，不要用于“请使用某个智能体回答”这类场景，也不要因为一时未检索到合适的公共Agent就自动创建新应用。"""
            # 1.调用celery异步任务在后端创建应用
            auto_create_app.delay(name, description, account_id)

            # 2.返回成功提示
            return (
                "已调用后端异步任务创建Agent应用，并自动生成开场白和开场建议问题。"
                f"\n应用名称: {name}\n应用描述: {description}"
            )

        return create_app
