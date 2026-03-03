from contextlib import contextmanager
import json
from types import SimpleNamespace
from uuid import uuid4
import base64

from flask import Flask
import pytest
from pydantic import ValidationError as PydanticValidationError
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


class TestApiToolService:
    def _req(self):
        return SimpleNamespace(
            name=SimpleNamespace(data="Weather Tools"),
            icon=SimpleNamespace(data="https://a.com/icon.png"),
            openapi_schema=SimpleNamespace(data='{"openapi":"3.0.0"}'),
            headers=SimpleNamespace(data=[{"key": "Authorization", "value": "Bearer x"}]),
        )

    def test_parse_openapi_schema_should_raise_for_invalid_json(self):
        with pytest.raises(ValidateErrorException):
            _ApiToolService.parse_openapi_schema("not-a-json")

    def test_parse_openapi_schema_should_raise_for_non_object_json(self):
        with pytest.raises(ValidateErrorException):
            _ApiToolService.parse_openapi_schema('["not-object"]')

    def test_parse_openapi_schema_should_raise_for_schema_validation_error(self):
        with pytest.raises(ValidateErrorException, match="description不能为空"):
            _ApiToolService.parse_openapi_schema(
                json.dumps(
                    {
                        "server": "https://api.example.com",
                        "description": "",
                        "paths": {
                            "/weather": {
                                "get": {
                                    "description": "查询天气",
                                    "operationId": "get_weather",
                                    "parameters": [],
                                }
                            }
                        },
                    }
                )
            )

    def test_parse_openapi_schema_should_raise_for_pydantic_validation_error(self, monkeypatch):
        class _Tmp(BaseModel):
            required: int

        with pytest.raises(PydanticValidationError) as tmp_error:
            _Tmp(required="bad")

        class _FakeOpenAPISchema:
            def __init__(self, **_kwargs):
                raise tmp_error.value

        monkeypatch.setattr("internal.service.api_tool_service.OpenAPISchema", _FakeOpenAPISchema)

        with pytest.raises(ValidateErrorException, match="OpenAPI schema格式错误"):
            _ApiToolService.parse_openapi_schema(
                json.dumps(
                    {
                        "server": "https://api.example.com",
                        "description": "天气工具",
                        "paths": {
                            "/weather": {
                                "get": {
                                    "description": "查询天气",
                                    "operationId": "get_weather",
                                    "parameters": [],
                                }
                            }
                        },
                    }
                )
            )

    def test_parse_openapi_schema_should_return_schema_for_valid_payload(self):
        schema = _ApiToolService.parse_openapi_schema(
            json.dumps(
                {
                    "server": "https://api.example.com",
                    "description": "天气工具",
                    "paths": {
                        "/weather": {
                            "get": {
                                "description": "查询天气",
                                "operationId": "get_weather",
                                "parameters": [],
                            }
                        }
                    },
                }
            )
        )

        assert schema.server == "https://api.example.com"
        assert schema.description == "天气工具"
        assert "/weather" in schema.paths

    def test_parse_openapi_schema_should_reraise_validate_error_from_schema_constructor(self, monkeypatch):
        class _FakeOpenAPISchema:
            def __init__(self, **_kwargs):
                raise ValidateErrorException("schema-field-error")

        monkeypatch.setattr("internal.service.api_tool_service.OpenAPISchema", _FakeOpenAPISchema)

        with pytest.raises(ValidateErrorException, match="schema-field-error"):
            _ApiToolService.parse_openapi_schema(
                json.dumps(
                    {
                        "server": "https://api.example.com",
                        "description": "天气工具",
                        "paths": {},
                    }
                )
            )

    def test_parse_openapi_schema_should_wrap_validation_error_with_location(self, monkeypatch):
        class _ValidationModel(BaseModel):
            required: int

        with pytest.raises(PydanticValidationError) as error_info:
            _ValidationModel(required="bad-int")

        class _FakeOpenAPISchema:
            def __init__(self, **_kwargs):
                raise error_info.value

        monkeypatch.setattr("internal.service.api_tool_service.OpenAPISchema", _FakeOpenAPISchema)

        with pytest.raises(ValidateErrorException, match="required"):
            _ApiToolService.parse_openapi_schema(
                json.dumps(
                    {
                        "server": "https://api.example.com",
                        "description": "天气工具",
                        "paths": {},
                    }
                )
            )

    def test_create_api_tool_should_raise_for_duplicate_provider_name(self, monkeypatch):
        db = _DBStub(
            _SessionStub(
                {
                    ApiToolProvider: _QueryStub(one_or_none_result=SimpleNamespace(id=uuid4())),
                }
            )
        )
        service = _new_api_tool_service(db=db, api_provider_manager=SimpleNamespace())
        monkeypatch.setattr(
            service,
            "parse_openapi_schema",
            lambda _schema: SimpleNamespace(description="desc", server="https://api", paths={}),
        )

        with pytest.raises(ValidateErrorException):
            service.create_api_tool(self._req(), SimpleNamespace(id=uuid4()))

    def test_create_api_tool_should_create_provider_and_tools(self, monkeypatch):
        provider_id = uuid4()
        db = _DBStub(_SessionStub({ApiToolProvider: _QueryStub(one_or_none_result=None)}))
        service = _new_api_tool_service(db=db, api_provider_manager=SimpleNamespace())

        monkeypatch.setattr(
            service,
            "parse_openapi_schema",
            lambda _schema: SimpleNamespace(
                description="天气工具",
                server="https://api.example.com",
                paths={
                    "/weather": {
                        "get": {
                            "operationId": "get_weather",
                            "description": "查询天气",
                            "parameters": [{"name": "city", "in": "query"}],
                        }
                    }
                },
            ),
        )

        create_calls = []

        def _fake_create(model, **kwargs):
            create_calls.append((model, kwargs))
            if model is ApiToolProvider:
                return SimpleNamespace(id=provider_id)
            return SimpleNamespace(id=uuid4(), **kwargs)

        monkeypatch.setattr(service, "create", _fake_create)

        service.create_api_tool(self._req(), SimpleNamespace(id=uuid4()))

        assert len(create_calls) == 2
        assert create_calls[0][0] is ApiToolProvider
        assert create_calls[1][0] is ApiTool
        assert create_calls[1][1]["provider_id"] == provider_id
        assert create_calls[1][1]["url"] == "https://api.example.com/weather"
        assert create_calls[1][1]["method"] == "get"

    def test_get_api_tool_provider_should_raise_when_not_found(self, monkeypatch):
        service = _new_api_tool_service(db=SimpleNamespace(session=SimpleNamespace()), api_provider_manager=SimpleNamespace())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)

        with pytest.raises(NotFoundException):
            service.get_api_tool_provider(uuid4(), SimpleNamespace(id=str(uuid4())))

    def test_delete_api_tool_provider_should_delete_tools_and_provider(self, monkeypatch):
        account = SimpleNamespace(id=str(uuid4()))
        provider = SimpleNamespace(id=uuid4(), account_id=account.id)
        tool_query = _QueryStub()
        db = _DBStub(_SessionStub({ApiTool: tool_query}))
        service = _new_api_tool_service(db=db, api_provider_manager=SimpleNamespace())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: provider)

        service.delete_api_tool_provider(provider.id, account)

        assert tool_query.deleted is True
        assert provider in db.session.deleted_entities

    def test_update_api_tool_provider_should_replace_tools_and_update_provider(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        provider = SimpleNamespace(id=uuid4(), account_id=account.id)
        provider_query = _QueryStub(one_or_none_result=None)
        tool_delete_query = _QueryStub()
        db = _DBStub(
            _SessionStub(
                {
                    ApiToolProvider: provider_query,
                    ApiTool: tool_delete_query,
                }
            )
        )
        service = _new_api_tool_service(db=db, api_provider_manager=SimpleNamespace())
        req = self._req()

        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: provider)
        monkeypatch.setattr(
            service,
            "parse_openapi_schema",
            lambda _schema: SimpleNamespace(
                description="new-desc",
                server="https://api.example.com",
                paths={
                    "/weather": {
                        "get": {
                            "operationId": "get_weather",
                            "description": "查询天气",
                            "parameters": [{"name": "city", "in": "query"}],
                        }
                    }
                },
            ),
        )
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )
        create_calls = []
        monkeypatch.setattr(
            service,
            "create",
            lambda model, **kwargs: create_calls.append((model, kwargs)) or SimpleNamespace(**kwargs),
        )

        service.update_api_tool_provider(provider.id, req, account)

        assert tool_delete_query.deleted is True
        assert updates[0][0] is provider
        assert updates[0][1]["name"] == req.name.data
        assert updates[0][1]["description"] == "new-desc"
        assert len(create_calls) == 1
        assert create_calls[0][0] is ApiTool
        assert create_calls[0][1]["provider_id"] == provider.id
        assert create_calls[0][1]["url"] == "https://api.example.com/weather"
        assert create_calls[0][1]["method"] == "get"

    def test_update_api_tool_provider_should_raise_when_provider_missing_or_not_owned(self):
        service = _new_api_tool_service(
            db=_DBStub(_SessionStub({ApiToolProvider: _QueryStub(one_or_none_result=None)})),
            api_provider_manager=SimpleNamespace(),
        )
        req = self._req()
        service.get = lambda *_args, **_kwargs: None

        with pytest.raises(ValidateErrorException):
            service.update_api_tool_provider(uuid4(), req, SimpleNamespace(id=uuid4()))

    def test_update_api_tool_provider_should_raise_when_provider_name_conflicted(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        provider = SimpleNamespace(id=uuid4(), account_id=account.id)
        duplicate_provider = SimpleNamespace(id=uuid4(), account_id=account.id)
        db = _DBStub(
            _SessionStub(
                {
                    ApiToolProvider: _QueryStub(one_or_none_result=duplicate_provider),
                }
            )
        )
        service = _new_api_tool_service(db=db, api_provider_manager=SimpleNamespace())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: provider)
        monkeypatch.setattr(
            service,
            "parse_openapi_schema",
            lambda _schema: SimpleNamespace(description="desc", server="https://api", paths={}),
        )

        with pytest.raises(ValidateErrorException):
            service.update_api_tool_provider(provider.id, self._req(), account)

    def test_get_api_tool_providers_with_page_should_delegate_to_paginator(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        service = _new_api_tool_service(
            db=SimpleNamespace(session=_SessionStub({ApiToolProvider: _QueryStub(all_result=[])})),
            api_provider_manager=SimpleNamespace(),
        )
        captures = {}

        class _Paginator:
            def __init__(self, db, req):
                captures["db"] = db
                captures["req"] = req

            def paginate(self, query):
                captures["query"] = query
                return ["provider-1"]

        monkeypatch.setattr("internal.service.api_tool_service.Paginator", _Paginator)
        req = SimpleNamespace(
            current_page=SimpleNamespace(data=1),
            page_size=SimpleNamespace(data=20),
            search_word=SimpleNamespace(data="weather"),
        )

        records, paginator = service.get_api_tool_providers_wiith_page(req, account)

        assert records == ["provider-1"]
        assert captures["req"] is req
        assert captures["db"] is service.db
        assert captures["query"] is not None
        assert isinstance(paginator, _Paginator)

    def test_get_api_tool_providers_with_page_should_work_without_search_word(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        service = _new_api_tool_service(
            db=SimpleNamespace(session=_SessionStub({ApiToolProvider: _QueryStub(all_result=[])})),
            api_provider_manager=SimpleNamespace(),
        )

        class _Paginator:
            def __init__(self, db, req):
                self.db = db
                self.req = req

            def paginate(self, query):
                assert query is not None
                return ["provider-a", "provider-b"]

        monkeypatch.setattr("internal.service.api_tool_service.Paginator", _Paginator)
        req = SimpleNamespace(
            current_page=SimpleNamespace(data=1),
            page_size=SimpleNamespace(data=20),
            search_word=SimpleNamespace(data=""),
        )

        records, paginator = service.get_api_tool_providers_wiith_page(req, account)

        assert records == ["provider-a", "provider-b"]
        assert isinstance(paginator, _Paginator)

    def test_get_api_tool_should_return_record_when_owned(self):
        account_uuid = uuid4()
        api_tool = SimpleNamespace(id=uuid4(), account_id=account_uuid)
        service = _new_api_tool_service(
            db=SimpleNamespace(
                session=_SessionStub({ApiTool: _QueryStub(one_or_none_result=api_tool)}),
            ),
            api_provider_manager=SimpleNamespace(),
        )

        result = service.get_api_tool(uuid4(), "get_weather", SimpleNamespace(id=str(account_uuid)))

        assert result is api_tool

    def test_get_api_tool_should_raise_when_not_found_or_not_owned(self):
        service = _new_api_tool_service(
            db=SimpleNamespace(
                session=_SessionStub({ApiTool: _QueryStub(one_or_none_result=SimpleNamespace(account_id=uuid4()))}),
            ),
            api_provider_manager=SimpleNamespace(),
        )

        with pytest.raises(NotFoundException):
            service.get_api_tool(uuid4(), "get_weather", SimpleNamespace(id=str(uuid4())))

    def test_get_api_tool_provider_should_return_record_when_owned(self, monkeypatch):
        service = _new_api_tool_service(db=SimpleNamespace(session=SimpleNamespace()), api_provider_manager=SimpleNamespace())
        account_uuid = uuid4()
        provider = SimpleNamespace(id=uuid4(), account_id=account_uuid)
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: provider)

        result = service.get_api_tool_provider(provider.id, SimpleNamespace(id=str(account_uuid)))

        assert result is provider

    def test_delete_api_tool_provider_should_raise_when_provider_not_found(self, monkeypatch):
        service = _new_api_tool_service(db=_DBStub(_SessionStub({})), api_provider_manager=SimpleNamespace())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)

        with pytest.raises(NotFoundException):
            service.delete_api_tool_provider(uuid4(), SimpleNamespace(id=str(uuid4())))

    def test_regenerate_icon_should_raise_when_provider_not_found(self, monkeypatch):
        service = _new_api_tool_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            api_provider_manager=SimpleNamespace(),
            icon_generator_service=SimpleNamespace(generate_icon=lambda _name, _desc: "https://icon"),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)

        with pytest.raises(NotFoundException):
            service.regenerate_icon(uuid4(), SimpleNamespace(id=str(uuid4())))

    def test_regenerate_icon_should_update_provider_icon(self, monkeypatch):
        account_uuid = uuid4()
        provider = SimpleNamespace(
            id=uuid4(),
            account_id=account_uuid,
            name="weather-api",
            description="天气API",
            icon="old",
        )
        service = _new_api_tool_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            api_provider_manager=SimpleNamespace(),
            icon_generator_service=SimpleNamespace(
                generate_icon=lambda name, description: f"https://icon/{name}/{description}"
            ),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: provider)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.regenerate_icon(provider.id, SimpleNamespace(id=str(account_uuid)))

        assert result.startswith("https://icon/weather-api/")
        assert updates == [(provider, {"icon": result})]

    def test_regenerate_icon_should_raise_fail_exception_when_generator_failed(self, monkeypatch):
        account_uuid = uuid4()
        provider = SimpleNamespace(id=uuid4(), account_id=account_uuid, name="api", description="desc")

        def _raise_icon_error(**_kwargs):
            raise RuntimeError("icon failed")

        service = _new_api_tool_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            api_provider_manager=SimpleNamespace(),
            icon_generator_service=SimpleNamespace(
                generate_icon=_raise_icon_error
            ),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: provider)

        with pytest.raises(FailException):
            service.regenerate_icon(provider.id, SimpleNamespace(id=str(account_uuid)))

    def test_generate_icon_preview_should_return_generated_icon(self):
        service = _new_api_tool_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            api_provider_manager=SimpleNamespace(),
            icon_generator_service=SimpleNamespace(
                generate_icon=lambda name, description: f"https://preview/{name}/{description}"
            ),
        )

        icon_url = service.generate_icon_preview("weather-api", "desc")

        assert icon_url == "https://preview/weather-api/desc"

    def test_generate_icon_preview_should_raise_fail_exception_when_generator_failed(self):

        def _raise_preview_error(**_kwargs):
            raise RuntimeError("preview failed")

        service = _new_api_tool_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            api_provider_manager=SimpleNamespace(),
            icon_generator_service=SimpleNamespace(
                generate_icon=_raise_preview_error
            ),
        )

        with pytest.raises(FailException):
            service.generate_icon_preview("weather-api", "desc")
