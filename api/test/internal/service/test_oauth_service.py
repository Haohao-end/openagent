from contextlib import contextmanager
import json
from types import SimpleNamespace
from uuid import uuid4
import base64

from flask import Flask
import pytest
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

from internal.exception import (
    FailException,
    ForbiddenException,
    NotFoundException,
    ValidateErrorException,
)
from internal.entity.ai_entity import OPENAPI_SCHEMA_ASSISTANT_PROMPT, PYTHON_CODE_ASSISTANT_PROMPT
from internal.model import Account, AccountOAuth, ApiKey, ApiTool, ApiToolProvider
from internal.service.account_service import AccountService as _AccountService
from internal.service.ai_service import AIService, PythonMarkdownOutputParser
from internal.service.api_key_service import ApiKeyService
from internal.service.api_tool_service import ApiToolService as _ApiToolService
from internal.service.builtin_tool_service import BuiltinToolService
from internal.service.oauth_service import OAuthService


class _QueryStub:
    """可复用的最小查询桩，支持链式调用和删除统计。"""

    def __init__(self, *, one_or_none_result=None, all_result=None):
        self._one_or_none_result = one_or_none_result
        self._all_result = all_result if all_result is not None else []
        self.deleted = False

    def filter(self, *_args, **_kwargs):
        return self

    def filter_by(self, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def one_or_none(self):
        return self._one_or_none_result

    def all(self):
        return self._all_result

    def delete(self):
        self.deleted = True


class _SessionStub:
    def __init__(self, query_map: dict):
        self._query_map = query_map
        self.deleted_entities = []

    def query(self, model):
        result = self._query_map.get(model, _QueryStub())
        if isinstance(result, list):
            return result.pop(0)
        return result

    def delete(self, entity):
        self.deleted_entities.append(entity)


class _DBStub:
    def __init__(self, session):
        self.session = session

    @contextmanager
    def auto_commit(self):
        yield


def _new_account_service(**kwargs):
    kwargs.setdefault("email_service", SimpleNamespace())
    return _AccountService(**kwargs)


def _new_api_tool_service(**kwargs):
    kwargs.setdefault("icon_generator_service", SimpleNamespace())
    return _ApiToolService(**kwargs)


class _AppTemplateStub:
    """模拟应用模板实体，只实现 目标方法 依赖的字段。"""

    language_model_config = {"provider": "openai", "model": "gpt-4o-mini"}

    def model_dump(self, include=None):
        payload = {
            "name": "助手模板",
            "icon": "https://a.com/app.png",
            "description": "desc",
            "dialog_round": 5,
            "preset_prompt": "你是助手",
            "tools": [],
            "workflows": [],
            "retrieval_config": {},
            "long_term_memory": {"enable": True},
            "opening_statement": "hello",
            "opening_questions": ["q1"],
            "speech_to_text": {"enable": False},
            "text_to_speech": {"enable": False},
            "review_config": {"enable": False},
            "suggested_after_answer": {"enable": True},
        }
        if include is None:
            return payload
        return {key: payload[key] for key in include}


class _AppSessionStub:
    """最小化模拟 SQLAlchemy session.add/flush，确保模型会拿到 id。"""

    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        if self.added and getattr(self.added[-1], "id", None) is None:
            self.added[-1].id = uuid4()


class _AppDBStub:
    def __init__(self):
        self.session = _AppSessionStub()

    @contextmanager
    def auto_commit(self):
        yield


class TestOAuthService:
    def _build_service(self, account_service=None) -> OAuthService:
        return OAuthService(
            db=SimpleNamespace(),
            jwt_service=SimpleNamespace(generate_token=lambda _payload: "oauth-jwt"),
            account_service=account_service or SimpleNamespace(),
        )

    def test_resolve_redirect_uri_should_use_origin_when_in_allowlist(self, monkeypatch):
        app = Flask(__name__)
        app.config["OAUTH_ALLOWED_ORIGINS"] = ["http://localhost:5173"]
        monkeypatch.setenv("GITHUB_REDIRECT_URI", "https://ui.example.com/auth/authorize/github")
        with app.test_request_context(
            "/oauth/github",
            headers={"Origin": "http://localhost:5173"},
        ):
            uri = OAuthService._resolve_redirect_uri("github", "GITHUB_REDIRECT_URI")

        assert uri == "http://localhost:5173/auth/authorize/github"

    def test_resolve_redirect_uri_should_fallback_to_env_when_origin_not_allowed(self, monkeypatch):
        app = Flask(__name__)
        app.config["OAUTH_ALLOWED_ORIGINS"] = ["https://allowed.example.com"]
        monkeypatch.setenv("GITHUB_REDIRECT_URI", "https://ui.example.com/auth/authorize/github")
        with app.test_request_context(
            "/oauth/github",
            headers={"Origin": "http://localhost:5173"},
        ):
            uri = OAuthService._resolve_redirect_uri("github", "GITHUB_REDIRECT_URI")

        assert uri == "https://ui.example.com/auth/authorize/github"

    def test_resolve_redirect_uri_should_fallback_to_env_when_origin_blank(self, monkeypatch):
        app = Flask(__name__)
        monkeypatch.setenv("GITHUB_REDIRECT_URI", "https://ui.example.com/auth/authorize/github")
        with app.test_request_context(
            "/oauth/github",
            headers={"Origin": "   "},
        ):
            uri = OAuthService._resolve_redirect_uri("github", "GITHUB_REDIRECT_URI")

        assert uri == "https://ui.example.com/auth/authorize/github"

    def test_allowed_origins_should_parse_comma_separated_string_from_config(self, monkeypatch):
        app = Flask(__name__)
        app.config["OAUTH_ALLOWED_ORIGINS"] = "https://a.example.com, https://b.example.com/ "
        monkeypatch.delenv("OAUTH_ALLOWED_ORIGINS", raising=False)
        monkeypatch.setattr("internal.service.oauth_service.has_request_context", lambda: True)

        with app.app_context():
            origins = OAuthService._allowed_origins()

        assert origins == {"https://a.example.com", "https://b.example.com"}

    def test_allowed_origins_should_fallback_to_env_when_configured_string_is_blank(self, monkeypatch):
        app = Flask(__name__)
        app.config["OAUTH_ALLOWED_ORIGINS"] = "   "
        monkeypatch.setenv("OAUTH_ALLOWED_ORIGINS", "https://env-only.example.com")

        with app.test_request_context("/oauth/github"):
            origins = OAuthService._allowed_origins()

        assert origins == {"https://env-only.example.com"}

    def test_allowed_origins_should_parse_from_env_without_request_context(self, monkeypatch):
        monkeypatch.setenv("OAUTH_ALLOWED_ORIGINS", "https://env-a.example.com,https://env-b.example.com/")

        origins = OAuthService._allowed_origins()

        assert origins == {"https://env-a.example.com", "https://env-b.example.com"}

    def test_allowed_origins_should_return_empty_set_when_env_missing(self, monkeypatch):
        monkeypatch.delenv("OAUTH_ALLOWED_ORIGINS", raising=False)

        assert OAuthService._allowed_origins() == set()

    def test_get_oauth_by_provider_name_should_raise_when_provider_absent(self, monkeypatch):
        monkeypatch.setattr(
            OAuthService,
            "get_all_oauth",
            classmethod(lambda cls: {"github": object()}),
        )

        with pytest.raises(NotFoundException):
            OAuthService.get_oauth_by_provider_name("google")

    def test_get_oauth_by_provider_name_should_return_oauth_instance(self, monkeypatch):
        oauth_instance = object()
        monkeypatch.setattr(
            OAuthService,
            "get_all_oauth",
            classmethod(lambda cls: {"google": oauth_instance}),
        )

        result = OAuthService.get_oauth_by_provider_name("google")

        assert result is oauth_instance

    def test_get_all_oauth_should_build_github_and_google_clients(self, monkeypatch):
        monkeypatch.setenv("GITHUB_CLIENT_ID", "github-id")
        monkeypatch.setenv("GITHUB_CLIENT_SECRET", "github-secret")
        monkeypatch.setenv("GITHUB_REDIRECT_URI", "https://ui.example.com/auth/authorize/github")
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-secret")
        monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://ui.example.com/auth/authorize/google")

        oauth_map = OAuthService.get_all_oauth()

        assert set(oauth_map.keys()) == {"github", "google"}
        assert oauth_map["github"].client_id == "github-id"
        assert oauth_map["google"].client_secret == "google-secret"
        assert oauth_map["github"].redirect_uri.endswith("/auth/authorize/github")
        assert oauth_map["google"].redirect_uri.endswith("/auth/authorize/google")

    def test_oauth_login_should_create_account_and_oauth_binding(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        oauth_user = SimpleNamespace(id="openid-1", email="demo@example.com", name="demo")
        oauth = SimpleNamespace(
            get_access_token=lambda _code: "oauth-token",
            get_user_info=lambda _token: oauth_user,
        )
        account_service = SimpleNamespace(
            get_account_oauth_by_provider_name_and_openid=lambda *_args, **_kwargs: None,
            get_account_by_email=lambda _email: None,
            create_account=lambda **_kwargs: account,
            get_account=lambda _id: account,
        )
        service = self._build_service(account_service=account_service)

        monkeypatch.setattr(service, "get_oauth_by_provider_name", lambda _name: oauth)
        create_calls = []
        monkeypatch.setattr(
            service,
            "create",
            lambda model, **kwargs: create_calls.append((model, kwargs))
            or SimpleNamespace(account_id=account.id),
        )
        update_calls = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: update_calls.append((target, kwargs)),
        )

        app = Flask(__name__)
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": "10.0.0.8"}):
            result = service.oauth_login("github", "code-1")

        assert result["access_token"] == "oauth-jwt"
        assert len(create_calls) == 1
        assert create_calls[0][1]["provider"] == "github"
        assert create_calls[0][1]["openid"] == "openid-1"
        assert update_calls[0][1]["last_login_ip"] == "10.0.0.8"
        assert update_calls[1][1]["encrypted_token"] == "oauth-token"

    def test_oauth_login_should_use_existing_binding_account(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        account_oauth = SimpleNamespace(account_id=account.id)
        oauth_user = SimpleNamespace(id="openid-2", email="bound@example.com", name="bound")
        oauth = SimpleNamespace(
            get_access_token=lambda _code: "oauth-token-existing",
            get_user_info=lambda _token: oauth_user,
        )
        account_service = SimpleNamespace(
            get_account_oauth_by_provider_name_and_openid=lambda *_args, **_kwargs: account_oauth,
            get_account_by_email=lambda _email: (_ for _ in ()).throw(AssertionError("should not query email")),
            create_account=lambda **_kwargs: (_ for _ in ()).throw(AssertionError("should not create account")),
            get_account=lambda _id: account,
        )
        service = self._build_service(account_service=account_service)
        monkeypatch.setattr(service, "get_oauth_by_provider_name", lambda _name: oauth)
        monkeypatch.setattr(
            service,
            "create",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not create oauth binding")),
        )

        update_calls = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: update_calls.append((target, kwargs)),
        )

        app = Flask(__name__)
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": "10.0.0.9"}):
            result = service.oauth_login("github", "code-existing")

        assert result["access_token"] == "oauth-jwt"
        assert update_calls[0][0] is account
        assert update_calls[1][0] is account_oauth
        assert update_calls[0][1]["last_login_ip"] == "10.0.0.9"
        assert update_calls[1][1]["encrypted_token"] == "oauth-token-existing"

    def test_oauth_login_should_bind_oauth_for_existing_email_account(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        oauth_user = SimpleNamespace(id="openid-3", email="existing@example.com", name="existing")
        oauth = SimpleNamespace(
            get_access_token=lambda _code: "oauth-token-existing-email",
            get_user_info=lambda _token: oauth_user,
        )
        account_service = SimpleNamespace(
            get_account_oauth_by_provider_name_and_openid=lambda *_args, **_kwargs: None,
            get_account_by_email=lambda _email: account,
            create_account=lambda **_kwargs: (_ for _ in ()).throw(AssertionError("should not create account")),
            get_account=lambda _id: account,
        )
        service = self._build_service(account_service=account_service)
        monkeypatch.setattr(service, "get_oauth_by_provider_name", lambda _name: oauth)
        create_calls = []
        monkeypatch.setattr(
            service,
            "create",
            lambda model, **kwargs: create_calls.append((model, kwargs))
            or SimpleNamespace(account_id=account.id),
        )
        update_calls = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: update_calls.append((target, kwargs)),
        )

        app = Flask(__name__)
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": "10.0.0.10"}):
            result = service.oauth_login("github", "code-existing-email")

        assert result["access_token"] == "oauth-jwt"
        assert len(create_calls) == 1
        assert create_calls[0][1]["account_id"] == account.id
        assert update_calls[0][0] is account
