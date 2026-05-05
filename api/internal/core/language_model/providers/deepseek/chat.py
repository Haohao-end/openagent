from langchain_deepseek.chat_models import ChatDeepSeek
from internal.core.language_model.entities.model_entity import BaseLanguageModel
from internal.core.language_model.providers._defaults import apply_default_model_timeout


class Chat(ChatDeepSeek, BaseLanguageModel):
    """DeepSeek 聊天模型"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **apply_default_model_timeout(kwargs))
