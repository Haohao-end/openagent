import json
from typing import Any, Type
import requests
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from internal.lib.helper import add_attribute


class IPLookupArgsSchema(BaseModel):
    ip: str = Field(default="", description="需要查询的IP地址，不填则查询当前IP")


class IPLookupTool(BaseTool):
    """IP地址查询工具"""
    name: str = "ip_lookup"
    description: str = "查询IP地址的地理位置、运营商等信息"
    args_schema: Type[BaseModel] = IPLookupArgsSchema

    def _run(self, *args: Any, **kwargs: Any) -> str:
        """调用IP查询API"""
        try:
            ip = kwargs.get("ip", "").strip()

            # 使用免费的IP查询API
            if ip:
                api_url = f"http://ip-api.com/json/{ip}?lang=zh-CN"
            else:
                api_url = "http://ip-api.com/json/?lang=zh-CN"

            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success":
                result = {
                    "ip": data.get("query", ""),
                    "country": data.get("country", ""),
                    "region": data.get("regionName", ""),
                    "city": data.get("city", ""),
                    "isp": data.get("isp", ""),
                    "org": data.get("org", ""),
                    "timezone": data.get("timezone", ""),
                    "lat": data.get("lat", ""),
                    "lon": data.get("lon", "")
                }
                return json.dumps(result, ensure_ascii=False)
            else:
                return f"IP查询失败：{data.get('message', '未知错误')}"

        except Exception as e:
            return f"IP查询失败：{str(e)}"


@add_attribute("args_schema", IPLookupArgsSchema)
def ip_lookup(**kwargs) -> BaseTool:
    """获取IP查询工具"""
    return IPLookupTool()
