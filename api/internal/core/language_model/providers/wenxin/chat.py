from typing import Any, Optional
from pydantic import Field
from langchain_community.chat_models.baidu_qianfan_endpoint import QianfanChatEndpoint

from internal.core.language_model.entities.model_entity import BaseLanguageModel


class Chat(QianfanChatEndpoint, BaseLanguageModel):
    """百度千帆聊天模型"""
    max_output_tokens: Optional[int] = Field(default=None)
    disable_search: Optional[bool] = Field(default=None)

    @property
    def _default_params(self) -> dict[str, Any]:
        """补充千帆模型扩展参数，确保可按YAML参数透传。"""
        params = super()._default_params
        if self.max_output_tokens is not None:
            params["max_output_tokens"] = self.max_output_tokens
        if self.disable_search is not None:
            params["disable_search"] = self.disable_search
        return params
