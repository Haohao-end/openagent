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
        service = ApiKeyService(
            db=SimpleNamespace(
                session=_SessionStub({ApiKey: _QueryStub(all_result=[])}),
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
        assert captures["query"] is not None
        assert isinstance(paginator, _Paginator)
