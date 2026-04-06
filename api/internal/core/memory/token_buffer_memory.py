from dataclasses import dataclass
from langchain_core.messages import AnyMessage, AIMessage, trim_messages
from sqlalchemy import desc
from internal.core.language_model.entities.model_entity import BaseLanguageModel
from internal.entity.conversation_entity import MessageStatus
from internal.model import Conversation, Message
from pkg.sqlalchemy import SQLAlchemy
import tiktoken


@dataclass
class TokenBufferMemory:
    """基于token计数的缓冲记忆组件"""
    db: SQLAlchemy  # 数据库实例
    conversation: Conversation  # 会话模型
    model_instance: BaseLanguageModel  # LLM大语言模型

    def _fallback_token_counter(self, messages: list[AnyMessage]) -> int:
        """备用token计数器，使用tiktoken库计算token数量"""
        try:
            # 使用cl100k_base编码器(GPT-4/GPT-3.5-turbo使用的编码器)
            encoding = tiktoken.get_encoding("cl100k_base")
            num_tokens = 0
            for message in messages:
                # 每条消息的基础token开销
                num_tokens += 4
                # 计算消息内容的token数
                if isinstance(message.content, str):
                    num_tokens += len(encoding.encode(message.content))
                elif isinstance(message.content, list):
                    # 处理多模态消息
                    for item in message.content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            num_tokens += len(encoding.encode(item.get("text", "")))
            # 每次对话的结束token
            num_tokens += 2
            return num_tokens
        except Exception:
            # 如果tiktoken也失败，使用简单的字符数估算(1 token ≈ 4 chars)
            total_chars = sum(
                len(msg.content) if isinstance(msg.content, str)
                else sum(len(item.get("text", "")) for item in msg.content if isinstance(item, dict) and item.get("type") == "text")
                for msg in messages
            )
            return total_chars // 4

    def get_history_prompt_messages(
            self,
            max_token_limit: int = 2000,
            message_limit: int = 10,
    ) -> list[AnyMessage]:
        """根据传递的token限制+消息条数限制获取指定会话模型的历史消息列表"""
        # 1.判断会话模型是否存在，如果不存在则直接返回空列表
        if self.conversation is None:
            return []

        # 2.查询该会话的消息列表，并且使用时间进行倒序，同时匹配答案不为空、匹配会话id、没有软删除、状态是正常
        messages = self.db.session.query(Message).filter(
            Message.conversation_id == self.conversation.id,
            Message.answer != "",
            Message.is_deleted == False,
            Message.status.in_([MessageStatus.NORMAL, MessageStatus.STOP, MessageStatus.TIMEOUT]),
        ).order_by(desc("created_at")).limit(message_limit).all()
        messages = list(reversed(messages))

        # 3.将messages转换成LangChain消息列表
        prompt_messages = []
        for message in messages:
            prompt_messages.extend([
                self.model_instance.convert_to_human_message(message.query, message.image_urls),
                AIMessage(content=message.answer),
            ])

        # 4.调用LangChain继承的trim_messages函数剪切消息列表
        # 尝试使用模型自带的token计数器，如果失败则使用备用方案
        try:
            return trim_messages(
                messages=prompt_messages,
                max_tokens=max_token_limit,
                token_counter=self.model_instance,
                strategy="last",
                start_on="human",
                end_on="ai",
            )
        except NotImplementedError:
            # 模型不支持get_num_tokens_from_messages，使用备用token计数器
            return trim_messages(
                messages=prompt_messages,
                max_tokens=max_token_limit,
                token_counter=self._fallback_token_counter,
                strategy="last",
                start_on="human",
                end_on="ai",
            )
