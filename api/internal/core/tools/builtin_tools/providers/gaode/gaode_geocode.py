import json
from typing import Any, Type
import requests
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import os
from internal.lib.helper import add_attribute


class GaodeGeocodeArgsSchema(BaseModel):
    address: str = Field(description="需要转换的地址，例如：北京市朝阳区阜通东大街6号")
    city: str = Field(default="", description="指定查询的城市，例如：北京、上海")


class GaodeGeocodeTool(BaseTool):
    """高德地理编码工具"""
    name: str = "gaode_geocode"
    description: str = "将结构化地址转换为经纬度坐标"
    args_schema: Type[BaseModel] = GaodeGeocodeArgsSchema

    def _run(self, *args: Any, **kwargs: Any) -> str:
        """调用高德API进行地理编码"""
        try:
            gaode_api_key = os.getenv("GAODE_API_KEY")
            if not gaode_api_key:
                return "高德开放平台API未配置"

            address = kwargs.get("address", "")
            city = kwargs.get("city", "")

            api_url = "https://restapi.amap.com/v3/geocode/geo"
            params = {
                "key": gaode_api_key,
                "address": address,
                "city": city
            }

            response = requests.get(api_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "1" and data.get("geocodes"):
                geocode = data["geocodes"][0]
                result = {
                    "formatted_address": geocode.get("formatted_address", ""),
                    "location": geocode.get("location", ""),
                    "level": geocode.get("level", ""),
                    "province": geocode.get("province", ""),
                    "city": geocode.get("city", ""),
                    "district": geocode.get("district", "")
                }
                return json.dumps(result, ensure_ascii=False)

            return f"地址'{address}'地理编码失败"
        except Exception as e:
            return f"地理编码失败：{str(e)}"


@add_attribute("args_schema", GaodeGeocodeArgsSchema)
def gaode_geocode(**kwargs) -> BaseTool:
    """获取高德地理编码工具"""
    return GaodeGeocodeTool()
