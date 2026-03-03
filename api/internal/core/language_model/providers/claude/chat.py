import os
from typing import Any
from pydantic import model_validator
from langchain_openai import ChatOpenAI
from internal.core.language_model.entities.model_entity import BaseLanguageModel


class Chat(ChatOpenAI, BaseLanguageModel):
    """Claude聊天模型"""

    @model_validator(mode="before")
    @classmethod
    def resolve_claude_relay_env(cls, values: Any) -> Any:
        """
        为Claude模型补充中转环境变量：
        - 优先使用显式传入参数
        - 其次使用 CLAUDE_API_KEY / CLAUDE_API_BASE
        - 最后退回 ChatOpenAI 默认读取 OPENAI_API_KEY / OPENAI_API_BASE
        """
        if not isinstance(values, dict):
            return values

        resolved = dict(values)

        if not resolved.get("api_key") and not resolved.get("openai_api_key"):
            relay_key = os.getenv("CLAUDE_API_KEY", "")
            if relay_key:
                resolved["api_key"] = relay_key

        if not resolved.get("base_url") and not resolved.get("openai_api_base"):
            relay_base = os.getenv("CLAUDE_API_BASE", "")
            if relay_base:
                resolved["base_url"] = relay_base

        return resolved
