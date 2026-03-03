from __future__ import annotations

from typing import Callable

import pytest
from flask import Flask


@pytest.fixture(scope="session")
def schema_flask_app() -> Flask:
    """提供 schema 表单校验所需的最小 Flask 应用上下文。"""
    app = Flask("schema-tests")
    app.config.update(
        TESTING=True,
        SECRET_KEY="schema-test-secret",
        WTF_CSRF_ENABLED=False,
    )
    return app


@pytest.fixture
def form_request(schema_flask_app: Flask) -> Callable:
    """
    统一创建请求上下文。

    说明：
    1. FlaskForm 默认从 request 中读取数据，这里统一封装，避免每个测试重复样板代码。
    2. 支持 form-data/json/multipart，便于覆盖 upload 与 JSON 关键词校验等分支。
    """

    def _build(
        *,
        data: dict | None = None,
        json: dict | list | None = None,
        method: str = "POST",
        path: str = "/",
        content_type: str | None = None,
    ):
        kwargs: dict = {"method": method}
        if data is not None:
            kwargs["data"] = data
        if json is not None:
            kwargs["json"] = json
        if content_type is not None:
            kwargs["content_type"] = content_type
        return schema_flask_app.test_request_context(path, **kwargs)

    return _build
