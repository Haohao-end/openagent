import os
import requests
from langchain_core.tools import Tool
from pydantic import BaseModel, Field
from internal.lib.helper import add_attribute


class GitHubIssueSearchArgsSchema(BaseModel):
    """GitHub Issue搜索参数描述"""
    query: str = Field(description="需要搜索的Issue关键词")


def _search_issues(query: str, **kwargs) -> str:
    """搜索GitHub Issues"""
    token = os.getenv("GITHUB_ACCESS_TOKEN")
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"

    url = "https://api.github.com/search/issues"
    params = {
        "q": query,
        "sort": "updated",
        "order": "desc",
        "per_page": kwargs.get("per_page", 5)
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        items = data.get("items", [])
        if not items:
            return "未找到相关Issue"

        results = []
        for issue in items:
            results.append(
                f"标题：{issue.get('title', 'N/A')}\n"
                f"仓库：{issue.get('repository_url', 'N/A').split('/')[-2:]}\n"
                f"状态：{issue.get('state', 'N/A')}\n"
                f"创建时间：{issue.get('created_at', 'N/A')}\n"
                f"链接：{issue.get('html_url', 'N/A')}\n"
            )

        return "\n---\n".join(results)
    except Exception as e:
        return f"搜索Issue时出错：{str(e)}"


@add_attribute("args_schema", GitHubIssueSearchArgsSchema)
def github_issue_search(**kwargs) -> Tool:
    """GitHub Issue搜索工具"""
    return Tool(
        name="github_issue_search",
        description="搜索GitHub上的Issues和Pull Requests。输入应该是搜索关键词。",
        func=lambda query: _search_issues(query, **kwargs),
        args_schema=GitHubIssueSearchArgsSchema
    )
