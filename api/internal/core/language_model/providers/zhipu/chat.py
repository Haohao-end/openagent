from langchain_community.chat_models.zhipuai import ChatZhipuAI
from internal.core.language_model.entities.model_entity import BaseLanguageModel


class Chat(ChatZhipuAI, BaseLanguageModel):
    """智谱聊天模型"""
    pass
