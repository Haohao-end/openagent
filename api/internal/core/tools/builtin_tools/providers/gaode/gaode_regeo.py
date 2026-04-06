import json
from typing import Any, Type
import requests
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import os
from internal.lib.helper import add_attribute


class GaodeRegeoArgsSchema(BaseModel):
    location: str = Field(description="需要转换的坐标，格式：经度,纬度，例如：116.481028,39.989643")


class GaodeRegeoTool(BaseTool):
    """高德逆地理编码工具"""
    name: str = "gaode_regeo"
    description: str = "将经纬度坐标转换为结构化地址信息"
    args_schema: Type[BaseModel] = GaodeRegeoArgsSchema

    def _run(self, *args: Any, **kwargs: Any) -> str:
        """调用高德API进行逆地理编码"""
        try:
            gaode_api_key = os.getenv("GAODE_API_KEY")
            if not gaode_api_key:
                return "高德开放平台API未配置"

            location = kwargs.get("location", "")

            api_url = "https://restapi.amap.com/v3/geocode/regeo"
            params = {
                "key": gaode_api_key,
                "location": location,
                "extensions": "all"
            }

            response = requests.get(api_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "1" and data.get("regeocode"):
                regeocode = data["regeocode"]
                addressComponent = regeocode.get("addressComponent", {})
                result = {
                    "formatted_address": regeocode.get("formatted_address", ""),
                    "province": addressComponent.get("province", ""),
                    "city": addressComponent.get("city", ""),
                    "district": addressComponent.get("district", ""),
                    "township": addressComponent.get("township", ""),
                    "street": addressComponent.get("streetNumber", {}).get("street", ""),
                    "number": addressComponent.get("streetNumber", {}).get("number", "")
                }
                return json.dumps(result, ensure_ascii=False)

            return f"坐标'{location}'逆地理编码失败"
        except Exception as e:
            return f"逆地理编码失败：{str(e)}"


@add_attribute("args_schema", GaodeRegeoArgsSchema)
def gaode_regeo(**kwargs) -> BaseTool:
    """获取高德逆地理编码工具"""
    return GaodeRegeoTool()
