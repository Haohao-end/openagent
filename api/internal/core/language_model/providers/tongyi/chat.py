from typing import Any, Optional
from pydantic import Field
from langchain_community.chat_models.tongyi import ChatTongyi
from internal.core.language_model.entities.model_entity import BaseLanguageModel


class Chat(ChatTongyi, BaseLanguageModel):
    """通义千问聊天模型"""
    temperature: Optional[float] = Field(default=None)
    max_tokens: Optional[int] = Field(default=None)
    presence_penalty: Optional[float] = Field(default=None)
    frequency_penalty: Optional[float] = Field(default=None)
    enable_search: Optional[bool] = Field(default=None)

    @property
    def _default_params(self) -> dict[str, Any]:
        """补充Tongyi常用采样参数，保持UI参数与底层API透传一致。"""
        params = super()._default_params

        if self.temperature is not None:
            params["temperature"] = self.temperature
        if self.max_tokens is not None:
            params["max_tokens"] = self.max_tokens
        if self.presence_penalty is not None:
            params["presence_penalty"] = self.presence_penalty
        if self.frequency_penalty is not None:
            params["frequency_penalty"] = self.frequency_penalty
        if self.enable_search is not None:
            params["enable_search"] = self.enable_search

        return params
