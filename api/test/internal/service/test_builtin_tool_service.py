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


class TestBuiltinToolService:
    def test_get_builtin_tools_should_flatten_provider_and_tool_inputs(self):
        class _ArgsSchema(BaseModel):
            city: str = Field(description="城市")

        provider_entity = SimpleNamespace(
            model_dump=lambda exclude=None: {"name": "demo_provider", "label": "Demo Provider"},
        )
        tool_entity = SimpleNamespace(
            name="weather",
            model_dump=lambda: {"name": "weather", "label": "Weather"},
        )
        provider = SimpleNamespace(
            provider_entity=provider_entity,
            get_tool_entities=lambda: [tool_entity],
            get_tool=lambda _tool_name: SimpleNamespace(args_schema=_ArgsSchema),
        )
        service = BuiltinToolService(
            builtin_provider_manager=SimpleNamespace(get_providers=lambda: [provider]),
            builtin_category_manager=SimpleNamespace(),
        )

        result = service.get_builtin_tools()

        assert result[0]["name"] == "demo_provider"
        assert result[0]["tools"][0]["name"] == "weather"
        assert result[0]["tools"][0]["inputs"][0]["name"] == "city"

    def test_get_provider_icon_should_read_icon_from_provider_asset(self, tmp_path):
        app_root = tmp_path / "app" / "http"
        app_root.mkdir(parents=True)
        icon_path = (
            tmp_path
            / "internal"
            / "core"
            / "tools"
            / "builtin_tools"
            / "providers"
            / "demo_provider"
            / "_asset"
            / "icon.png"
        )
        icon_path.parent.mkdir(parents=True)
        icon_path.write_bytes(b"icon-bytes")

        provider = SimpleNamespace(provider_entity=SimpleNamespace(icon="icon.png"))
        service = BuiltinToolService(
            builtin_provider_manager=SimpleNamespace(get_provider=lambda _name: provider),
            builtin_category_manager=SimpleNamespace(),
        )
        app = Flask(__name__, root_path=str(app_root))
        with app.app_context():
            content, mimetype, icon_url = service.get_provider_icon("demo_provider")

        assert content == b"icon-bytes"
        assert mimetype == "image/png"
        assert icon_url is None

    def test_get_provider_icon_should_return_url_when_icon_is_remote(self):
        provider = SimpleNamespace(provider_entity=SimpleNamespace(icon="https://example.com/icon.svg"))
        service = BuiltinToolService(
            builtin_provider_manager=SimpleNamespace(get_provider=lambda _name: provider),
            builtin_category_manager=SimpleNamespace(),
        )

        content, mimetype, icon_url = service.get_provider_icon("demo_provider")

        assert content is None
        assert mimetype is None
        assert icon_url == "https://example.com/icon.svg"

    def test_get_tool_inputs_should_parse_pydantic_schema(self):
        class _ArgsSchema(BaseModel):
            city: str = Field(description="城市名")
            top_k: int = Field(default=3, description="召回数量")

        inputs = BuiltinToolService.get_tool_inputs(SimpleNamespace(args_schema=_ArgsSchema))

        assert inputs[0]["name"] == "city"
        assert inputs[0]["required"] is True
        assert inputs[1]["name"] == "top_k"
        assert inputs[1]["required"] is False

    def test_get_provider_tool_should_raise_when_provider_missing(self):
        service = BuiltinToolService(
            builtin_provider_manager=SimpleNamespace(get_provider=lambda _name: None),
            builtin_category_manager=SimpleNamespace(),
        )

        with pytest.raises(NotFoundException):
            service.get_provider_tool("missing-provider", "search")

    def test_get_provider_tool_should_raise_when_tool_missing(self):
        provider = SimpleNamespace(get_tool_entity=lambda _tool_name: None)
        service = BuiltinToolService(
            builtin_provider_manager=SimpleNamespace(get_provider=lambda _name: provider),
            builtin_category_manager=SimpleNamespace(),
        )

        with pytest.raises(NotFoundException):
            service.get_provider_tool("demo-provider", "missing-tool")

    def test_get_provider_tool_should_return_provider_and_tool_payload(self):
        class _ArgsSchema(BaseModel):
            city: str = Field(description="城市")

        provider_entity = SimpleNamespace(
            created_at="2026-01-01T00:00:00Z",
            model_dump=lambda exclude=None: {
                k: v
                for k, v in {
                    "name": "demo-provider",
                    "label": "Demo Provider",
                    "icon": "icon.svg",
                    "created_at": "ignored",
                }.items()
                if k not in (exclude or set())
            },
        )
        tool_entity = SimpleNamespace(
            name="weather",
            model_dump=lambda: {"name": "weather", "label": "Weather"},
        )
        provider = SimpleNamespace(
            provider_entity=provider_entity,
            get_tool_entity=lambda tool_name: tool_entity if tool_name == "weather" else None,
            get_tool=lambda _tool_name: SimpleNamespace(args_schema=_ArgsSchema),
        )
        service = BuiltinToolService(
            builtin_provider_manager=SimpleNamespace(get_provider=lambda _name: provider),
            builtin_category_manager=SimpleNamespace(),
        )

        result = service.get_provider_tool("demo-provider", "weather")

        assert result["provider"] == {"name": "demo-provider", "label": "Demo Provider"}
        assert result["name"] == "weather"
        assert result["label"] == "Weather"
        assert result["created_at"] == "2026-01-01T00:00:00Z"
        assert result["inputs"][0]["name"] == "city"

    def test_get_provider_icon_should_raise_when_provider_missing(self):
        service = BuiltinToolService(
            builtin_provider_manager=SimpleNamespace(get_provider=lambda _name: None),
            builtin_category_manager=SimpleNamespace(),
        )

        with pytest.raises(NotFoundException):
            service.get_provider_icon("missing-provider")

    def test_get_tool_inputs_should_return_empty_for_non_pydantic_schema(self):
        inputs = BuiltinToolService.get_tool_inputs(SimpleNamespace(args_schema=str))

        assert inputs == []

    def test_get_provider_icon_should_raise_when_icon_file_missing(self, tmp_path):
        app_root = tmp_path / "app" / "http"
        app_root.mkdir(parents=True)
        (
            tmp_path
            / "internal"
            / "core"
            / "tools"
            / "builtin_tools"
            / "providers"
            / "demo_provider"
            / "_asset"
        ).mkdir(parents=True)

        provider = SimpleNamespace(provider_entity=SimpleNamespace(icon="missing.png"))
        service = BuiltinToolService(
            builtin_provider_manager=SimpleNamespace(get_provider=lambda _name: provider),
            builtin_category_manager=SimpleNamespace(),
        )
        app = Flask(__name__, root_path=str(app_root))

        with app.app_context():
            with pytest.raises(NotFoundException):
                service.get_provider_icon("demo_provider")

    def test_get_categories_should_flatten_category_map(self):
        service = BuiltinToolService(
            builtin_provider_manager=SimpleNamespace(),
            builtin_category_manager=SimpleNamespace(
                get_category_map=lambda: {
                    "search": {
                        "entity": SimpleNamespace(name="搜索", category="search"),
                        "icon": "/builtin-tools/icons/search.svg",
                    }
                }
            ),
        )

        categories = service.get_categories()

        assert categories == [
            {
                "name": "搜索",
                "category": "search",
                "icon": "/builtin-tools/icons/search.svg",
            }
        ]
