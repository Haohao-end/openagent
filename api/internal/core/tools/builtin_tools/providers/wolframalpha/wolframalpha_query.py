from langchain_community.tools.wolfram_alpha import WolframAlphaQueryRun
from langchain_community.utilities.wolfram_alpha import WolframAlphaAPIWrapper
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from internal.lib.helper import add_attribute


class WolframAlphaArgsSchema(BaseModel):
    """Wolfram Alpha查询参数描述"""
    query: str = Field(description="需要计算或查询的数学、科学问题")


@add_attribute("args_schema", WolframAlphaArgsSchema)
def wolframalpha_query(**kwargs) -> BaseTool:
    """Wolfram Alpha计算和查询工具"""
    api_wrapper = WolframAlphaAPIWrapper()

    return WolframAlphaQueryRun(
        name="wolframalpha_query",
        description="使用Wolfram Alpha进行数学计算、科学计算和知识查询。输入应该是数学表达式或科学问题。",
        api_wrapper=api_wrapper,
        args_schema=WolframAlphaArgsSchema
    )
