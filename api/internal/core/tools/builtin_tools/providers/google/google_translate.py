import os
from langchain_core.tools import Tool
from pydantic import BaseModel, Field
from internal.lib.helper import add_attribute


class GoogleTranslateArgsSchema(BaseModel):
    """Google翻译参数"""
    text: str = Field(description="需要翻译的文本")
    target_lang: str = Field(default="zh-CN", description="目标语言代码，如zh-CN、en、ja等")
    source_lang: str = Field(default="auto", description="源语言代码，auto为自动检测")


def _translate_text(text: str, target_lang: str = "zh-CN", source_lang: str = "auto", **kwargs) -> str:
    """使用Google翻译API翻译文本"""
    try:
        from googletrans import Translator
        translator = Translator()

        src = None if source_lang == "auto" else source_lang
        result = translator.translate(text, dest=target_lang, src=src)

        return f"原文：{text}\n译文：{result.text}\n源语言：{result.src}\n目标语言：{result.dest}"
    except ImportError:
        return "Google翻译功能需要安装googletrans库：pip install googletrans==3.1.0a0"
    except Exception as e:
        return f"翻译失败：{str(e)}"


@add_attribute("args_schema", GoogleTranslateArgsSchema)
def google_translate(**kwargs) -> Tool:
    """Google翻译工具"""
    return Tool(
        name="google_translate",
        description="使用Google翻译API进行文本翻译，支持自动检测源语言。",
        func=lambda text, target_lang="zh-CN", source_lang="auto": _translate_text(
            text, target_lang, source_lang, **kwargs
        ),
        args_schema=GoogleTranslateArgsSchema
    )
