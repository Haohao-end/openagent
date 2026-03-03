from langchain_community.tools import OpenWeatherMapQueryRun
from langchain_community.utilities import OpenWeatherMapAPIWrapper
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from internal.lib.helper import add_attribute


class OpenWeatherMapArgsSchema(BaseModel):
    """OpenWeatherMap天气查询参数描述"""
    location: str = Field(description="需要查询天气的城市名称，例如：Beijing, London, New York")


@add_attribute("args_schema", OpenWeatherMapArgsSchema)
def openweathermap_weather(**kwargs) -> BaseTool:
    """OpenWeatherMap天气查询工具"""
    api_wrapper = OpenWeatherMapAPIWrapper()

    return OpenWeatherMapQueryRun(
        name="openweathermap_weather",
        description="查询全球任意城市的实时天气信息，包括温度、湿度、风速等。输入应该是城市名称。",
        api_wrapper=api_wrapper,
        args_schema=OpenWeatherMapArgsSchema
    )
