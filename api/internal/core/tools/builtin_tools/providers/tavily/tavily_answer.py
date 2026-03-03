from langchain_community.tools.tavily_search import TavilyAnswer
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from internal.lib.helper import add_attribute


class TavilyAnswerArgsSchema(BaseModel):
    """Tavily答案提取参数描述"""
    query: str = Field(description="需要回答的问题")


@add_attribute("args_schema", TavilyAnswerArgsSchema)
def tavily_answer(**kwargs) -> BaseTool:
    """Tavily答案提取工具"""
    return TavilyAnswer(
        name="tavily_answer",
        description="从搜索结果中提取答案的工具，直接返回问题的答案而不是搜索结果列表。输入应该是一个问题。",
        args_schema=TavilyAnswerArgsSchema
    )
