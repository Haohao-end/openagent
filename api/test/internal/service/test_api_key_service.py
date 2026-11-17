from contextlib import contextmanager
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4
import base64

from flask import Flask
import pytest
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

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
        self.commit_calls = 0

    def query(self, model):
        result = self._query_map.get(model, _QueryStub())
        if isinstance(result, list):
            return result.pop(0)
        return result

    def delete(self, entity):
        self.deleted_entities.append(entity)

    def commit(self):
        self.commit_calls += 1


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


class TestApiKeyService:
    def _build_service(self) -> ApiKeyService:
        return ApiKeyService(db=SimpleNamespace(session=SimpleNamespace()))

    def test_record_last_used_at_should_never_overwrite_a_newer_database_timestamp(
        self, monkeypatch
    ):
        api_key_id = uuid4()
        later_used_at = datetime(2026, 11, 13, 12, 0, 0)
        earlier_request_at = datetime(2026, 11, 13, 11, 0, 0)
        newest_request_at = datetime(2026, 11, 13, 13, 0, 0)
        engine = create_engine("sqlite://")
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE api_key (id CHAR(32) PRIMARY KEY, last_used_at DATETIME)"
            )
            connection.execute(
                text("INSERT INTO api_key (id, last_used_at) VALUES (:id, :last_used_at)"),
                {"id": api_key_id.hex, "last_used_at": later_used_at.isoformat(sep=" ")},
            )
        session = Session(engine)

        @contextmanager
        def auto_commit():
            try:
                yield
                session.commit()
            except Exception:
                session.rollback()
                raise

        service = ApiKeyService(db=SimpleNamespace(session=session, auto_commit=auto_commit))
        monkeypatch.setattr(
            "internal.service.api_key_service.utc_now_naive",
            lambda: earlier_request_at,
        )
        api_key_record = SimpleNamespace(id=api_key_id)

        service.record_last_used_at(api_key_record)

        stored_timestamp = session.execute(
            text("SELECT last_used_at FROM api_key WHERE id = :id"),
            {"id": api_key_id.hex},
        ).scalar_one()
        assert datetime.fromisoformat(stored_timestamp) == later_used_at

        monkeypatch.setattr(
            "internal.service.api_key_service.utc_now_naive",
            lambda: newest_request_at,
        )
        service.record_last_used_at(api_key_record)

        stored_timestamp = session.execute(
            text("SELECT last_used_at FROM api_key WHERE id = :id"),
            {"id": api_key_id.hex},
        ).scalar_one()
        assert datetime.fromisoformat(stored_timestamp) == newest_request_at
        session.close()
        engine.dispose()

    def test_record_last_used_at_should_enforce_a_rolling_one_minute_interval(self, monkeypatch):
        api_key_id = uuid4()
        first_use = datetime(2026, 11, 13, 10, 5, 59)
        rapid_followup = datetime(2026, 11, 13, 10, 6, 0)
        before_interval = datetime(2026, 11, 13, 10, 6, 58)
        next_eligible_use = datetime(2026, 11, 13, 10, 6, 59)
        engine = create_engine("sqlite://")
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE api_key (id CHAR(32) PRIMARY KEY, last_used_at DATETIME)"
            )
            connection.execute(
                text("INSERT INTO api_key (id, last_used_at) VALUES (:id, :last_used_at)"),
                {
                    "id": api_key_id.hex,
                    "last_used_at": datetime(2026, 11, 13, 10, 4, 59).isoformat(sep=" "),
                },
            )
        session = Session(engine)

        @contextmanager
        def auto_commit():
            try:
                yield
                session.commit()
            except Exception:
                session.rollback()
                raise

        service = ApiKeyService(db=SimpleNamespace(session=session, auto_commit=auto_commit))
        api_key_record = SimpleNamespace(id=api_key_id)

        expected_by_use = {
            first_use: first_use,
            rapid_followup: first_use,
            before_interval: first_use,
            next_eligible_use: next_eligible_use,
        }
        for used_at, expected_timestamp in expected_by_use.items():
            monkeypatch.setattr(
                "internal.service.api_key_service.utc_now_naive",
                lambda used_at=used_at: used_at,
            )
            service.record_last_used_at(api_key_record)
            stored_timestamp = session.execute(
                text("SELECT last_used_at FROM api_key WHERE id = :id"),
                {"id": api_key_id.hex},
            ).scalar_one()
            assert datetime.fromisoformat(stored_timestamp) == expected_timestamp
        session.close()
        engine.dispose()

    def test_record_api_key_request_counts_each_request_and_throttles_last_used_at(self, monkeypatch):
        api_key_id = uuid4()
        first_request = datetime(2026, 11, 15, 10, 0, 0)
        second_request = datetime(2026, 11, 15, 10, 0, 30)
        engine = create_engine("sqlite://")
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE api_key (id CHAR(32) PRIMARY KEY, request_count BIGINT NOT NULL, last_used_at DATETIME)"
            )
            connection.execute(
                text("INSERT INTO api_key (id, request_count, last_used_at) VALUES (:id, 0, NULL)"),
                {"id": api_key_id.hex},
            )
        session = Session(engine)

        @contextmanager
        def auto_commit():
            try:
                yield
                session.commit()
            except Exception:
                session.rollback()
                raise

        service = ApiKeyService(db=SimpleNamespace(session=session, auto_commit=auto_commit))
        api_key_record = SimpleNamespace(id=api_key_id)

        for request_count, requested_at in enumerate((first_request, second_request), start=1):
            monkeypatch.setattr(
                "internal.service.api_key_service.utc_now_naive",
                lambda requested_at=requested_at: requested_at,
            )
            service.record_api_key_request(api_key_record)
            stored_count, stored_last_used = session.execute(
                text("SELECT request_count, last_used_at FROM api_key WHERE id = :id"),
                {"id": api_key_id.hex},
            ).one()
            assert stored_count == request_count
            assert datetime.fromisoformat(stored_last_used) == first_request
        session.close()
        engine.dispose()

    def test_record_api_key_request_should_safely_ignore_record_without_id(self):
        service = ApiKeyService(db=SimpleNamespace(session=None, auto_commit=None))
        service.record_api_key_request(None)
        service.record_api_key_request(SimpleNamespace())

    def test_record_last_used_at_should_safely_ignore_record_without_id(self):
        service = ApiKeyService(db=SimpleNamespace(session=None, auto_commit=None))
        service.record_last_used_at(None)
        service.record_last_used_at(SimpleNamespace())

    def test_get_api_by_by_credential_should_return_query_result(self):
        api_key_record = SimpleNamespace(id=uuid4(), api_key="llmops-v1/demo")
        service = ApiKeyService(
            db=SimpleNamespace(
                session=_SessionStub(
                    {
                        ApiKey: _QueryStub(one_or_none_result=api_key_record),
                    }
                )
            )
        )

        # 通过真实查询入口验证：按凭证查询时应直接返回匹配记录
        result = service.get_api_by_by_credential("llmops-v1/demo")

        assert result is api_key_record

    def test_get_api_by_by_credential_should_upgrade_plaintext_record(self):
        legacy_api_key = SimpleNamespace(id=uuid4(), api_key="llmops-v1/demo")
        session = _SessionStub(
            {
                ApiKey: [
                    _QueryStub(one_or_none_result=None),
                    _QueryStub(one_or_none_result=legacy_api_key),
                ]
            }
        )
        service = ApiKeyService(db=SimpleNamespace(session=session))

        result = service.get_api_by_by_credential("llmops-v1/demo")

        assert result is legacy_api_key
        assert legacy_api_key.api_key == ApiKeyService.hash_api_key("llmops-v1/demo")
        assert session.commit_calls == 1

    def test_get_api_by_by_credential_should_not_commit_when_legacy_already_hashed(self):
        hashed_api_key = ApiKeyService.hash_api_key("llmops-v1/demo")
        legacy_api_key = SimpleNamespace(id=uuid4(), api_key=hashed_api_key)
        session = _SessionStub(
            {
                ApiKey: [
                    _QueryStub(one_or_none_result=None),
                    _QueryStub(one_or_none_result=legacy_api_key),
                ]
            }
        )
        service = ApiKeyService(db=SimpleNamespace(session=session))

        result = service.get_api_by_by_credential("llmops-v1/demo")

        assert result is legacy_api_key
        assert legacy_api_key.api_key == hashed_api_key
        assert session.commit_calls == 0

    def test_get_api_by_by_credential_should_upgrade_without_commit_method(self):
        legacy_api_key = SimpleNamespace(id=uuid4(), api_key="llmops-v1/demo")

        class _SessionWithoutCommit:
            def __init__(self):
                self._queries = [
                    _QueryStub(one_or_none_result=None),
                    _QueryStub(one_or_none_result=legacy_api_key),
                ]

            def query(self, _model):
                return self._queries.pop(0)

        service = ApiKeyService(db=SimpleNamespace(session=_SessionWithoutCommit()))

        result = service.get_api_by_by_credential("llmops-v1/demo")

        assert result is legacy_api_key
        assert legacy_api_key.api_key == ApiKeyService.hash_api_key("llmops-v1/demo")

    def test_get_api_by_by_credential_should_return_none_for_empty_or_whitespace_key(self):
        query_called = []
        session = SimpleNamespace(query=lambda _m: query_called.append(True))
        service = ApiKeyService(db=SimpleNamespace(session=session))

        assert service.get_api_by_by_credential("") is None
        assert service.get_api_by_by_credential("   ") is None
        assert service.get_api_by_by_credential(None) is None
        assert query_called == []

    def test_get_api_by_by_credential_should_rollback_and_return_record_when_commit_fails(self):
        legacy_api_key = SimpleNamespace(id=uuid4(), api_key="llmops-v1/demo")
        rollback_called = []

        class _FlakySession:
            def __init__(self):
                self._queries = [
                    _QueryStub(one_or_none_result=None),
                    _QueryStub(one_or_none_result=legacy_api_key),
                ]

            def query(self, _model):
                return self._queries.pop(0)

            def commit(self):
                raise RuntimeError("simulated commit failure")

            def rollback(self):
                rollback_called.append(True)

        service = ApiKeyService(db=SimpleNamespace(session=_FlakySession()))

        result = service.get_api_by_by_credential("llmops-v1/demo")

        assert result is legacy_api_key
        assert rollback_called == [True]

    def test_get_api_key_should_raise_when_not_owned(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        monkeypatch.setattr(
            service,
            "get",
            lambda *_args, **_kwargs: SimpleNamespace(account_id=uuid4()),
        )

        with pytest.raises(ForbiddenException):
            service.get_api_key(uuid4(), account)

    def test_update_api_key_should_reject_updates_from_another_account(self, monkeypatch):
        service = self._build_service()
        requester = SimpleNamespace(id=uuid4())
        api_key = SimpleNamespace(id=uuid4(), account_id=uuid4())
        updates = []
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: api_key)
        monkeypatch.setattr(
            service,
            "update",
            lambda *args, **kwargs: updates.append((args, kwargs)),
        )

        with pytest.raises(ForbiddenException):
            service.update_api_key(api_key.id, requester, remark="changed")

        assert updates == []

    def test_update_api_key_should_filter_unallowed_fields_and_validate_scopes(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        api_key = SimpleNamespace(id=uuid4(), account_id=account.id)
        updates = []
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: api_key)
        monkeypatch.setattr(
            service,
            "update",
            lambda *args, **kwargs: updates.append(kwargs),
        )

        service.update_api_key(
            api_key.id,
            account,
            remark="new-remark",
            is_active=False,
            scopes=["openapi:chat"],
            account_id=uuid4(),
            request_count=999,
            api_key="hacked",
        )

        assert updates == [{
            "remark": "new-remark",
            "is_active": False,
            "scopes": ["openapi:chat"],
        }]

    def test_update_api_key_should_reject_invalid_scopes(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        api_key = SimpleNamespace(id=uuid4(), account_id=account.id)
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: api_key)

        with pytest.raises(ValueError, match="unsupported scope"):
            service.update_api_key(api_key.id, account, scopes=["admin:all"])

        with pytest.raises(ValueError, match="cannot contain duplicates"):
            service.update_api_key(api_key.id, account, scopes=["openapi:chat", "openapi:chat"])

        with pytest.raises(ValueError, match="list of strings"):
            service.update_api_key(api_key.id, account, scopes="not-a-list")

    def test_delete_api_key_should_reject_deletion_from_another_account(self, monkeypatch):
        service = self._build_service()
        requester = SimpleNamespace(id=uuid4())
        api_key = SimpleNamespace(id=uuid4(), account_id=uuid4())
        deleted = []
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: api_key)
        monkeypatch.setattr(service, "delete", lambda target: deleted.append(target))

        with pytest.raises(ForbiddenException):
            service.delete_api_key(api_key.id, requester)

        assert deleted == []

    def test_get_api_key_should_return_record_when_owned(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        owned_api_key = SimpleNamespace(id=uuid4(), account_id=account.id)
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: owned_api_key)

        result = service.get_api_key(owned_api_key.id, account)

        assert result is owned_api_key

    def test_create_api_key_should_use_generated_key(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        req = SimpleNamespace(
            is_active=SimpleNamespace(data=True),
            remark=SimpleNamespace(data="for-ci"),
            expires_at=SimpleNamespace(data=1_900_000_000),
            scopes=SimpleNamespace(data=[]),
        )
        monkeypatch.setattr(service, "generate_api_key", lambda: "llmops-v1/mock-key")

        captures = []
        monkeypatch.setattr(
            service,
            "create",
            lambda model, **kwargs: captures.append((model, kwargs)) or SimpleNamespace(**kwargs),
        )

        created = service.create_api_key(req, account)

        assert created["api_key"] == "llmops-v1/mock-key"
        assert captures[0][1]["account_id"] == account.id
        assert captures[0][1]["remark"] == "for-ci"
        assert captures[0][1]["api_key"] == ApiKeyService.hash_api_key("llmops-v1/mock-key")
        assert captures[0][1]["expires_at"] == datetime.fromtimestamp(1_900_000_000, UTC).replace(tzinfo=None)
        assert captures[0][1]["scopes"] == []

    def test_create_api_key_should_default_to_chat_scope_when_missing(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        req = SimpleNamespace(
            is_active=SimpleNamespace(data=True),
            remark=SimpleNamespace(data="for-ci"),
            expires_at=SimpleNamespace(data=None),
        )
        monkeypatch.setattr(service, "generate_api_key", lambda: "llmops-v1/mock-key")
        captures = []
        monkeypatch.setattr(
            service,
            "create",
            lambda model, **kwargs: captures.append((model, kwargs)) or SimpleNamespace(**kwargs),
        )

        service.create_api_key(req, account)

        assert captures[0][1]["scopes"] == ["openapi:chat"]

    def test_update_api_key_should_delegate_update(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        api_key = SimpleNamespace(id=uuid4(), account_id=account.id)
        monkeypatch.setattr(service, "get_api_key", lambda *_args, **_kwargs: api_key)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.update_api_key(api_key.id, account, remark="updated", expires_at=1_900_000_000)

        assert result is api_key
        assert updates == [(
            api_key,
            {
                "remark": "updated",
                "expires_at": datetime.fromtimestamp(1_900_000_000, UTC).replace(tzinfo=None),
            },
        )]

    def test_update_api_key_should_clear_expiration(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        api_key = SimpleNamespace(id=uuid4(), account_id=account.id)
        monkeypatch.setattr(service, "get_api_key", lambda *_args, **_kwargs: api_key)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        service.update_api_key(api_key.id, account, expires_at=None)

        assert updates == [(api_key, {"expires_at": None})]

    @pytest.mark.parametrize("invalid_remark", [123, "a" * 101])
    def test_update_api_key_should_reject_invalid_remark(self, monkeypatch, invalid_remark):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        api_key = SimpleNamespace(id=uuid4(), account_id=account.id)
        monkeypatch.setattr(service, "get_api_key", lambda *_args, **_kwargs: api_key)

        with pytest.raises(ValueError):
            service.update_api_key(api_key.id, account, remark=invalid_remark)

    def test_update_api_key_should_strip_remark(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        api_key = SimpleNamespace(id=uuid4(), account_id=account.id)
        monkeypatch.setattr(service, "get_api_key", lambda *_args, **_kwargs: api_key)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        service.update_api_key(api_key.id, account, remark="  trimmed  ")

        assert updates == [(api_key, {"remark": "trimmed"})]

    @pytest.mark.parametrize("invalid_ts", [0, -1, -100])
    def test_update_api_key_should_reject_non_positive_expiration(self, monkeypatch, invalid_ts):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        api_key = SimpleNamespace(id=uuid4(), account_id=account.id)
        monkeypatch.setattr(service, "get_api_key", lambda *_args, **_kwargs: api_key)

        with pytest.raises(ValueError, match="positive"):
            service.update_api_key(api_key.id, account, expires_at=invalid_ts)

    def test_generate_api_key_should_keep_prefix(self):
        key = ApiKeyService.generate_api_key("prefix/")
        assert key.startswith("prefix/")
        assert len(key) > len("prefix/")

    def test_hash_api_key_should_generate_stable_sha256_hex(self):
        value = "llmops-v1/test"
        assert ApiKeyService.hash_api_key(value) == ApiKeyService.hash_api_key(value)
        assert len(ApiKeyService.hash_api_key(value)) == 64

    def test_delete_api_key_should_delegate_delete_and_return_record(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        api_key = SimpleNamespace(id=uuid4(), account_id=account.id)
        monkeypatch.setattr(service, "get_api_key", lambda *_args, **_kwargs: api_key)
        deleted = []
        monkeypatch.setattr(service, "delete", lambda target: deleted.append(target))

        result = service.delete_api_key(api_key.id, account)

        assert result is api_key
        assert deleted == [api_key]

    def test_get_api_keys_with_page_should_return_paginated_records(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())

        class _AccountScopedQuery(_QueryStub):
            def __init__(self):
                super().__init__(all_result=[])
                self.criteria = []
                self.ordering = ()

            def filter(self, *criteria, **kwargs):
                self.criteria.extend(criteria)
                return self

            def order_by(self, *columns):
                self.ordering = tuple(map(str, columns))
                return self

        query = _AccountScopedQuery()
        service = ApiKeyService(
            db=SimpleNamespace(
                session=_SessionStub({ApiKey: query}),
            )
        )
        captures = {}

        class _Paginator:
            def __init__(self, db, req):
                captures["db"] = db
                captures["req"] = req

            def paginate(self, query):
                captures["query"] = query
                return ["k1", "k2"]

        monkeypatch.setattr("internal.service.api_key_service.Paginator", _Paginator)
        req = SimpleNamespace(current_page=SimpleNamespace(data=1), page_size=SimpleNamespace(data=20))

        records, paginator = service.get_api_keys_with_page(req, account)

        assert records == ["k1", "k2"]
        assert captures["req"] is req
        assert captures["db"] is service.db
        assert captures["query"] is query
        assert len(query.criteria) == 1
        account_filter = query.criteria[0]
        assert account_filter.left.name == "account_id"
        assert account_filter.left.table.name == ApiKey.__tablename__
        assert account_filter.right.value == account.id
        assert query.ordering == ("api_key.created_at DESC", "api_key.id DESC")
        assert isinstance(paginator, _Paginator)

    def test_check_rate_limit_should_allow_under_quota_and_block_when_exceeded(self):
        service = ApiKeyService(db=SimpleNamespace())
        account_id = uuid4()
        api_key_record = SimpleNamespace(id=uuid4(), account_id=account_id)
        store = {}
        ttls = {}

        class _MockRedis:
            def incr(self, key):
                store[key] = store.get(key, 0) + 1
                return store[key]

            def expire(self, key, seconds):
                ttls[key] = seconds

            def ttl(self, key):
                return ttls.get(key, -1)

        mock_redis = _MockRedis()
        allowed, count, ttl = service.check_rate_limit(api_key_record, max_requests=2, client=mock_redis)
        assert allowed is True
        assert count == 1
        assert ttl == 60

        allowed, count, _ = service.check_rate_limit(api_key_record, max_requests=2, client=mock_redis)
        assert allowed is True
        assert count == 2

        allowed, count, _ = service.check_rate_limit(api_key_record, max_requests=2, client=mock_redis)
        assert allowed is False
        assert count == 3

    def test_check_rate_limit_should_isolate_accounts_and_keys(self):
        service = ApiKeyService(db=SimpleNamespace())
        key1 = SimpleNamespace(id=uuid4(), account_id=uuid4())
        key2 = SimpleNamespace(id=uuid4(), account_id=uuid4())
        store = {}

        class _MockRedis:
            def incr(self, key):
                store[key] = store.get(key, 0) + 1
                return store[key]

            def expire(self, key, seconds):
                pass

            def ttl(self, key):
                return 60

        mock_redis = _MockRedis()
        service.check_rate_limit(key1, max_requests=1, client=mock_redis)
        allowed, count, _ = service.check_rate_limit(key2, max_requests=1, client=mock_redis)
        assert allowed is True
        assert count == 1
        assert len(store) == 2

    def test_check_rate_limit_should_handle_missing_key_and_redis_errors(self):
        service = ApiKeyService(db=SimpleNamespace())
        assert service.check_rate_limit(None) == (False, 0, 0)
        assert service.check_rate_limit(SimpleNamespace(id=None)) == (False, 0, 0)

        class _FailingRedis:
            def incr(self, _key):
                raise RuntimeError("Redis connection failure")

        key = SimpleNamespace(id=uuid4(), account_id=uuid4())
        assert service.check_rate_limit(key, client=_FailingRedis(), fail_closed=False)[0] is True
        assert service.check_rate_limit(key, client=_FailingRedis(), fail_closed=True)[0] is False

    def test_check_rate_limit_should_use_atomic_lua_when_supported(self):
        service = ApiKeyService(db=SimpleNamespace())
        key = SimpleNamespace(id=uuid4(), account_id=uuid4())
        eval_calls = []

        class _EvalRedis:
            def eval(self, script, numkeys, cache_key, window_seconds):
                eval_calls.append((script, numkeys, cache_key, window_seconds))
                return [1, window_seconds]

        allowed, count, ttl = service.check_rate_limit(key, max_requests=5, window_seconds=60, client=_EvalRedis())
        assert allowed is True
        assert count == 1
        assert ttl == 60
        assert len(eval_calls) == 1
        assert "INCR" in eval_calls[0][0]

    def test_check_rate_limit_should_heal_ttl_when_negative(self):
        service = ApiKeyService(db=SimpleNamespace())
        key = SimpleNamespace(id=uuid4(), account_id=uuid4())
        expired_calls = []

        class _MissingTtlRedis:
            def incr(self, _key):
                return 2

            def expire(self, key, seconds):
                expired_calls.append((key, seconds))

            def ttl(self, _key):
                return -1

        allowed, count, ttl = service.check_rate_limit(key, max_requests=5, window_seconds=60, client=_MissingTtlRedis())
        assert allowed is True
        assert count == 2
        assert ttl == 60
        assert len(expired_calls) == 1
