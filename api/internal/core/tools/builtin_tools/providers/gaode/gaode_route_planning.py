import json
from typing import Any, Type
import requests
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import os
from internal.lib.helper import add_attribute


class GaodeRoutePlanningArgsSchema(BaseModel):
    origin: str = Field(description="起点坐标，格式：经度,纬度，例如：116.481028,39.989643")
    destination: str = Field(description="终点坐标，格式：经度,纬度，例如：116.434446,39.90816")
    strategy: int = Field(default=0, description="路径规划策略：0-速度优先（时间），1-费用优先（不走收费路段），2-距离优先，3-不走快速路")


class GaodeRoutePlanningTool(BaseTool):
    """高德地图驾车路径规划工具"""
    name: str = "gaode_route_planning"
    description: str = "根据起点和终点坐标规划驾车路线，返回路线详情、距离和预计时间"
    args_schema: Type[BaseModel] = GaodeRoutePlanningArgsSchema

    def _run(self, *args: Any, **kwargs: Any) -> str:
        """调用高德API进行路径规划"""
        try:
            gaode_api_key = os.getenv("GAODE_API_KEY")
            if not gaode_api_key:
                return "高德开放平台API未配置"

            origin = kwargs.get("origin", "")
            destination = kwargs.get("destination", "")
            strategy = kwargs.get("strategy", 0)

            api_url = "https://restapi.amap.com/v3/direction/driving"
            params = {
                "key": gaode_api_key,
                "origin": origin,
                "destination": destination,
                "strategy": strategy,
                "extensions": "all"
            }

            response = requests.get(api_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "1" and data.get("route"):
                route = data["route"]
                paths = route.get("paths", [])
                if paths:
                    path = paths[0]
                    result = {
                        "distance": f"{int(path.get('distance', 0)) / 1000:.2f}公里",
                        "duration": f"{int(path.get('duration', 0)) / 60:.0f}分钟",
                        "strategy": path.get("strategy", ""),
                        "tolls": f"{int(path.get('tolls', 0))}元",
                        "toll_distance": f"{int(path.get('toll_distance', 0)) / 1000:.2f}公里"
                    }
                    return json.dumps(result, ensure_ascii=False)

            return "路径规划失败，请检查起点和终点坐标是否正确"
        except Exception as e:
            return f"路径规划失败：{str(e)}"


@add_attribute("args_schema", GaodeRoutePlanningArgsSchema)
def gaode_route_planning(**kwargs) -> BaseTool:
    """获取高德路径规划工具"""
    return GaodeRoutePlanningTool()
