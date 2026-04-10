import logging
import types
from pathlib import Path

import pytest

from internal.exception import NotFoundException
from internal.server.http import Http
from pkg.response import HttpCode


class _FakeConf:
    CELERY = {"broker_url": "redis://example"}
    CORS_ALLOW_ORIGINS = ["https://ui.example.com"]
    CORS_SUPPORTS_CREDENTIALS = True


class _WildcardCorsConf:
    CELERY = {"broker_url": "redis://example"}
    CORS_ALLOW_ORIGINS = ["*"]
    CORS_SUPPORTS_CREDENTIALS = True


class _FakeDB:
    def __init__(self):
        self.init_calls = []

    def init_app(self, app):
        self.init_calls.append(app)


class _FakeWeaviate:
    def __init__(self):
        self.init_calls = []

    def init_app(self, app):
        self.init_calls.append(app)


class _FakeMigrate:
    def __init__(self):
        self.init_calls = []

    def init_app(self, app, db, directory):
        self.init_calls.append((app, db, directory))


class _FakeLoginManager:
    def __init__(self):
        self.init_calls = []
        self.request_loader_fn = None

    def init_app(self, app):
        self.init_calls.append(app)

    def request_loader(self, fn):
        self.request_loader_fn = fn


class _FakeMail:
    def __init__(self):
        self.init_calls = []

    def init_app(self, app):
        self.init_calls.append(app)


class _FakeMiddleware:
    @staticmethod
    def request_loader(_request):
        return None


class _FakeRouter:
    def __init__(self):
        self.register_calls = []

    def register_router(self, app):
        self.register_calls.append(app)


def _new_http_app(monkeypatch):
    cors_calls = []
    ext_calls = []
    socketio_calls = []

    monkeypatch.setattr(
        "internal.server.http.CORS",
        lambda app, resources: cors_calls.append((app, resources)),
    )
    monkeypatch.setattr(
        "internal.server.http.logging_extension.init_app",
        lambda app: ext_calls.append(("logging", app)),
    )
    monkeypatch.setattr(
        "internal.server.http.redis_extension.init_app",
        lambda app: ext_calls.append(("redis", app)),
    )
    monkeypatch.setattr(
        "internal.server.http.celery_extension.init_app",
        lambda app: ext_calls.append(("celery", app)),
    )
    monkeypatch.setattr(
        "internal.server.http.init_socketio",
        lambda app: socketio_calls.append(app),
    )

    db = _FakeDB()
    weaviate = _FakeWeaviate()
    migrate = _FakeMigrate()
    login_manager = _FakeLoginManager()
    mail = _FakeMail()
    middleware = _FakeMiddleware()
    router = _FakeRouter()

    app = Http(
        "test-http",
        conf=_FakeConf(),
        db=db,
        weaviate=weaviate,
        migrate=migrate,
        login_manager=login_manager,
        mail=mail,
        middleware=middleware,
        router=router,
    )
    return app, db, weaviate, migrate, login_manager, mail, router, cors_calls, ext_calls, socketio_calls


def test_http_init_should_wire_extensions_middleware_and_router(monkeypatch):
    app, db, weaviate, migrate, login_manager, mail, router, cors_calls, ext_calls, socketio_calls = _new_http_app(monkeypatch)

    assert app.config["CELERY"] == {"broker_url": "redis://example"}
    assert db.init_calls == [app]
    assert weaviate.init_calls == [app]
    assert migrate.init_calls == [(app, db, "internal/migration")]
    assert login_manager.init_calls == [app]
    assert mail.init_calls == [app]
    assert login_manager.request_loader_fn == _FakeMiddleware.request_loader
    assert router.register_calls == [app]
    assert len(cors_calls) == 1
    assert cors_calls[0][1]["/*"]["origins"] == ["https://ui.example.com"]
    assert cors_calls[0][1]["/*"]["supports_credentials"] is True
    assert [name for name, _ in ext_calls] == ["logging", "redis", "celery"]
    assert socketio_calls == [app]


def test_http_init_should_fallback_to_localhost_when_wildcard_conflicts_with_credentials(monkeypatch):
    cors_calls = []

    monkeypatch.setattr(
        "internal.server.http.CORS",
        lambda app, resources: cors_calls.append((app, resources)),
    )
    monkeypatch.setattr("internal.server.http.logging_extension.init_app", lambda app: None)
    monkeypatch.setattr("internal.server.http.redis_extension.init_app", lambda app: None)
    monkeypatch.setattr("internal.server.http.celery_extension.init_app", lambda app: None)
    monkeypatch.setattr("internal.server.http.init_socketio", lambda app: None)

    Http(
        "test-http",
        conf=_WildcardCorsConf(),
        db=_FakeDB(),
        weaviate=_FakeWeaviate(),
        migrate=_FakeMigrate(),
        login_manager=_FakeLoginManager(),
        mail=_FakeMail(),
        middleware=_FakeMiddleware(),
        router=_FakeRouter(),
    )

    assert cors_calls[0][1]["/*"]["origins"] == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    assert cors_calls[0][1]["/*"]["supports_credentials"] is True


def test_http_error_handler_should_return_custom_exception_payload(monkeypatch):
    app, *_ = _new_http_app(monkeypatch)

    with app.app_context():
        response, status = app._register_error_handler(NotFoundException("missing", {"detail": "x"}))

    assert status == 200
    payload = response.get_json()
    assert payload["code"] == HttpCode.NOT_FOUND.value
    assert payload["message"] == "missing"
    assert payload["data"] == {"detail": "x"}


