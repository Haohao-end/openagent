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


class _RedisStub:
    def __init__(self, *, exists_keys=None, incr_values=None):
        self.exists_keys = set(exists_keys or [])
        self.incr_values = dict(incr_values or {})
        self.expire_calls = []
        self.setex_calls = []
        self.delete_calls = []

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
        return True

    def delete(self, *keys):
        self.delete_calls.extend(keys)
        for key in keys:
            self.exists_keys.discard(key)
        return len(keys)


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
            with pytest.raises(FailException):
                service.password_login("demo@example.com", "pwd")

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
            with pytest.raises(FailException):
                service.password_login("demo@example.com", "bad-pwd")

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

        app = Flask(__name__)
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": "127.0.0.1"}):
            with pytest.raises(FailException):
                service.password_login("demo@example.com", "new-pwd")

    def test_password_login_should_return_token_and_update_login_info(self, monkeypatch):
        jwt_payload = {}
        redis_stub = _RedisStub()
        monkeypatch.setattr("internal.service.account_service.redis_client", redis_stub)
        service = _new_account_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            jwt_service=SimpleNamespace(
                generate_token=lambda payload: jwt_payload.update(payload) or "jwt-token"
            ),
        )
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
            "update",
            lambda target, **kwargs: update_calls.append((target, kwargs)) or target,
        )

        app = Flask(__name__)
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": "10.0.0.5"}):
            result = service.password_login("demo@example.com", "good-pwd")

        assert result["access_token"] == "jwt-token"
        assert result["expire_at"] > 0
        assert jwt_payload["sub"] == str(account.id)
        assert jwt_payload["iss"] == "llmops"
        assert jwt_payload["exp"] == result["expire_at"]
        assert update_calls[0][0] is account
        assert update_calls[0][1]["last_login_ip"] == "10.0.0.5"
        assert update_calls[0][1]["last_login_at"] is not None
        assert len(redis_stub.delete_calls) == 4

    def test_password_login_should_raise_when_login_locked(self, monkeypatch):
        service = self._build_service()
        email = "demo@example.com"
        lock_key = service._login_email_lock_key(email)
        monkeypatch.setattr("internal.service.account_service.redis_client", _RedisStub(exists_keys={lock_key}))

        app = Flask(__name__)
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": "10.0.0.8"}):
            with pytest.raises(FailException) as exc_info:
                service.password_login(email, "pwd")

        assert "登录失败次数过多" in str(exc_info.value)

    def test_password_login_should_raise_lock_message_when_failure_reaches_threshold(self, monkeypatch):
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

        assert "登录失败次数过多" in str(exc_info.value)
        assert len(redis_stub.setex_calls) >= 1

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

    def test_password_login_should_raise_lock_message_when_wrong_password_reaches_threshold(self, monkeypatch):
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

        assert "登录失败次数过多" in str(exc_info.value)

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
