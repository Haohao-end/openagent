import json
from typing import Any, Type
import requests
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from internal.lib.helper import add_attribute


class URLShortenerArgsSchema(BaseModel):
    url: str = Field(description="需要缩短的长URL")


class URLShortenerTool(BaseTool):
    """短链接生成工具"""
    name: str = "url_shortener"
    description: str = "将长URL转换为短链接，方便分享"
    args_schema: Type[BaseModel] = URLShortenerArgsSchema

    def _run(self, *args: Any, **kwargs: Any) -> str:
        """生成短链接"""
        try:
            url = kwargs.get("url", "")
            if not url:
                return "请提供需要缩短的URL"

            # 使用免费的短链接API
            api_url = "https://cleanuri.com/api/v1/shorten"
            data = {"url": url}

            response = requests.post(api_url, data=data, timeout=10)
            response.raise_for_status()
            result_data = response.json()

            if "result_url" in result_data:
                result = {
                    "original_url": url,
                    "short_url": result_data["result_url"],
                    "message": "短链接生成成功"
                }
                return json.dumps(result, ensure_ascii=False)
            else:
                return f"短链接生成失败：{result_data.get('error', '未知错误')}"

        except Exception as e:
            return f"短链接生成失败：{str(e)}"


@add_attribute("args_schema", URLShortenerArgsSchema)
def url_shortener(**kwargs) -> BaseTool:
    """获取短链接生成工具"""
    return URLShortenerTool()
