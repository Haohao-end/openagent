from langchain_core.tools import Tool
from pydantic import BaseModel, Field
from internal.lib.helper import add_attribute


class WikipediaSummaryArgsSchema(BaseModel):
    """维基百科摘要查询参数"""
    query: str = Field(description="需要查询的词条名称")
    lang: str = Field(default="zh", description="语言代码，zh为中文，en为英文")


def _get_wikipedia_summary(query: str, lang: str = "zh", **kwargs) -> str:
    """获取维基百科摘要"""
    try:
        import wikipedia
        wikipedia.set_lang(lang)

        # 搜索相关词条
        search_results = wikipedia.search(query, results=1)
        if not search_results:
            return f"未找到关于'{query}'的维基百科词条"

        # 获取摘要
        page_title = search_results[0]
        summary = wikipedia.summary(page_title, sentences=5)
        page = wikipedia.page(page_title)

        result = (
            f"标题：{page.title}\n"
            f"摘要：{summary}\n"
            f"链接：{page.url}\n"
        )
        return result
    except ImportError:
        return "维基百科功能需要安装wikipedia库：pip install wikipedia"
    except Exception as e:
        return f"查询维基百科失败：{str(e)}"


@add_attribute("args_schema", WikipediaSummaryArgsSchema)
def wikipedia_summary(**kwargs) -> Tool:
    """维基百科摘要查询工具"""
    return Tool(
        name="wikipedia_summary",
        description="获取维基百科词条的摘要信息和链接。输入应该是词条名称。",
        func=lambda query, lang="zh": _get_wikipedia_summary(query, lang, **kwargs),
        args_schema=WikipediaSummaryArgsSchema
    )
