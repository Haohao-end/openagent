from langchain_community.tools import ArxivQueryRun
from langchain_community.utilities import ArxivAPIWrapper
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from internal.lib.helper import add_attribute


class ArxivSearchArgsSchema(BaseModel):
    """Arxiv搜索参数描述"""
    query: str = Field(description="需要搜索的学术论文关键词或主题")


@add_attribute("args_schema", ArxivSearchArgsSchema)
def arxiv_search(**kwargs) -> BaseTool:
    """Arxiv学术论文搜索工具"""
    max_results = kwargs.get("max_results", 5)

    api_wrapper = ArxivAPIWrapper(
        top_k_results=max_results,
        doc_content_chars_max=4000
    )

    return ArxivQueryRun(
        name="arxiv_search",
        description="搜索Arxiv学术论文数据库，返回相关论文的标题、作者、摘要和链接。输入应该是学术关键词或研究主题。",
        api_wrapper=api_wrapper,
        args_schema=ArxivSearchArgsSchema
    )
