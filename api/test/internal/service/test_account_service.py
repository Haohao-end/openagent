from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import json
from types import SimpleNamespace
from uuid import uuid4
import base64

from flask import Flask
import pytest
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy.exc import SQLAlchemyError

from internal.exception import (
    FailException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
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
        self.added_entities = []

    def query(self, model):
        result = self._query_map.get(model, _QueryStub())
        if isinstance(result, list):
            return result.pop(0)
        return result

    def delete(self, entity):
        self.deleted_entities.append(entity)

    def add(self, entity):
        self.added_entities.append(entity)


class _DBStub:
    def __init__(self, session):
        self.session = session

    @contextmanager
    def auto_commit(self):
        yield


class _RedisStub:
    def __init__(self, *, exists_keys=None, incr_values=None):
        self.exists_keys = set(exists_keys or [])
        self.incr_values = dict(incr_values or {})
        self.expire_calls = []
        self.setex_calls = []
        self.delete_calls = []
        self.values = {}

    def exists(self, key):
        return 1 if key in self.exists_keys else 0

    def incr(self, key):
        next_value = self.incr_values.get(key, 0) + 1
        self.incr_values[key] = next_value
        return next_value

    def expire(self, key, seconds):
        self.expire_calls.append((key, seconds))
        return True

    def setex(self, key, ttl, value):
        self.setex_calls.append((key, ttl, value))
        self.exists_keys.add(key)
        self.values[key] = value.encode() if isinstance(value, str) else value
        return True

    def delete(self, *keys):
        self.delete_calls.extend(keys)
        for key in keys:
            self.exists_keys.discard(key)
            self.values.pop(key, None)
        return len(keys)

    def get(self, key):
        return self.values.get(key)


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


class TestAccountService:
    def _build_service(self) -> _AccountService:
        return _new_account_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            jwt_service=SimpleNamespace(generate_token=lambda _payload: "jwt-token"),
        )

    def test_update_password_should_store_base64_hash_and_salt(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())

        monkeypatch.setattr(
            "internal.service.account_service.secrets.token_bytes",
            lambda _size: b"\x01" * 16,
        )
        monkeypatch.setattr(
            "internal.service.account_service.hash_password",
            lambda _password, _salt: b"\x02" * 32,
        )
        updates = []
        monkeypatch.setattr(
            service,
            "update_account",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.update_password("pass-123", account)

        assert result is account
        assert len(updates) == 1
        payload = updates[0][1]
        assert payload["password_salt"] == base64.b64encode(b"\x01" * 16).decode()
        assert payload["password"] == base64.b64encode(b"\x02" * 32).decode()

    def test_change_password_should_require_current_password_for_existing_password(self):
        service = self._build_service()
        account = SimpleNamespace(
            id=uuid4(),
            is_password_set=True,
            password="hashed",
            password_salt="salt",
        )

        with pytest.raises(FailException) as exc_info:
            service.change_password(account, "", "NewPass123")

        assert "请输入当前密码" in str(exc_info.value)

    def test_change_password_should_validate_current_password_before_update(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(
            id=uuid4(),
            is_password_set=True,
            password="hashed",
            password_salt="salt",
        )
        monkeypatch.setattr(
            "internal.service.account_service.compare_password",
            lambda *_args, **_kwargs: True,
        )
        update_calls = []
        monkeypatch.setattr(
            service,
            "update_password",
            lambda password, target: update_calls.append((password, target)) or target,
        )

        result = service.change_password(account, "OldPass123", "NewPass123")

        assert result is account
        assert update_calls == [("NewPass123", account)]

    def test_issue_credential_should_create_session_and_embed_jti(self, monkeypatch):
        jwt_payload = {}
        session = _SessionStub({})
        service = _new_account_service(
            db=_DBStub(session),
            jwt_service=SimpleNamespace(
                generate_token=lambda payload: jwt_payload.update(payload) or "jwt-token"
            ),
        )
        account = SimpleNamespace(id=uuid4())
        update_calls = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: update_calls.append((target, kwargs)) or target,
        )

        app = Flask(__name__)
        with app.test_request_context(
            "/",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/123.0"},
            environ_base={"REMOTE_ADDR": "10.0.0.5"},
        ):
            result = service.issue_credential(account)

        assert result["access_token"] == "jwt-token"
        assert result["expire_at"] > 0
        assert jwt_payload["sub"] == str(account.id)
        assert jwt_payload["iss"] == "llmops"
        assert "jti" in jwt_payload
        assert update_calls[0][1]["last_login_ip"] == "10.0.0.5"
        assert update_calls[1][0] is account

    def test_issue_credential_should_send_login_alert_when_ip_unusual(self, monkeypatch):
        alert_calls = []
        service = _new_account_service(
            db=_DBStub(_SessionStub({})),
            jwt_service=SimpleNamespace(generate_token=lambda _payload: "jwt-token"),
            email_service=SimpleNamespace(
                send_login_alert_email=lambda email, **kwargs: alert_calls.append((email, kwargs))
            ),
        )
        account = SimpleNamespace(id=uuid4(), name="tester", email="tester@example.com")
        new_session_id = uuid4()

        monkeypatch.setattr(
            service,
            "create_account_session",
            lambda _account: SimpleNamespace(id=new_session_id, account_id=account.id),
        )
        monkeypatch.setattr(service, "update", lambda target, **kwargs: target)
        monkeypatch.setattr(
            service,
            "get_account_sessions_by_account_id",
            lambda _account_id: [
                SimpleNamespace(id=uuid4(), last_login_ip="10.0.0.4"),
            ],
        )

        app = Flask(__name__)
        with app.test_request_context(
            "/",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/123.0"},
            environ_base={"REMOTE_ADDR": "10.0.0.5"},
        ):
            service.issue_credential(account)

        assert len(alert_calls) == 1
        assert alert_calls[0][0] == "tester@example.com"
        assert alert_calls[0][1]["account_name"] == "tester"
        assert alert_calls[0][1]["client_ip"] == "10.0.0.5"
        assert alert_calls[0][1]["user_agent"] == "Mozilla/5.0 (Windows NT 10.0) Chrome/123.0"
        assert isinstance(alert_calls[0][1]["login_at"], datetime)

    def test_issue_credential_should_fallback_to_legacy_token_when_session_storage_unavailable(self, monkeypatch):
        jwt_payload = {}
        service = _new_account_service(
            db=_DBStub(_SessionStub({})),
            jwt_service=SimpleNamespace(
                generate_token=lambda payload: jwt_payload.update(payload) or "jwt-token"
            ),
        )
        account = SimpleNamespace(id=uuid4())
        update_calls = []

        def _raise_session_error(_account):
            raise SQLAlchemyError("account_session unavailable")

        monkeypatch.setattr(service, "create_account_session", _raise_session_error)
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: update_calls.append((target, kwargs)) or target,
        )

        app = Flask(__name__)
        with app.test_request_context(
            "/",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/123.0"},
            environ_base={"REMOTE_ADDR": "10.0.0.5"},
        ):
            result = service.issue_credential(account)

        assert result["access_token"] == "jwt-token"
        assert jwt_payload["sub"] == str(account.id)
        assert "jti" not in jwt_payload
        assert len(update_calls) == 1
        assert update_calls[0][0] is account

    def test_validate_access_session_should_return_none_when_session_storage_unavailable(self):
        service = self._build_service()

        def _raise_session_error(_session_id):
            raise SQLAlchemyError("account_session unavailable")

        service.get_account_session = _raise_session_error

        assert service.validate_access_session({"sub": "account-id-1", "jti": "session-1"}) is None

    def test_validate_access_session_should_return_none_for_legacy_token(self):
        service = self._build_service()

        assert service.validate_access_session({"sub": "account-id-1"}) is None

    def test_validate_access_session_should_raise_when_session_missing(self):
        service = self._build_service()
        service.get_account_session = lambda _session_id: None

        with pytest.raises(UnauthorizedException):
            service.validate_access_session({"sub": "account-id-1", "jti": "session-1"})

    def test_resolve_ip_location_should_return_local_network_label_without_remote_lookup(self, monkeypatch):
        service = self._build_service()
        monkeypatch.setattr(
            "internal.service.account_service.requests.get",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not query remote api")),
        )

        assert service.resolve_ip_location("127.0.0.1") == "本机"
        assert service.resolve_ip_location("192.168.1.8") == "局域网"

    def test_resolve_ip_location_should_cache_public_lookup_result(self, monkeypatch):
        redis_stub = _RedisStub()
        monkeypatch.setattr("internal.service.account_service.redis_client", redis_stub)
        service = self._build_service()
        request_calls = []

        class _ResponseStub:
            @staticmethod
            def raise_for_status():
                return None

            @staticmethod
            def json():
                return {
                    "status": "success",
                    "country": "中国",
                    "regionName": "上海市",
                    "city": "上海市",
                }

        def _fake_get(url, timeout):
            request_calls.append((url, timeout))
            return _ResponseStub()

        monkeypatch.setattr("internal.service.account_service.requests.get", _fake_get)

        assert service.resolve_ip_location("1.2.3.4") == "上海市"
        assert service.resolve_ip_location("1.2.3.4") == "上海市"
        assert len(request_calls) == 1

    def test_format_ip_location_should_include_district_when_provider_returns_it(self):
        service = self._build_service()

        location = service._format_ip_location({
            "country": "中国",
            "regionName": "北京市",
            "city": "北京市",
            "district": "朝阳区",
        })

        assert location == "北京市朝阳区"

    def test_get_account_sessions_should_filter_revoked_and_mark_current(self, monkeypatch):
        service = self._build_service()
        now = datetime.now(UTC).replace(tzinfo=None)
        account = SimpleNamespace(id=uuid4())
        monkeypatch.setattr(service, "resolve_ip_location", lambda ip: "上海市" if ip == "10.0.0.5" else "")
        monkeypatch.setattr(
            service,
            "get_account_sessions_by_account_id",
            lambda _account_id: [
                SimpleNamespace(
                    id="session-current",
                    user_agent="Mozilla/5.0 (Windows NT 10.0) Chrome/123.0",
                    last_login_ip="10.0.0.5",
                    created_at=now,
                    last_active_at=now,
                    expires_at=now + timedelta(days=1),
                    revoked_at=None,
                ),
                SimpleNamespace(
                    id="session-revoked",
                    user_agent="Mozilla/5.0",
                    last_login_ip="10.0.0.6",
                    created_at=now,
                    last_active_at=now,
                    expires_at=now + timedelta(days=1),
                    revoked_at=now,
                ),
            ],
        )

        sessions = service.get_account_sessions(account, "session-current")

        assert len(sessions) == 1
        assert sessions[0]["current"] is True
        assert sessions[0]["legacy"] is False
        assert sessions[0]["device_name"] == "Windows · Chrome"
        assert sessions[0]["location"] == "上海市"

    def test_get_account_sessions_should_include_legacy_current_device_when_token_is_old(self, monkeypatch):
        service = self._build_service()
        now = datetime.now(UTC).replace(tzinfo=None)
        account = SimpleNamespace(
            id=uuid4(),
            last_login_at=now,
            last_login_ip="10.0.0.5",
            created_at=now - timedelta(days=3),
        )
        monkeypatch.setattr(service, "resolve_ip_location", lambda ip: "上海市" if ip == "10.0.0.5" else "")
        monkeypatch.setattr(service, "get_account_sessions_by_account_id", lambda _account_id: [])

        app = Flask(__name__)
        with app.test_request_context(
            "/",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/123.0"},
            environ_base={"REMOTE_ADDR": "10.0.0.5"},
        ):
            sessions = service.get_account_sessions(account, None)

        assert len(sessions) == 1
        assert sessions[0]["current"] is True
        assert sessions[0]["legacy"] is True
        assert sessions[0]["ip"] == "10.0.0.5"
        assert sessions[0]["location"] == "上海市"

    def test_get_account_sessions_should_fallback_to_legacy_device_when_session_storage_unavailable(self, monkeypatch):
        service = self._build_service()
        now = datetime.now(UTC).replace(tzinfo=None)
        account = SimpleNamespace(
            id=uuid4(),
            last_login_at=now,
            last_login_ip="10.0.0.5",
            created_at=now - timedelta(days=10),
        )
        monkeypatch.setattr(service, "resolve_ip_location", lambda ip: "上海市" if ip == "10.0.0.5" else "")

        def _raise_session_error(_account_id):
            raise SQLAlchemyError("account_session unavailable")

        monkeypatch.setattr(service, "get_account_sessions_by_account_id", _raise_session_error)

        app = Flask(__name__)
        with app.test_request_context(
            "/",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/123.0"},
            environ_base={"REMOTE_ADDR": "10.0.0.5"},
        ):
            sessions = service.get_account_sessions(account, None)

        assert len(sessions) == 1
        assert sessions[0]["legacy"] is True
        assert sessions[0]["current"] is True
        assert sessions[0]["location"] == "上海市"

    def test_get_account_login_history_should_mark_unusual_ip_and_status(self, monkeypatch):
        service = self._build_service()
        now = datetime.now(UTC).replace(tzinfo=None)
        account = SimpleNamespace(id=uuid4())
        monkeypatch.setattr(
            service,
            "resolve_ip_location",
            lambda ip: "上海市" if ip == "10.0.0.5" else "北京市" if ip == "10.0.0.9" else "",
        )
        monkeypatch.setattr(
            service,
            "get_account_sessions_by_account_id",
            lambda _account_id: [
                SimpleNamespace(
                    id="session-old",
                    user_agent="Mozilla/5.0 (Windows NT 10.0) Chrome/123.0",
                    last_login_ip="10.0.0.5",
                    created_at=now - timedelta(days=3),
                    last_active_at=now - timedelta(days=3),
                    expires_at=now + timedelta(days=10),
                    revoked_at=None,
                ),
                SimpleNamespace(
                    id="session-revoked",
                    user_agent="Mozilla/5.0 (Macintosh) Safari/605.1",
                    last_login_ip="10.0.0.9",
                    created_at=now - timedelta(days=2),
                    last_active_at=now - timedelta(days=2),
                    expires_at=now + timedelta(days=8),
                    revoked_at=now - timedelta(days=1),
                ),
                SimpleNamespace(
                    id="session-current",
                    user_agent="Mozilla/5.0 (Macintosh) Safari/605.1",
                    last_login_ip="10.0.0.9",
                    created_at=now - timedelta(days=1),
                    last_active_at=now - timedelta(hours=1),
                    expires_at=now - timedelta(minutes=1),
                    revoked_at=None,
                ),
            ],
        )

        history_payload = service.get_account_login_history(account, "session-current")
        history = history_payload["history"]

        assert history_payload["total"] == 3
        assert [item["id"] for item in history] == [
            "session-current",
            "session-revoked",
            "session-old",
        ]
        assert history[0]["current"] is True
        assert history[0]["legacy"] is False
        assert history[0]["status"] == "expired"
        assert history[0]["location"] == "北京市"
        assert history[1]["status"] == "revoked"
        assert history[1]["unusual_ip"] is True
        assert history[1]["location"] == "北京市"
        assert history[2]["status"] == "active"
        assert history[2]["unusual_ip"] is False
        assert history[2]["location"] == "上海市"

    def test_get_account_login_history_should_support_legacy_fallback_filter_and_pagination(self, monkeypatch):
        service = self._build_service()
        now = datetime.now(UTC).replace(tzinfo=None)
        account = SimpleNamespace(
            id=uuid4(),
            last_login_at=now,
            last_login_ip="10.0.0.5",
            created_at=now - timedelta(days=10),
        )
        monkeypatch.setattr(service, "resolve_ip_location", lambda ip: "上海市" if ip == "10.0.0.5" else "")
        monkeypatch.setattr(service, "get_account_sessions_by_account_id", lambda _account_id: [])

        app = Flask(__name__)
        with app.test_request_context(
            "/",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/123.0"},
            environ_base={"REMOTE_ADDR": "10.0.0.5"},
        ):
            history_payload = service.get_account_login_history(
                account,
                None,
                status="legacy",
                search="上海市",
                current_page=1,
                page_size=1,
            )

        assert history_payload["total"] == 1
        assert history_payload["current_page"] == 1
        assert history_payload["page_size"] == 1
        assert len(history_payload["history"]) == 1
        assert history_payload["history"][0]["legacy"] is True
        assert history_payload["history"][0]["status"] == "legacy"
        assert history_payload["history"][0]["location"] == "上海市"

    def test_get_account_login_history_should_fallback_to_legacy_history_when_session_storage_unavailable(self, monkeypatch):
        service = self._build_service()
        now = datetime.now(UTC).replace(tzinfo=None)
        account = SimpleNamespace(
            id=uuid4(),
            last_login_at=now,
            last_login_ip="10.0.0.5",
            created_at=now - timedelta(days=10),
        )
        monkeypatch.setattr(service, "resolve_ip_location", lambda ip: "上海市" if ip == "10.0.0.5" else "")

        def _raise_session_error(_account_id):
            raise SQLAlchemyError("account_session unavailable")

        monkeypatch.setattr(service, "get_account_sessions_by_account_id", _raise_session_error)

        app = Flask(__name__)
        with app.test_request_context(
            "/",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/123.0"},
            environ_base={"REMOTE_ADDR": "10.0.0.5"},
        ):
            history_payload = service.get_account_login_history(account, None)

        assert history_payload["total"] == 1
        assert history_payload["history"][0]["legacy"] is True
        assert history_payload["history"][0]["status"] == "legacy"
        assert history_payload["history"][0]["location"] == "上海市"

    def test_revoke_account_session_should_block_current_device_by_default(self):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        current_session = SimpleNamespace(id="session-1", account_id=account.id, revoked_at=None)
        service.get_account_session = lambda _session_id: current_session

        with pytest.raises(FailException):
            service.revoke_account_session(account, "session-1", current_session_id="session-1")

    def test_revoke_other_account_sessions_should_require_current_session(self):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())

        with pytest.raises(FailException):
            service.revoke_other_account_sessions(account, None)

    def test_get_account_oauth_bindings_should_expand_supported_providers(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        monkeypatch.setattr(
            service,
            "get_account_oauths_by_account_id",
            lambda _account_id: [
                SimpleNamespace(provider="github", created_at=None),
            ],
        )

        bindings = service.get_account_oauth_bindings(account)

        assert bindings[0]["provider"] == "github"
        assert bindings[0]["bound"] is True
        assert bindings[1]["provider"] == "google"
        assert bindings[1]["bound"] is False

    def test_get_account_should_delegate_to_base_get(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: account)

        result = service.get_account(account.id)

        assert result is account

    def test_get_account_oauth_should_return_binding_record(self):
        oauth_binding = SimpleNamespace(id=uuid4(), provider="github", openid="openid-1")
        service = _new_account_service(
            db=SimpleNamespace(
                session=_SessionStub(
                    {
                        AccountOAuth: _QueryStub(one_or_none_result=oauth_binding),
                    }
                )
            ),
            jwt_service=SimpleNamespace(generate_token=lambda _payload: "jwt-token"),
        )

        result = service.get_account_oauth_by_provider_name_and_openid("github", "openid-1")

        assert result is oauth_binding

    def test_get_account_by_email_should_return_query_result(self):
        account = SimpleNamespace(id=uuid4(), email="demo@example.com")
        service = _new_account_service(
            db=SimpleNamespace(
                session=_SessionStub(
                    {
                        Account: _QueryStub(one_or_none_result=account),
                    }
                )
            ),
            jwt_service=SimpleNamespace(generate_token=lambda _payload: "jwt-token"),
        )

        result = service.get_account_by_email("demo@example.com")

        assert result is account

    def test_create_account_should_delegate_to_base_create(self, monkeypatch):
        service = self._build_service()
        captures = []
        monkeypatch.setattr(
            service,
            "create",
            lambda model, **kwargs: captures.append((model, kwargs)) or SimpleNamespace(**kwargs),
        )

        created = service.create_account(email="new@example.com", name="new-user")

        assert captures[0][0] is Account
        assert captures[0][1]["email"] == "new@example.com"
        assert created.name == "new-user"

    def test_update_account_should_delegate_update_and_return_account(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4(), name="old")
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.update_account(account, name="new-name")

        assert result is account
        assert updates == [(account, {"name": "new-name"})]

    def test_password_login_should_raise_when_email_not_exists(self, monkeypatch):
        service = self._build_service()
        monkeypatch.setattr("internal.service.account_service.redis_client", _RedisStub())
        monkeypatch.setattr(service, "get_account_by_email", lambda _email: None)

        app = Flask(__name__)
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": "127.0.0.1"}):
            with pytest.raises(FailException) as exc_info:
                service.password_login("demo@example.com", "pwd")

        assert exc_info.value.data["reason_code"] == service.INVALID_CREDENTIALS_REASON_CODE

    def test_password_login_should_raise_when_password_invalid(self, monkeypatch):
        service = self._build_service()
        monkeypatch.setattr("internal.service.account_service.redis_client", _RedisStub())
        account = SimpleNamespace(
            id=uuid4(),
            password="hashed",
            password_salt="salt",
            is_password_set=True,
        )
        monkeypatch.setattr(service, "get_account_by_email", lambda _email: account)
        monkeypatch.setattr(
            "internal.service.account_service.compare_password",
            lambda *_args, **_kwargs: False,
        )

        app = Flask(__name__)
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": "127.0.0.1"}):
            with pytest.raises(FailException) as exc_info:
                service.password_login("demo@example.com", "bad-pwd")

        assert exc_info.value.data["reason_code"] == service.INVALID_CREDENTIALS_REASON_CODE

    def test_password_login_should_raise_when_password_not_initialized(self, monkeypatch):
        service = self._build_service()
        monkeypatch.setattr("internal.service.account_service.redis_client", _RedisStub())
        account = SimpleNamespace(
            id=uuid4(),
            password="",
            password_salt="salt",
            is_password_set=False,
        )
        monkeypatch.setattr(service, "get_account_by_email", lambda _email: account)
        monkeypatch.setattr(
            service,
            "get_account_oauths_by_account_id",
            lambda _account_id: [SimpleNamespace(provider="google")],
        )

        app = Flask(__name__)
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": "127.0.0.1"}):
            with pytest.raises(FailException) as exc_info:
                service.password_login("demo@example.com", "new-pwd")

        assert "账号不存在或者密码错误" in str(exc_info.value)
        assert exc_info.value.data["reason_code"] == service.INVALID_CREDENTIALS_REASON_CODE

    def test_prepare_register_should_raise_account_exists_reason_code_for_password_account(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(
            id=uuid4(),
            email="demo@example.com",
            is_password_set=True,
        )
        monkeypatch.setattr(service, "get_account_by_email", lambda _email: account)

        with pytest.raises(FailException) as exc_info:
            service.prepare_register("demo@example.com", "Abcd1234")

        assert str(exc_info.value) == "账号已存在，请直接登录"
        assert exc_info.value.data["reason_code"] == service.ACCOUNT_EXISTS_REASON_CODE

    def test_prepare_register_should_raise_oauth_only_reason_code_with_providers(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(
            id=uuid4(),
            email="oauth@example.com",
            is_password_set=False,
        )
        monkeypatch.setattr(service, "get_account_by_email", lambda _email: account)
        monkeypatch.setattr(
            service,
            "get_account_oauths_by_account_id",
            lambda _account_id: [
                SimpleNamespace(provider="google"),
                SimpleNamespace(provider="google"),
                SimpleNamespace(provider="github"),
            ],
        )

        with pytest.raises(FailException) as exc_info:
            service.prepare_register("oauth@example.com", "Abcd1234")

        assert str(exc_info.value) == "该账号尚未设置密码，请使用Google / GitHub登录"
        assert exc_info.value.data["reason_code"] == service.OAUTH_ONLY_ACCOUNT_REASON_CODE
        assert exc_info.value.data["providers"] == ["google", "github"]

    def test_password_login_should_return_token_and_update_login_info(self, monkeypatch):
        redis_stub = _RedisStub()
        monkeypatch.setattr("internal.service.account_service.redis_client", redis_stub)
        service = self._build_service()
        account = SimpleNamespace(
            id=uuid4(),
            password="hashed-password",
            password_salt="salt",
            is_password_set=True,
        )
        monkeypatch.setattr(service, "get_account_by_email", lambda _email: account)
        monkeypatch.setattr(
            "internal.service.account_service.compare_password",
            lambda *_args, **_kwargs: True,
        )
        update_calls = []
        monkeypatch.setattr(
            service,
            "issue_credential",
            lambda target_account: update_calls.append(target_account)
            or {"access_token": "jwt-token", "expire_at": 123},
        )

        app = Flask(__name__)
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": "10.0.0.5"}):
            result = service.password_login("demo@example.com", "good-pwd")

        assert result["access_token"] == "jwt-token"
        assert result["expire_at"] == 123
        assert update_calls == [account]
        assert len(redis_stub.delete_calls) == 0

    def test_password_login_should_return_login_challenge_when_ip_changes(self, monkeypatch):
        redis_stub = _RedisStub()
        monkeypatch.setattr("internal.service.account_service.redis_client", redis_stub)
        email_calls = []
        service = _new_account_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            jwt_service=SimpleNamespace(generate_token=lambda _payload: "jwt-token"),
            email_service=SimpleNamespace(send_login_challenge_code=lambda email: email_calls.append(email)),
        )
        account = SimpleNamespace(
            id=uuid4(),
            email="demo@example.com",
            password="hashed-password",
            password_salt="salt",
            is_password_set=True,
            last_login_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1),
            last_login_ip="10.0.0.4",
        )
        monkeypatch.setattr(service, "get_account_by_email", lambda _email: account)
        monkeypatch.setattr(
            "internal.service.account_service.compare_password",
            lambda *_args, **_kwargs: True,
        )
        monkeypatch.setattr(service, "get_account_sessions_by_account_id", lambda _account_id: [])
        monkeypatch.setattr(
            service,
            "issue_credential",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should require challenge first")),
        )

        app = Flask(__name__)
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": "10.0.0.8"}):
            result = service.password_login("demo@example.com", "good-pwd")

        assert result["challenge_required"] is True
        assert result["challenge_type"] == "email_code"
        assert result["risk_reason"] == "new_ip"
        assert result["masked_email"].startswith("de")
        assert email_calls == ["demo@example.com"]
        assert service._login_challenge_key(result["challenge_id"]) in redis_stub.values
        assert len(redis_stub.delete_calls) == 0

    def test_resend_login_challenge_should_reuse_pending_challenge(self, monkeypatch):
        redis_stub = _RedisStub()
        monkeypatch.setattr("internal.service.account_service.redis_client", redis_stub)
        email_calls = []
        service = _new_account_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            jwt_service=SimpleNamespace(generate_token=lambda _payload: "jwt-token"),
            email_service=SimpleNamespace(send_login_challenge_code=lambda email: email_calls.append(email)),
        )
        challenge_id = "challenge-1"
        redis_stub.setex(
            service._login_challenge_key(challenge_id),
            timedelta(minutes=10),
            json.dumps({"account_id": str(uuid4()), "email": "demo@example.com", "risk_reason": "new_ip"}),
        )

        result = service.resend_login_challenge(challenge_id)

        assert result == {
            "challenge_required": True,
            "challenge_id": challenge_id,
            "challenge_type": "email_code",
            "masked_email": "de**@example.com",
            "risk_reason": "new_ip",
        }
        assert email_calls == ["demo@example.com"]

    def test_verify_login_challenge_should_issue_credential_and_clear_pending_challenge(self, monkeypatch):
        redis_stub = _RedisStub()
        monkeypatch.setattr("internal.service.account_service.redis_client", redis_stub)
        service = _new_account_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            jwt_service=SimpleNamespace(generate_token=lambda _payload: "jwt-token"),
            email_service=SimpleNamespace(
                verify_login_challenge_code=lambda email, code: email == "demo@example.com" and code == "123456"
            ),
        )
        account = SimpleNamespace(id=uuid4(), email="demo@example.com")
        challenge_id = "challenge-2"
        redis_stub.setex(
            service._login_challenge_key(challenge_id),
            timedelta(minutes=10),
            json.dumps({"account_id": str(account.id), "email": account.email, "risk_reason": "new_ip"}),
        )
        monkeypatch.setattr(service, "get_account", lambda account_id: account if str(account_id) == str(account.id) else None)
        issue_calls = []
        monkeypatch.setattr(
            service,
            "issue_credential",
            lambda target, **kwargs: issue_calls.append((target, kwargs)) or {"access_token": "jwt-token", "expire_at": 123},
        )

        result = service.verify_login_challenge(challenge_id, "123456")

        assert result == {"access_token": "jwt-token", "expire_at": 123}
        assert issue_calls == [(account, {"skip_login_alert": True})]
        assert service._login_challenge_key(challenge_id) in redis_stub.delete_calls

    def test_verify_login_challenge_should_raise_when_code_invalid(self, monkeypatch):
        redis_stub = _RedisStub()
        monkeypatch.setattr("internal.service.account_service.redis_client", redis_stub)
        service = _new_account_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            jwt_service=SimpleNamespace(generate_token=lambda _payload: "jwt-token"),
            email_service=SimpleNamespace(verify_login_challenge_code=lambda *_args, **_kwargs: False),
        )
        challenge_id = "challenge-3"
        redis_stub.setex(
            service._login_challenge_key(challenge_id),
            timedelta(minutes=10),
            json.dumps({"account_id": str(uuid4()), "email": "demo@example.com", "risk_reason": "new_ip"}),
        )

        with pytest.raises(FailException, match="验证码错误或已过期"):
            service.verify_login_challenge(challenge_id, "000000")

    def test_password_login_should_raise_generic_message_when_failure_reaches_threshold(self, monkeypatch):
        service = self._build_service()
        email = "demo@example.com"
        ip = "10.0.0.9"
        redis_stub = _RedisStub(
            incr_values={
                service._login_email_fail_key(email): service.MAX_LOGIN_FAILURE_PER_EMAIL - 1,
                service._login_ip_fail_key(ip): service.MAX_LOGIN_FAILURE_PER_IP - 1,
            }
        )
        monkeypatch.setattr("internal.service.account_service.redis_client", redis_stub)
        monkeypatch.setattr(service, "get_account_by_email", lambda _email: None)

        app = Flask(__name__)
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": ip}):
            with pytest.raises(FailException) as exc_info:
                service.password_login(email, "pwd")

        assert "账号不存在或者密码错误" in str(exc_info.value)
        assert len(redis_stub.setex_calls) == 0

    def test_is_login_locked_should_fallback_to_false_when_redis_unavailable(self, monkeypatch):
        class _BrokenRedis:
            @staticmethod
            def exists(_key):
                raise RuntimeError("redis-down")

        service = self._build_service()
        monkeypatch.setattr("internal.service.account_service.redis_client", _BrokenRedis())

        assert service._is_login_locked("demo@example.com", "10.0.0.1") is False

    def test_record_login_failure_should_fallback_to_false_when_redis_unavailable(self, monkeypatch):
        class _BrokenRedis:
            @staticmethod
            def incr(_key):
                raise RuntimeError("redis-down")

        service = self._build_service()
        monkeypatch.setattr("internal.service.account_service.redis_client", _BrokenRedis())

        assert service._record_login_failure("demo@example.com", "10.0.0.2") is False

    def test_clear_login_failure_should_swallow_redis_delete_error(self, monkeypatch):
        class _BrokenRedis:
            @staticmethod
            def delete(*_keys):
                raise RuntimeError("redis-down")

        service = self._build_service()
        monkeypatch.setattr("internal.service.account_service.redis_client", _BrokenRedis())

        # no exception
        service._clear_login_failure("demo@example.com", "10.0.0.3")

    def test_password_login_should_raise_generic_message_when_wrong_password_reaches_threshold(self, monkeypatch):
        service = self._build_service()
        email = "demo@example.com"
        ip = "10.0.0.10"
        redis_stub = _RedisStub(
            incr_values={
                service._login_email_fail_key(email): service.MAX_LOGIN_FAILURE_PER_EMAIL - 1,
            }
        )
        monkeypatch.setattr("internal.service.account_service.redis_client", redis_stub)
        monkeypatch.setattr(
            service,
            "get_account_by_email",
            lambda _email: SimpleNamespace(
                id=uuid4(),
                password="hashed",
                password_salt="salt",
                is_password_set=True,
            ),
        )
        monkeypatch.setattr(
            "internal.service.account_service.compare_password",
            lambda *_args, **_kwargs: False,
        )

        app = Flask(__name__)
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": ip}):
            with pytest.raises(FailException) as exc_info:
                service.password_login(email, "wrong")

        assert "账号不存在或者密码错误" in str(exc_info.value)

    def test_send_reset_code_should_return_silently_when_email_not_registered(self, monkeypatch):
        service = self._build_service()
        monkeypatch.setattr(service, "get_account_by_email", lambda _email: None)
        email_calls = []
        service.email_service = SimpleNamespace(send_verification_code=lambda email: email_calls.append(email))

        service.send_reset_code("missing@example.com")

        assert email_calls == []

    def test_send_reset_code_should_delegate_to_email_service(self, monkeypatch):
        email_calls = []
        service = _new_account_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            jwt_service=SimpleNamespace(generate_token=lambda _payload: "jwt-token"),
            email_service=SimpleNamespace(
                send_verification_code=lambda email: email_calls.append(email),
                verify_code=lambda _email, _code: False,
            ),
        )
        monkeypatch.setattr(service, "get_account_by_email", lambda _email: SimpleNamespace(id=uuid4()))

        service.send_reset_code("demo@example.com")

        assert email_calls == ["demo@example.com"]

    def test_send_change_email_code_should_reject_same_email(self):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4(), email="demo@example.com")

        with pytest.raises(FailException):
            service.send_change_email_code(account, "demo@example.com")

    def test_send_change_email_code_should_delegate_to_email_service(self, monkeypatch):
        email_calls = []
        service = _new_account_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            jwt_service=SimpleNamespace(generate_token=lambda _payload: "jwt-token"),
            email_service=SimpleNamespace(
                send_change_email_code=lambda email: email_calls.append(email),
                verify_change_email_code=lambda _email, _code: False,
            ),
        )
        account = SimpleNamespace(id=uuid4(), email="demo@example.com")
        monkeypatch.setattr(service, "get_account_by_email", lambda _email: None)

        service.send_change_email_code(account, "next@example.com")

        assert email_calls == ["next@example.com"]

    def test_update_email_should_require_current_password_when_password_is_set(self, monkeypatch):
        service = _new_account_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            jwt_service=SimpleNamespace(generate_token=lambda _payload: "jwt-token"),
            email_service=SimpleNamespace(
                send_change_email_code=lambda _email: None,
                verify_change_email_code=lambda _email, _code: True,
            ),
        )
        account = SimpleNamespace(
            id=uuid4(),
            email="demo@example.com",
            is_password_set=True,
            password="hashed",
            password_salt="salt",
        )
        monkeypatch.setattr(service, "get_account_by_email", lambda _email: None)

        with pytest.raises(FailException, match="请输入当前密码"):
            service.update_email(account, "next@example.com", "123456", "")

    def test_update_email_should_raise_when_current_password_invalid(self, monkeypatch):
        service = _new_account_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            jwt_service=SimpleNamespace(generate_token=lambda _payload: "jwt-token"),
            email_service=SimpleNamespace(
                send_change_email_code=lambda _email: None,
                verify_change_email_code=lambda _email, _code: (_ for _ in ()).throw(
                    AssertionError("should not verify code when password invalid")
                ),
            ),
        )
        account = SimpleNamespace(
            id=uuid4(),
            email="demo@example.com",
            is_password_set=True,
            password="hashed",
            password_salt="salt",
        )
        monkeypatch.setattr(service, "get_account_by_email", lambda _email: None)
        monkeypatch.setattr(
            "internal.service.account_service.compare_password",
            lambda *_args, **_kwargs: False,
        )

        with pytest.raises(FailException, match="当前密码错误"):
            service.update_email(account, "next@example.com", "123456", "bad-password")

    def test_update_email_should_raise_when_code_invalid(self, monkeypatch):
        service = _new_account_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            jwt_service=SimpleNamespace(generate_token=lambda _payload: "jwt-token"),
            email_service=SimpleNamespace(
                send_change_email_code=lambda _email: None,
                verify_change_email_code=lambda _email, _code: False,
            ),
        )
        account = SimpleNamespace(id=uuid4(), email="demo@example.com", is_password_set=False)
        monkeypatch.setattr(service, "get_account_by_email", lambda _email: None)

        with pytest.raises(FailException):
            service.update_email(account, "next@example.com", "123456")

    def test_update_email_should_update_account_when_code_valid(self, monkeypatch):
        service = _new_account_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            jwt_service=SimpleNamespace(generate_token=lambda _payload: "jwt-token"),
            email_service=SimpleNamespace(
                send_change_email_code=lambda _email: None,
                verify_change_email_code=lambda _email, _code: True,
            ),
        )
        account = SimpleNamespace(id=uuid4(), email="demo@example.com", is_password_set=False)
        update_calls = []
        monkeypatch.setattr(service, "get_account_by_email", lambda _email: None)
        monkeypatch.setattr(
            service,
            "update_account",
            lambda target, **kwargs: update_calls.append((target, kwargs)) or target,
        )

        result = service.update_email(account, "next@example.com", "123456")

        assert result is account
        assert update_calls == [(account, {"email": "next@example.com"})]

    def test_reset_password_should_raise_when_code_invalid(self, monkeypatch):
        service = _new_account_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            jwt_service=SimpleNamespace(generate_token=lambda _payload: "jwt-token"),
            email_service=SimpleNamespace(
                send_verification_code=lambda _email: None,
                verify_code=lambda _email, _code: False,
            ),
        )
        monkeypatch.setattr(
            service,
            "get_account_by_email",
            lambda _email: (_ for _ in ()).throw(AssertionError("should not query account when code invalid")),
        )

        with pytest.raises(FailException):
            service.reset_password("demo@example.com", "123456", "new-pass")

    def test_reset_password_should_raise_when_account_missing(self):
        service = _new_account_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            jwt_service=SimpleNamespace(generate_token=lambda _payload: "jwt-token"),
            email_service=SimpleNamespace(
                send_verification_code=lambda _email: None,
                verify_code=lambda _email, _code: True,
            ),
        )
        service.get_account_by_email = lambda _email: None

        with pytest.raises(FailException):
            service.reset_password("demo@example.com", "123456", "new-pass")

    def test_reset_password_should_update_password_when_code_valid(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        service = _new_account_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            jwt_service=SimpleNamespace(generate_token=lambda _payload: "jwt-token"),
            email_service=SimpleNamespace(
                send_verification_code=lambda _email: None,
                verify_code=lambda _email, _code: True,
            ),
        )
        monkeypatch.setattr(service, "get_account_by_email", lambda _email: account)
        update_password_calls = []
        monkeypatch.setattr(
            service,
            "update_password",
            lambda password, target_account: update_password_calls.append((password, target_account)),
        )

        service.reset_password("demo@example.com", "123456", "new-pass")

        assert update_password_calls == [("new-pass", account)]
