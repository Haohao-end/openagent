from langchain_community.utilities import SerpAPIWrapper
from langchain_core.tools import Tool
from pydantic import BaseModel, Field
from internal.lib.helper import add_attribute


class SerpAPISearchArgsSchema(BaseModel):
    """SerpAPI搜索参数描述"""
    query: str = Field(description="需要检索查询的语句")


@add_attribute("args_schema", SerpAPISearchArgsSchema)
def serpapi_search(**kwargs) -> Tool:
    """SerpAPI搜索工具"""
    engine = kwargs.get("engine", "google")

    search = SerpAPIWrapper(
        params={"engine": engine}
    )

    return Tool(
        name="serpapi_search",
        description="使用SerpAPI进行搜索，支持Google、Bing、Yahoo等多个搜索引擎。输入应该是一个搜索查询语句。",
        func=search.run,
        args_schema=SerpAPISearchArgsSchema
    )
