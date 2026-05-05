import os
from typing import Any
from pydantic import model_validator
from langchain_openai import ChatOpenAI
from internal.core.language_model.entities.model_entity import BaseLanguageModel
from internal.core.language_model.providers._defaults import apply_default_model_timeout


class Chat(ChatOpenAI, BaseLanguageModel):
    """xAI Grok聊天模型（OpenAI兼容接口）"""

    @model_validator(mode="before")
    @classmethod
    def resolve_grok_env(cls, values: Any) -> Any:
        """
        Grok默认环境变量优先级：
        1. 显式传参 api_key/base_url
        2. GROK_API_KEY/GROK_API_BASE
        3. XAI_API_KEY/XAI_API_BASE
        4. ChatOpenAI默认 OPENAI_API_KEY/OPENAI_API_BASE
        """
        if not isinstance(values, dict):
            return values

        resolved = dict(values)

        if not resolved.get("api_key") and not resolved.get("openai_api_key"):
            key = os.getenv("GROK_API_KEY", "") or os.getenv("XAI_API_KEY", "")
            if key:
                resolved["api_key"] = key

        if not resolved.get("base_url") and not resolved.get("openai_api_base"):
            base = (
                os.getenv("GROK_API_BASE", "")
                or os.getenv("XAI_API_BASE", "")
                or "https://api.x.ai/v1"
            )
            if base:
                resolved["base_url"] = base

        apply_default_model_timeout(resolved)
        return resolved
