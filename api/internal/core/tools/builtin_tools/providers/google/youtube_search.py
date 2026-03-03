from langchain_community.tools import YouTubeSearchTool
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from internal.lib.helper import add_attribute


class YouTubeSearchArgsSchema(BaseModel):
    """YouTube搜索参数描述"""
    query: str = Field(description="需要搜索的视频关键词")


@add_attribute("args_schema", YouTubeSearchArgsSchema)
def youtube_search(**kwargs) -> BaseTool:
    """YouTube视频搜索工具"""
    max_results = kwargs.get("max_results", 5)

    return YouTubeSearchTool(
        name="youtube_search",
        description="搜索YouTube视频，返回相关视频的标题和链接。输入应该是视频关键词。",
        args_schema=YouTubeSearchArgsSchema
    )
