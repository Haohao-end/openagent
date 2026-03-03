from __future__ import annotations

import io
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any


def ns(**kwargs: Any) -> SimpleNamespace:
    """快速构造带属性访问能力的测试对象。"""
    return SimpleNamespace(**kwargs)


def utc_dt(
    year: int = 2024,
    month: int = 1,
    day: int = 1,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
) -> datetime:
    """生成 UTC datetime，便于断言时间戳转换结果。"""
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)


def upload(filename: str, content: bytes | None = None):
    """构造 Flask/Werkzeug 可识别的上传文件元组。"""
    return (io.BytesIO(content or b"test-bytes"), filename)

