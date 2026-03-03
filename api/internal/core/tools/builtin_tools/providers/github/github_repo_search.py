import os
import requests
from langchain_core.tools import Tool
from pydantic import BaseModel, Field
from internal.lib.helper import add_attribute


class GitHubRepoSearchArgsSchema(BaseModel):
    """GitHub仓库搜索参数描述"""
    query: str = Field(description="需要搜索的仓库关键词")


def _search_repositories(query: str, **kwargs) -> str:
    """搜索GitHub仓库"""
    token = os.getenv("GITHUB_ACCESS_TOKEN")
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"

    url = "https://api.github.com/search/repositories"
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": kwargs.get("per_page", 5)
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        items = data.get("items", [])
        if not items:
            return "未找到相关仓库"

        results = []
        for repo in items:
            results.append(
                f"仓库：{repo.get('full_name', 'N/A')}\n"
                f"描述：{repo.get('description', 'N/A')}\n"
                f"Stars：{repo.get('stargazers_count', 0)}\n"
                f"语言：{repo.get('language', 'N/A')}\n"
                f"链接：{repo.get('html_url', 'N/A')}\n"
            )

        return "\n---\n".join(results)
    except Exception as e:
        return f"搜索仓库时出错：{str(e)}"


@add_attribute("args_schema", GitHubRepoSearchArgsSchema)
def github_repo_search(**kwargs) -> Tool:
    """GitHub仓库搜索工具"""
    return Tool(
        name="github_repo_search",
        description="搜索GitHub仓库，返回最受欢迎的相关仓库。输入应该是搜索关键词。",
        func=lambda query: _search_repositories(query, **kwargs),
        args_schema=GitHubRepoSearchArgsSchema
    )
