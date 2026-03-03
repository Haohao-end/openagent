from langchain_google_genai import ChatGoogleGenerativeAI
from internal.core.language_model.entities.model_entity import BaseLanguageModel


class Chat(ChatGoogleGenerativeAI, BaseLanguageModel):
    """Google Gemini聊天模型"""
    pass
