from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from internal.lib.helper import add_attribute


class TavilySearchArgsSchema(BaseModel):
    """Tavily搜索参数描述"""
    query: str = Field(description="需要检索查询的语句")


@add_attribute("args_schema", TavilySearchArgsSchema)
def tavily_search(**kwargs) -> BaseTool:
    """Tavily搜索工具"""
    max_results = kwargs.get("max_results", 5)

    return TavilySearchResults(
        name="tavily_search",
        description="专为AI应用优化的搜索工具，返回高质量的搜索结果。输入应该是一个搜索查询语句。",
        max_results=max_results,
        args_schema=TavilySearchArgsSchema
    )
