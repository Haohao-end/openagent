import os
import json
import logging
from typing import Any, Type

import requests
from internal.lib.helper import add_attribute
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)
_DEFAULT_GAODE_TIMEOUT_SECONDS = 10
_NO_PROXY = {"http": None, "https": None}


class GaodeWeatherArgsSchema(BaseModel):
    city: str = Field(description="需要查询天气预报的目标城市，例如：广州")


class GaodeWeatherTool(BaseTool):
    """根据传入的城市名查询天气"""
    name:str = "gaode_weather"
    description:str = "当你想查询天气或者与天气相关的问题时可以使用的工具"
    args_schema: Type[BaseModel] = GaodeWeatherArgsSchema

    @staticmethod
    def _get_timeout() -> int:
        raw = (os.getenv("GAODE_API_TIMEOUT_SECONDS") or "").strip()
        if not raw:
            return _DEFAULT_GAODE_TIMEOUT_SECONDS
        try:
            value = int(raw)
        except ValueError:
            return _DEFAULT_GAODE_TIMEOUT_SECONDS
        return value if value > 0 else _DEFAULT_GAODE_TIMEOUT_SECONDS

    @staticmethod
    def _is_success(payload: dict[str, Any]) -> bool:
        return payload.get("status") == "1" or payload.get("info") == "OK"

    def _run(self, *args: Any, **kwargs: Any) -> str:
        """根据传入的城市名称运行调用api获取城市对应的天气预报信息"""
        city = str(kwargs.get("city", "")).strip()
        session = None
        if not city:
            return "获取天气预报信息失败：缺少城市参数"

        try:
            # 1.获取高德API秘钥，如果没有创建的话，则抛出错误
            gaode_api_key = os.getenv("GAODE_API_KEY")
            if not gaode_api_key:
                return "高德开放平台API未配置"

            # 2.从参数中获取city城市名字
            api_domain = "https://restapi.amap.com/v3"
            session = requests.session()
            timeout = self._get_timeout()

            # 3.发起行政区域编码查询，根据city获取ad_code
            city_response = session.request(
                method="GET",
                url=f"{api_domain}/config/district",
                params={
                    "key": gaode_api_key,
                    "keywords": city,
                    "subdistrict": 0,
                },
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=timeout,
                proxies=_NO_PROXY,
            )
            city_response.raise_for_status()
            city_data = city_response.json()
            if not self._is_success(city_data):
                logger.warning("高德行政区查询失败: city=%s payload=%s", city, city_data)
                return f"获取{city}天气预报信息失败：行政区查询失败"

            districts = city_data.get("districts") or []
            if not districts or not districts[0].get("adcode"):
                logger.warning("高德行政区查询无结果: city=%s payload=%s", city, city_data)
                return f"获取{city}天气预报信息失败：未找到对应城市编码"

            ad_code = districts[0]["adcode"]

            # 4.根据得到的ad_code调用天气预报API接口，获取天气信息
            weather_response = session.request(
                method="GET",
                url=f"{api_domain}/weather/weatherInfo",
                params={
                    "key": gaode_api_key,
                    "city": ad_code,
                    "extensions": "all",
                },
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=timeout,
                proxies=_NO_PROXY,
            )
            weather_response.raise_for_status()
            weather_data = weather_response.json()
            if self._is_success(weather_data):
                # 5.返回最后的结果字符串
                return json.dumps(weather_data, ensure_ascii=False)

            logger.warning(
                "高德天气查询失败: city=%s ad_code=%s payload=%s",
                city,
                ad_code,
                weather_data,
            )
            return f"获取{city}天气预报信息失败：天气接口返回异常"
        except requests.Timeout:
            logger.warning("高德天气查询超时: city=%s timeout=%s", city, self._get_timeout())
            return f"获取{city}天气预报信息失败：请求超时"
        except requests.RequestException:
            logger.warning("高德天气查询请求异常: city=%s", city)
            return f"获取{city}天气预报信息失败：网络请求异常"
        except (ValueError, KeyError, IndexError, TypeError) as e:
            logger.warning("高德天气查询响应解析异常: city=%s error=%s", city, e)
            return f"获取{city}天气预报信息失败：响应解析异常"
        except Exception as e:
            logger.exception("高德天气查询未知异常: city=%s", city)
            return f"获取{city}天气预报信息失败：{type(e).__name__}"
        finally:
            try:
                if session is not None:
                    session.close()
            except Exception:
                pass


@add_attribute("args_schema",GaodeWeatherArgsSchema)
def gaode_weather(**kwargs) -> BaseTool:
    """获取高德天气预报查询工具"""
    return GaodeWeatherTool()
