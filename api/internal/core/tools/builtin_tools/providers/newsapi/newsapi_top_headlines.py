import os
import requests
from langchain_core.tools import Tool
from pydantic import BaseModel, Field
from internal.lib.helper import add_attribute


class NewsAPITopHeadlinesArgsSchema(BaseModel):
    """News API头条新闻参数描述"""
    country: str = Field(description="国家代码，例如：us(美国)、cn(中国)、gb(英国)", default="us")


def _get_top_headlines(country: str = "us", **kwargs) -> str:
    """获取头条新闻"""
    api_key = os.getenv("NEWSAPI_API_KEY")
    if not api_key:
        return "错误：未配置NEWSAPI_API_KEY环境变量"

    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "country": country,
        "apiKey": api_key,
        "pageSize": kwargs.get("page_size", 10)
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "ok":
            return f"获取失败：{data.get('message', '未知错误')}"

        articles = data.get("articles", [])
        if not articles:
            return "未找到头条新闻"

        results = []
        for article in articles:
            results.append(
                f"标题：{article.get('title', 'N/A')}\n"
                f"来源：{article.get('source', {}).get('name', 'N/A')}\n"
                f"时间：{article.get('publishedAt', 'N/A')}\n"
                f"描述：{article.get('description', 'N/A')}\n"
                f"链接：{article.get('url', 'N/A')}\n"
            )

        return "\n---\n".join(results)
    except Exception as e:
        return f"获取头条新闻时出错：{str(e)}"


@add_attribute("args_schema", NewsAPITopHeadlinesArgsSchema)
def newsapi_top_headlines(**kwargs) -> Tool:
    """News API头条新闻工具"""
    return Tool(
        name="newsapi_top_headlines",
        description="获取指定国家的头条新闻。输入应该是国家代码（如us、cn、gb）。",
        func=lambda country: _get_top_headlines(country, **kwargs),
        args_schema=NewsAPITopHeadlinesArgsSchema
    )
