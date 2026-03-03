from langchain_community.utilities import WikipediaAPIWrapper
from langchain_core.tools import BaseTool
from langchain_community.tools.wikipedia.tool import WikipediaQueryInput,WikipediaQueryRun
from internal.lib.helper import add_attribute
@add_attribute("args_schema",WikipediaQueryInput)
def wikipedia_search(**kwargs) -> BaseTool:
    """返回维基百科搜索工具"""
    return WikipediaQueryRun(
        api_wrapper=WikipediaAPIWrapper()
    )