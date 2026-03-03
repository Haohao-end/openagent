from langchain_deepseek.chat_models import ChatDeepSeek
from internal.core.language_model.entities.model_entity import BaseLanguageModel


class Chat(ChatDeepSeek, BaseLanguageModel):
    """DeepSeek 聊天模型"""
    pass
