import tiktoken
from typing import Tuple
from langchain_community.chat_models.moonshot import MoonshotChat
from internal.core.language_model.entities.model_entity import BaseLanguageModel
from internal.core.language_model.providers._defaults import apply_default_model_timeout


class Chat(MoonshotChat, BaseLanguageModel):
    """月之暗面聊天模型"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **apply_default_model_timeout(kwargs))

    def _get_encoding_model(self) -> Tuple[str, tiktoken.Encoding]:
        """重写月之暗面获取编码模型名字+模型函数，该类继承OpenAI，词表模型可以使用gpt-3.5-turbo防止出错"""
        # 1.将月之暗面的词表模型设置为gpt-3.5-turbo
        model = "gpt-3.5-turbo"

        # 2.返回模型名字+编码器
        return model, tiktoken.encoding_for_model(model)
