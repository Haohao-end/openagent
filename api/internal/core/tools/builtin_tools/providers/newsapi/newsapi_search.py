import os
import requests
from langchain_core.tools import Tool
from pydantic import BaseModel, Field
from internal.lib.helper import add_attribute


class NewsAPISearchArgsSchema(BaseModel):
    """News API搜索参数描述"""
    query: str = Field(description="需要搜索的新闻关键词")


def _search_news(query: str, **kwargs) -> str:
    """搜索新闻"""
    api_key = os.getenv("NEWSAPI_API_KEY")
    if not api_key:
        return "错误：未配置NEWSAPI_API_KEY环境变量"

    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "apiKey": api_key,
        "pageSize": kwargs.get("page_size", 5),
        "language": kwargs.get("language", "en"),
        "sortBy": "publishedAt"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "ok":
            return f"搜索失败：{data.get('message', '未知错误')}"

        articles = data.get("articles", [])
        if not articles:
            return "未找到相关新闻"

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
        return f"搜索新闻时出错：{str(e)}"


@add_attribute("args_schema", NewsAPISearchArgsSchema)
def newsapi_search(**kwargs) -> Tool:
    """News API搜索工具"""
    return Tool(
        name="newsapi_search",
        description="搜索全球新闻，返回最新的新闻文章。输入应该是新闻关键词。",
        func=lambda query: _search_news(query, **kwargs),
        args_schema=NewsAPISearchArgsSchema
    )
