from datetime import UTC, datetime
from typing import Any
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class CurrentTimeInput(BaseModel):
    """空输入模型 - 明确表示不需要参数"""
    # 不需要任何字段，但必须继承 BaseModel


class CurrentTimeTool(BaseTool):
    """获取当前时间的工具"""
    name: str = "current_time"
    description: str = "获取当前系统时间，返回格式为 'YYYY-MM-DD HH:MM:SS TZ'"
    args_schema: type[BaseModel] = CurrentTimeInput  # 使用具体的空模型

    def _run(self, **kwargs: Any) -> str:
        """获取当前时间"""
        # 即使有 kwargs，我们也忽略，因为不需要参数
        return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S %Z")

    async def _arun(self, **kwargs: Any) -> str:
        """异步获取当前时间"""
        return self._run(**kwargs)


def current_time(**kwargs: Any) -> BaseTool:
    """工厂函数：返回获取当前时间的 LangChain 工具"""
    return CurrentTimeTool()
