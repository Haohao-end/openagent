import json
from dataclasses import dataclass
from typing import Generator
from uuid import UUID
from injector import inject
from langchain_core.output_parsers import StrOutputParser
from langchain_core.output_parsers.transform import BaseCumulativeTransformOutputParser
from langchain_core.prompts import ChatPromptTemplate
from internal.core.language_model.providers.deepseek.chat import Chat
from internal.entity.ai_entity import (
    OPTIMIZE_PROMPT_TEMPLATE,
    OPENAPI_SCHEMA_ASSISTANT_PROMPT,
    PYTHON_CODE_ASSISTANT_PROMPT,
)
from internal.exception import ForbiddenException
from internal.model import Account, Message
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from .conversation_service import ConversationService
from ..core.language_model.entities.model_entity import ModelFeature


class PythonMarkdownOutputParser(BaseCumulativeTransformOutputParser[str]):
    """Python 代码输出解析器（流式增量模式，保留模型原始输出）。"""

    diff: bool = True

    @property
    def _type(self) -> str:
        return "python_markdown_output"

    def _diff(self, prev: str | None, next: str) -> str:
        previous = prev or ""
        if next.startswith(previous):
            return next[len(previous):]
        return next

    def parse(self, text: str) -> str:
        return text


@inject
@dataclass
class AIService(BaseService):
    """AI服务"""
    db: SQLAlchemy
    conversation_service: ConversationService

    def generate_suggested_questions_from_message_id(self, message_id: UUID, account: Account) -> list[str]:
        """根据传递的消息id+账号生成建议问题列表"""
        # 1.查询消息并校验权限信息
        message = self.get(Message, message_id)
        if not message or message.created_by != account.id:
            raise ForbiddenException("该条消息不存在或无权限")

        # 2.如果消息已有建议问题，直接返回
        if message.suggested_questions and len(message.suggested_questions) > 0:
            return message.suggested_questions

        # 3.构建对话历史列表
        histories = f"Human: {message.query}\nAI: {message.answer}"

        # 4.调用服务生成建议问题
        suggested_questions = self.conversation_service.generate_suggested_questions(histories)

        # 5.存储建议问题到数据库
        self.update(message, suggested_questions=suggested_questions)

        return suggested_questions

    @classmethod
    def optimize_prompt(cls, prompt: str) -> Generator[str, None, None]:
        """根据传递的prompt进行优化生成"""
        # 1.构建优化prompt的提示词模板
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", OPTIMIZE_PROMPT_TEMPLATE),
            ("human", "{prompt}")
        ])

        # 2.构建LLM
        llm = Chat(
            model="deepseek-chat",
            temperature=0.8,
            features=[ModelFeature.TOOL_CALL.value, ModelFeature.AGENT_THOUGHT.value],
            metadata={},
        )

        # 3.组装优化链
        optimize_chain = prompt_template | llm | StrOutputParser()

        # 4.调用链并流式事件返回
        for optimize_prompt in optimize_chain.stream({"prompt": prompt}):
            # 5.组装响应数据
            data = {"optimize_prompt": optimize_prompt}
            yield f"event: optimize_prompt\ndata: {json.dumps(data)}\n\n"

    @classmethod
    def code_assistant_chat(cls, question: str) -> Generator[str, None, None]:
        """代码助手聊天 - 流式输出"""
        # 1.构建提示词模板
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", PYTHON_CODE_ASSISTANT_PROMPT),
            ("human", "{question}")
        ])

        # 2.构建 LLM
        llm = Chat(
            model="deepseek-chat",
            temperature=0.7,
            features=[ModelFeature.TOOL_CALL.value],
            metadata={},
        )

        # 3.组装链（使用 Python 代码输出解析器）
        chain = prompt_template | llm | PythonMarkdownOutputParser()

        # 4.流式调用并返回
        for chunk in chain.stream({"question": question}):
            if not chunk:
                continue
            # 5.组装 SSE 响应数据
            data = {"content": chunk}
            yield f"event: message\ndata: {json.dumps(data)}\n\n"

    @classmethod
    def openapi_schema_assistant_chat(cls, question: str) -> Generator[str, None, None]:
        """OpenAPI Schema 助手聊天 - 流式输出"""
        system_prompt = OPENAPI_SCHEMA_ASSISTANT_PROMPT.replace("{", "{{").replace("}", "}}")

        # 1.构建提示词模板
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{question}")
        ])

        # 2.构建 LLM
        llm = Chat(
            model="deepseek-chat",
            temperature=0.2,
            features=[ModelFeature.TOOL_CALL.value],
            metadata={},
        )

        # 3.组装链
        chain = prompt_template | llm | StrOutputParser()

        # 4.流式调用并返回
        for chunk in chain.stream({"question": question}):
            if not chunk:
                continue

            # 5.组装 SSE 响应数据
            data = {"content": chunk}
            yield f"event: message\ndata: {json.dumps(data)}\n\n"