def test_http_error_handler_should_reraise_non_custom_error_when_debug(monkeypatch):
    app, *_ = _new_http_app(monkeypatch)
    app.debug = True
    monkeypatch.delenv("FLASK_ENV", raising=False)

    with app.app_context():
        with pytest.raises(RuntimeError, match="boom"):
            app._register_error_handler(RuntimeError("boom"))


def test_http_error_handler_should_reraise_non_custom_error_when_development_env(monkeypatch):
    app, *_ = _new_http_app(monkeypatch)
    app.debug = False
    monkeypatch.setenv("FLASK_ENV", "development")

    with app.app_context():
        with pytest.raises(RuntimeError, match="boom"):
            app._register_error_handler(RuntimeError("boom"))


def test_http_error_handler_should_return_fail_payload_in_production(monkeypatch):
    app, *_ = _new_http_app(monkeypatch)
    app.debug = False
    monkeypatch.setenv("FLASK_ENV", "production")

    with app.app_context():
        response, status = app._register_error_handler(RuntimeError("boom"))

    assert status == 200
    payload = response.get_json()
    assert payload["code"] == HttpCode.FAIL.value
    assert payload["message"] == "服务器内部错误"
    assert payload["data"] == {}


def test_app_module_main_should_invoke_http_run(monkeypatch):
    run_calls = []

    class _FakeHttp:
        def __init__(self, *_args, **_kwargs):
            self.extensions = {"celery": "fake-celery-app"}

        def run(self, **kwargs):
            run_calls.append(kwargs)

    class _FakeSQLAlchemy:
        pass

    class _FakeFlaskWeaviate:
        pass

    class _FakeMigrate:
        pass

    class _FakeLoginManager:
        pass

    class _FakeMail:
        pass

    class _FakeMiddleware:
        pass

    class _FakeRouter:
        pass

    class _FakeInjector:
        def __init__(self, mapping):
            self.mapping = mapping

        def get(self, cls):
            return self.mapping[cls]

    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.load_dotenv = lambda: None

    fake_flask_migrate = types.ModuleType("flask_migrate")
    fake_flask_migrate.Migrate = _FakeMigrate

    fake_config = types.ModuleType("config")
    fake_config.Config = type("Config", (), {})

    fake_internal_router = types.ModuleType("internal.router")
    fake_internal_router.Router = _FakeRouter

    fake_internal_server = types.ModuleType("internal.server")
    fake_internal_server.Http = _FakeHttp

    fake_pkg_sqlalchemy = types.ModuleType("pkg.sqlalchemy")
    fake_pkg_sqlalchemy.SQLAlchemy = _FakeSQLAlchemy

    fake_flask_weaviate = types.ModuleType("flask_weaviate")
    fake_flask_weaviate.FlaskWeaviate = _FakeFlaskWeaviate

    fake_flask_login = types.ModuleType("flask_login")
    fake_flask_login.LoginManager = _FakeLoginManager

    fake_flask_mail = types.ModuleType("flask_mail")
    fake_flask_mail.Mail = _FakeMail

    fake_internal_middleware = types.ModuleType("internal.middleware")
    fake_internal_middleware.Middleware = _FakeMiddleware

    fake_app_http_module = types.ModuleType("app.http.module")
    fake_app_http_module.injector = _FakeInjector(
        {
            _FakeSQLAlchemy: object(),
            _FakeFlaskWeaviate: object(),
            _FakeMigrate: object(),
            _FakeLoginManager: object(),
            _FakeMail: object(),
            _FakeMiddleware: object(),
            _FakeRouter: object(),
        }
    )

    monkeypatch.setitem(__import__("sys").modules, "dotenv", fake_dotenv)
    monkeypatch.setitem(__import__("sys").modules, "flask_migrate", fake_flask_migrate)
    monkeypatch.setitem(__import__("sys").modules, "config", fake_config)
    monkeypatch.setitem(__import__("sys").modules, "internal.router", fake_internal_router)
    monkeypatch.setitem(__import__("sys").modules, "internal.server", fake_internal_server)
    monkeypatch.setitem(__import__("sys").modules, "pkg.sqlalchemy", fake_pkg_sqlalchemy)
    monkeypatch.setitem(__import__("sys").modules, "flask_weaviate", fake_flask_weaviate)
    monkeypatch.setitem(__import__("sys").modules, "flask_login", fake_flask_login)
    monkeypatch.setitem(__import__("sys").modules, "flask_mail", fake_flask_mail)
    monkeypatch.setitem(__import__("sys").modules, "internal.middleware", fake_internal_middleware)
    monkeypatch.setitem(__import__("sys").modules, "app.http.module", fake_app_http_module)

    app_file = Path(__file__).resolve().parents[3] / "app" / "http" / "app.py"
    globals_dict = {
        "__name__": "__main__",
        "__package__": "app.http",
        "__file__": str(app_file),
    }

    # 通过 `__main__` 方式执行模块，精确覆盖 app/http/app.py 的入口分支。
    exec(compile(app_file.read_text(encoding="utf-8"), str(app_file), "exec"), globals_dict)

    assert globals_dict["celery"] == "fake-celery-app"
    assert run_calls == [{"debug": True, "port": 5001}]
