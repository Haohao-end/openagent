from datetime import datetime
import pytz
from langchain_core.tools import Tool
from pydantic import BaseModel, Field
from internal.lib.helper import add_attribute


class TimezoneConverterArgsSchema(BaseModel):
    """时区转换参数"""
    time_str: str = Field(description="时间字符串，格式：YYYY-MM-DD HH:MM:SS")
    from_timezone: str = Field(description="源时区，如：Asia/Shanghai、America/New_York、UTC")
    to_timezone: str = Field(description="目标时区，如：Asia/Shanghai、America/New_York、UTC")


def _convert_timezone(time_str: str, from_timezone: str, to_timezone: str, **kwargs) -> str:
    """转换时区"""
    try:
        # 解析时间字符串
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")

        # 设置源时区
        from_tz = pytz.timezone(from_timezone)
        dt_with_tz = from_tz.localize(dt)

        # 转换到目标时区
        to_tz = pytz.timezone(to_timezone)
        converted_dt = dt_with_tz.astimezone(to_tz)

        result = (
            f"原时间：{time_str} ({from_timezone})\n"
            f"转换后：{converted_dt.strftime('%Y-%m-%d %H:%M:%S')} ({to_timezone})\n"
            f"时差：{(converted_dt.utcoffset().total_seconds() - dt_with_tz.utcoffset().total_seconds()) / 3600:.1f}小时"
        )
        return result
    except Exception as e:
        return f"时区转换失败：{str(e)}"


@add_attribute("args_schema", TimezoneConverterArgsSchema)
def timezone_converter(**kwargs) -> Tool:
    """时区转换工具"""
    return Tool(
        name="timezone_converter",
        description="在不同时区之间转换时间。输入时间字符串、源时区和目标时区。",
        func=lambda time_str, from_timezone, to_timezone: _convert_timezone(
            time_str, from_timezone, to_timezone, **kwargs
        ),
        args_schema=TimezoneConverterArgsSchema
    )
