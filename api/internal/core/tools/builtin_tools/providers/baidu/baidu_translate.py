import json
import hashlib
import random
from typing import Any, Type
import requests
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import os
from internal.lib.helper import add_attribute


class BaiduTranslateArgsSchema(BaseModel):
    text: str = Field(description="需要翻译的文本内容")
    from_lang: str = Field(default="auto", description="源语言，auto为自动检测，zh为中文，en为英文，jp为日语等")
    to_lang: str = Field(default="zh", description="目标语言，zh为中文，en为英文，jp为日语等")


class BaiduTranslateTool(BaseTool):
    """百度翻译工具"""
    name: str = "baidu_translate"
    description: str = "使用百度翻译API进行文本翻译，支持多种语言互译"
    args_schema: Type[BaseModel] = BaiduTranslateArgsSchema

    def _run(self, *args: Any, **kwargs: Any) -> str:
        """调用百度翻译API"""
        try:
            app_id = os.getenv("BAIDU_TRANSLATE_APP_ID")
            secret_key = os.getenv("BAIDU_TRANSLATE_SECRET_KEY")

            if not app_id or not secret_key:
                return "百度翻译API未配置，请设置BAIDU_TRANSLATE_APP_ID和BAIDU_TRANSLATE_SECRET_KEY"

            text = kwargs.get("text", "")
            from_lang = kwargs.get("from_lang", "auto")
            to_lang = kwargs.get("to_lang", "zh")

            # 生成签名
            salt = random.randint(32768, 65536)
            sign_str = f"{app_id}{text}{salt}{secret_key}"
            sign = hashlib.md5(sign_str.encode()).hexdigest()

            api_url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
            params = {
                "q": text,
                "from": from_lang,
                "to": to_lang,
                "appid": app_id,
                "salt": salt,
                "sign": sign
            }

            response = requests.get(api_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "trans_result" in data:
                results = data["trans_result"]
                translations = [item["dst"] for item in results]
                return "\n".join(translations)
            elif "error_code" in data:
                error_msg = data.get("error_msg", "未知错误")
                return f"翻译失败：{error_msg}"

            return "翻译失败"
        except Exception as e:
            return f"翻译失败：{str(e)}"


@add_attribute("args_schema", BaiduTranslateArgsSchema)
def baidu_translate(**kwargs) -> BaseTool:
    """获取百度翻译工具"""
    return BaiduTranslateTool()
