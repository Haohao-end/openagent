import os
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy.orm import scoped_session, sessionmaker

# 在导入应用前关闭外部 tracing，避免初始化阶段产生联网副作用。
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"
os.environ.pop("LANGCHAIN_API_KEY", None)
os.environ.pop("LANGSMITH_API_KEY", None)

from app.http.app import app as _app
from internal.extension.database_extension import db as _db


@pytest.fixture(autouse=True)
def _disable_external_tracing(monkeypatch):
    """关闭外部 tracing，上报链路会干扰离线测试且没有业务价值。"""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    yield


@pytest.fixture
def app():
    """返回 Flask 应用，并开启测试模式。"""
    _app.config["TESTING"] = True
    # 测试阶段关闭鉴权，聚焦参数校验与 handler/service 逻辑。
    _app.config["LOGIN_DISABLED"] = True
    _app.config["WTF_CSRF_ENABLED"] = False
    return _app


@pytest.fixture
def client(app):
    """返回 Flask 测试客户端。"""
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def db(app):
    """每个测试使用独立事务，结束后统一回滚，确保不污染真实数据。"""
    with app.app_context():
        # 1) 基于原始连接开启事务；2) 复用该连接构造测试会话。
        connection = _db.engine.connect()
        transaction = connection.begin()
        session_factory = sessionmaker(bind=connection)
        session = scoped_session(session_factory)
        _db.session = session

        yield _db

        # 无论测试成功/失败都回滚，保证数据库状态不被测试持久化。
        transaction.rollback()
        connection.close()
        session.remove()


@pytest.fixture(autouse=True)
def _rollback_http_tests(request):
    """所有使用 `client` 夹具的 HTTP 测试自动绑定事务回滚。"""
    # 说明：部分矩阵测试使用自定义 http_client 且完整 mock service，不依赖数据库连接。
    if "client" in request.fixturenames:
        request.getfixturevalue("db")
    yield


@pytest.fixture
def login_account(monkeypatch):
    """兼容旧测试的登录态夹具，提供稳定 current_user 桩。"""
    account = SimpleNamespace(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        is_authenticated=True,
        email="tester@example.com",
        name="tester",
    )
    monkeypatch.setattr("internal.handler.app_handler.current_user", account)
    return account

