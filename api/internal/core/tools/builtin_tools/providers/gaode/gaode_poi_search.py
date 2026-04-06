import json
from typing import Any, Type
import requests
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import os
from internal.lib.helper import add_attribute


class GaodePOISearchArgsSchema(BaseModel):
    keywords: str = Field(description="搜索关键词，例如：肯德基、酒店、景点")
    city: str = Field(default="", description="城市名称，例如：北京、上海。不填则全国搜索")
    types: str = Field(default="", description="POI类型编码，例如：050000（餐饮服务）、060000（购物服务）")


class GaodePOISearchTool(BaseTool):
    """高德地图POI搜索工具"""
    name: str = "gaode_poi_search"
    description: str = "搜索指定城市或全国范围内的地点信息，如餐厅、酒店、景点、商场等"
    args_schema: Type[BaseModel] = GaodePOISearchArgsSchema

    def _run(self, *args: Any, **kwargs: Any) -> str:
        """调用高德API进行POI搜索"""
        try:
            gaode_api_key = os.getenv("GAODE_API_KEY")
            if not gaode_api_key:
                return "高德开放平台API未配置"

            keywords = kwargs.get("keywords", "")
            city = kwargs.get("city", "")
            types = kwargs.get("types", "")

            api_url = "https://restapi.amap.com/v3/place/text"
            params = {
                "key": gaode_api_key,
                "keywords": keywords,
                "city": city,
                "types": types,
                "offset": 10,
                "extensions": "all"
            }

            response = requests.get(api_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "1" and data.get("pois"):
                pois = data["pois"][:5]  # 只返回前5个结果
                results = []
                for poi in pois:
                    result = {
                        "name": poi.get("name", ""),
                        "type": poi.get("type", ""),
                        "address": poi.get("address", ""),
                        "location": poi.get("location", ""),
                        "tel": poi.get("tel", ""),
                        "distance": poi.get("distance", "")
                    }
                    results.append(result)
                return json.dumps(results, ensure_ascii=False)

            return f"未找到关于'{keywords}'的地点信息"
        except Exception as e:
            return f"POI搜索失败：{str(e)}"


@add_attribute("args_schema", GaodePOISearchArgsSchema)
def gaode_poi_search(**kwargs) -> BaseTool:
    """获取高德POI搜索工具"""
    return GaodePOISearchTool()
