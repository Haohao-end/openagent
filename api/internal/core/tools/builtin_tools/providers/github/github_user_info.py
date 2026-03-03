import os
import requests
from langchain_core.tools import Tool
from pydantic import BaseModel, Field
from internal.lib.helper import add_attribute


class GitHubUserInfoArgsSchema(BaseModel):
    """GitHub用户信息查询参数"""
    username: str = Field(description="GitHub用户名")


def _get_user_info(username: str, **kwargs) -> str:
    """查询GitHub用户信息"""
    token = os.getenv("GITHUB_ACCESS_TOKEN")
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"

    url = f"https://api.github.com/users/{username}"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        user = response.json()

        result = (
            f"用户名：{user.get('login', 'N/A')}\n"
            f"姓名：{user.get('name', 'N/A')}\n"
            f"简介：{user.get('bio', 'N/A')}\n"
            f"公司：{user.get('company', 'N/A')}\n"
            f"位置：{user.get('location', 'N/A')}\n"
            f"邮箱：{user.get('email', 'N/A')}\n"
            f"博客：{user.get('blog', 'N/A')}\n"
            f"公开仓库：{user.get('public_repos', 0)}\n"
            f"粉丝：{user.get('followers', 0)}\n"
            f"关注：{user.get('following', 0)}\n"
            f"主页：{user.get('html_url', 'N/A')}\n"
        )
        return result
    except Exception as e:
        return f"查询用户信息时出错：{str(e)}"


@add_attribute("args_schema", GitHubUserInfoArgsSchema)
def github_user_info(**kwargs) -> Tool:
    """GitHub用户信息查询工具"""
    return Tool(
        name="github_user_info",
        description="查询GitHub用户的详细信息，包括仓库数、粉丝数等。输入应该是GitHub用户名。",
        func=lambda username: _get_user_info(username, **kwargs),
        args_schema=GitHubUserInfoArgsSchema
    )
