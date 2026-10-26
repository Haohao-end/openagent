from langchain_community.tools import GoogleSerperRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel,Field
from langchain_community.utilities import GoogleSerperAPIWrapper
from internal.lib.helper import add_attribute
class GoogleSerperArgsSchema(BaseModel):
    """Parameters for a Google Serper web search."""
    query: str = Field(description="The search query to look up on the web.")

@add_attribute("args_schema",GoogleSerperArgsSchema)
def google_serper(**kwargs) -> BaseTool:
    """Google Serper web search."""
    return GoogleSerperRun(
        name="google_serper",
        description="Search the web with Google Serper using a search query.",
        args_schema=GoogleSerperArgsSchema,
        api_wrapper=GoogleSerperAPIWrapper()
    )
