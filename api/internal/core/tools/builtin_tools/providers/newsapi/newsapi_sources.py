import os
import json
import requests
from langchain_core.tools import Tool
from pydantic import BaseModel, Field
from internal.lib.helper import add_attribute


class NewsAPISourcesArgsSchema(BaseModel):
    """新闻源查询参数"""
    category: str = Field(default="", description="新闻类别：business, entertainment, general, health, science, sports, technology")
    language: str = Field(default="en", description="语言代码，如en、zh等")
    country: str = Field(default="", description="国家代码，如us、cn等")


def _get_news_sources(category: str = "", language: str = "en", country: str = "", **kwargs) -> str:
    """获取新闻源列表"""
    api_key = os.getenv("NEWSAPI_API_KEY")
    if not api_key:
        return "NewsAPI未配置，请设置NEWSAPI_API_KEY环境变量"

    url = "https://newsapi.org/v2/top-headlines/sources"
    params = {
        "apiKey": api_key,
        "language": language
    }

    if category:
        params["category"] = category
    if country:
        params["country"] = country

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "ok":
            sources = data.get("sources", [])[:10]  # 只返回前10个
            results = []
            for source in sources:
                results.append(
                    f"名称：{source.get('name', 'N/A')}\n"
                    f"描述：{source.get('description', 'N/A')}\n"
                    f"类别：{source.get('category', 'N/A')}\n"
                    f"语言：{source.get('language', 'N/A')}\n"
                    f"国家：{source.get('country', 'N/A')}\n"
                    f"链接：{source.get('url', 'N/A')}\n"
                )
            return "\n---\n".join(results)
        else:
            return f"获取新闻源失败：{data.get('message', '未知错误')}"
    except Exception as e:
        return f"获取新闻源失败：{str(e)}"


@add_attribute("args_schema", NewsAPISourcesArgsSchema)
def newsapi_sources(**kwargs) -> Tool:
    """新闻源列表查询工具"""
    return Tool(
        name="newsapi_sources",
        description="获取可用的新闻源列表，可按类别、语言、国家筛选。",
        func=lambda category="", language="en", country="": _get_news_sources(
            category, language, country, **kwargs
        ),
        args_schema=NewsAPISourcesArgsSchema
    )
