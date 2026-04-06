import logging
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from internal.extension import celery_extension, logging_extension, redis_extension, socketio_extension


def test_celery_extension_should_bind_flask_context_and_mount_extension(monkeypatch):
    class _BaseTask:
        def run(self, *args, **kwargs):
            return {"args": args, "kwargs": kwargs}

    class _FakeCelery:
        def __init__(self, name, task_cls):
            self.name = name
            self.task_cls = task_cls
            self.config_obj = None
            self.default_called = False

        def config_from_object(self, obj):
            self.config_obj = obj

        def set_default(self):
            self.default_called = True

    class _FakeApp:
        def __init__(self):
            self.name = "demo-app"
            self.config = {"CELERY": {"broker_url": "redis://example"}}
            self.extensions = {}
            self.context_entered = 0

        @contextmanager
        def app_context(self):
            self.context_entered += 1
            yield

    monkeypatch.setattr(celery_extension, "Task", _BaseTask)
    monkeypatch.setattr(celery_extension, "Celery", _FakeCelery)
    app = _FakeApp()

    celery_extension.init_app(app)

    celery_app = app.extensions["celery"]
    task_cls = celery_app.task_cls
    task_instance = task_cls()
    task_instance.run = lambda *args, **kwargs: {"args": args, "kwargs": kwargs}
    result = task_instance(1, x=2)

    assert isinstance(celery_app, _FakeCelery)
    assert celery_app.config_obj == {"broker_url": "redis://example"}
    assert celery_app.default_called is True
    assert result == {"args": (1,), "kwargs": {"x": 2}}
    assert app.context_entered == 1


class _FakeLogger:
    def __init__(self):
        self.level = logging.WARNING
        self.levels = []
        self.handlers = []

    def setLevel(self, level):
        self.level = level
        self.levels.append(level)

    def addHandler(self, handler):
        self.handlers.append(handler)

    def removeHandler(self, handler):
        if handler in self.handlers:
            self.handlers.remove(handler)


class _FakeHandler:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.level = None
        self.formatter = None

    def setLevel(self, level):
        self.level = level

    def setFormatter(self, formatter):
        self.formatter = formatter


@pytest.mark.parametrize(
    "debug, flask_env, folder_exists, expected_level, expected_handlers, expect_makedirs",
    [
        (True, "production", False, logging.DEBUG, 2, True),
        (False, "development", True, logging.DEBUG, 2, False),
        (False, "production", True, logging.WARNING, 1, False),
    ],
)
def test_logging_extension_should_cover_debug_dev_and_prod_branches(
    monkeypatch,
    debug,
    flask_env,
    folder_exists,
    expected_level,
    expected_handlers,
    expect_makedirs,
):
    fake_logger = _FakeLogger()
    makedirs_calls = []

    monkeypatch.setattr(logging_extension.logging, "getLogger", lambda: fake_logger)
    monkeypatch.setattr(
        logging_extension,
        "ConcurrentTimedRotatingFileHandler",
        lambda *args, **kwargs: _FakeHandler(*args, **kwargs),
    )
    monkeypatch.setattr(
        logging_extension.logging,
        "StreamHandler",
        lambda: _FakeHandler(),
    )
    monkeypatch.setattr(logging_extension.os.path, "exists", lambda _path: folder_exists)
    monkeypatch.setattr(logging_extension.os, "makedirs", lambda path: makedirs_calls.append(path))
    monkeypatch.setattr(logging_extension.os, "getcwd", lambda: "/tmp/project")
    monkeypatch.setattr(
        logging_extension.os,
        "getenv",
        lambda key: flask_env if key == "FLASK_ENV" else None,
    )

    app = SimpleNamespace(debug=debug)
    logging_extension.init_app(app)

    assert fake_logger.levels[-1] == expected_level
    assert len(fake_logger.handlers) == expected_handlers
    if expect_makedirs:
        assert makedirs_calls == ["/tmp/project/storage/log"]
    else:
        assert makedirs_calls == []


@pytest.mark.parametrize(
    "use_ssl, expected_class",
    [
        (False, redis_extension.Connection),
        (True, redis_extension.SSLConnection),
    ],
)
def test_redis_extension_should_select_connection_class_by_ssl_flag(
    monkeypatch, use_ssl, expected_class
):
    pool_calls = []
    fake_redis_client = SimpleNamespace(connection_pool=None)

    monkeypatch.setattr(
        redis_extension.redis,
        "ConnectionPool",
        lambda **kwargs: pool_calls.append(kwargs) or kwargs,
    )
    monkeypatch.setattr(redis_extension, "redis_client", fake_redis_client)

    app = SimpleNamespace(
        config={
            "REDIS_USE_SSL": use_ssl,
            "REDIS_HOST": "redis.local",
            "REDIS_PORT": 6380,
            "REDIS_USERNAME": "user",
            "REDIS_PASSWORD": "pwd",
            "REDIS_DB": 2,
        },
        extensions={},
    )

    redis_extension.init_app(app)

    assert pool_calls[0]["connection_class"] is expected_class
    assert fake_redis_client.connection_pool == pool_calls[0]
    assert app.extensions["redis"] is fake_redis_client


def test_socketio_extension_should_align_cors_settings_with_http_defaults(monkeypatch):
    register_calls = []
    socketio_calls = []

    class _FakeSocketIO:
        def __init__(self, app, **kwargs):
            self.app = app
            self.kwargs = kwargs
            socketio_calls.append((app, kwargs))

    monkeypatch.setattr("flask_socketio.SocketIO", _FakeSocketIO)
    monkeypatch.setattr(
        "internal.handler.websocket_handler.register_socketio_handlers",
        lambda socketio: register_calls.append(socketio),
    )

    app = SimpleNamespace(
        config={
            "CORS_ALLOW_ORIGINS": ["*"],
            "CORS_SUPPORTS_CREDENTIALS": True,
            "REDIS_URL": "redis://example",
        }
    )

    socketio = socketio_extension.init_socketio(app)

    assert socketio_calls[0][1]["cors_allowed_origins"] == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    assert socketio_calls[0][1]["cors_credentials"] is True
    assert socketio_calls[0][1]["message_queue"] == "redis://example"
    assert register_calls == [socketio]
