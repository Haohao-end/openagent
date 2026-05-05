from langchain_openai import OpenAI
from internal.core.language_model.entities.model_entity import BaseLanguageModel
from internal.core.language_model.providers._defaults import apply_default_model_timeout

class Completion(OpenAI, BaseLanguageModel):
    """OpenAI聊天模型基类"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **apply_default_model_timeout(kwargs))
