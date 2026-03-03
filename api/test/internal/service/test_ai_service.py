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


class TestAIService:
    def test_python_prompt_template_should_only_require_question(self):
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", PYTHON_CODE_ASSISTANT_PROMPT),
            ("human", "{question}"),
        ])

        assert prompt_template.input_variables == ["question"]

    def test_openapi_schema_prompt_template_should_only_require_question(self):
        system_prompt = OPENAPI_SCHEMA_ASSISTANT_PROMPT.replace("{", "{{").replace("}", "}}")
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{question}"),
        ])

        assert prompt_template.input_variables == ["question"]

    def test_python_markdown_output_parser_should_keep_original_text(self):
        parser = PythonMarkdownOutputParser()

        parsed = parser.parse("```python\ndef main(params):\n    return {'output': 1}\n```")

        assert parsed == "```python\ndef main(params):\n    return {'output': 1}\n```"

    def test_python_markdown_output_parser_should_expose_type_and_diff_rules(self):
        parser = PythonMarkdownOutputParser()

        assert parser._type == "python_markdown_output"
        assert parser._diff("hello", "hello world") == " world"
        assert parser._diff("old", "new") == "new"

    def test_generate_suggested_questions_should_raise_when_message_not_owned(self, monkeypatch):
        service = AIService(
            db=SimpleNamespace(),
            conversation_service=SimpleNamespace(generate_suggested_questions=lambda _h: []),
        )
        message = SimpleNamespace(created_by=uuid4(), query="q", answer="a")
        account = SimpleNamespace(id=uuid4())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: message)

        with pytest.raises(ForbiddenException):
            service.generate_suggested_questions_from_message_id(uuid4(), account)

    def test_generate_suggested_questions_should_delegate_to_conversation_service(self, monkeypatch):
        service = AIService(
            db=SimpleNamespace(),
            conversation_service=SimpleNamespace(
                generate_suggested_questions=lambda histories: [histories, "next-question"]
            ),
        )
        account = SimpleNamespace(id=uuid4())
        message = SimpleNamespace(
            created_by=account.id,
            query="你好",
            answer="您好",
            suggested_questions=[],
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: message)
        monkeypatch.setattr(service, "update", lambda *_args, **_kwargs: None)

        result = service.generate_suggested_questions_from_message_id(uuid4(), account)

        assert "Human: 你好" in result[0]
        assert "AI: 您好" in result[0]
        assert result[1] == "next-question"

    def test_generate_suggested_questions_should_return_existing_questions_directly(self, monkeypatch):
        service = AIService(
            db=SimpleNamespace(),
            conversation_service=SimpleNamespace(
                generate_suggested_questions=lambda _histories: (_ for _ in ()).throw(
                    AssertionError("should not call llm when message already has suggestions")
                )
            ),
        )
        account = SimpleNamespace(id=uuid4())
        message = SimpleNamespace(
            created_by=account.id,
            query="你好",
            answer="您好",
            suggested_questions=["问题1", "问题2"],
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: message)
        update_calls = []
        monkeypatch.setattr(
            service,
            "update",
            lambda *_args, **_kwargs: update_calls.append("called"),
        )

        result = service.generate_suggested_questions_from_message_id(uuid4(), account)

        assert result == ["问题1", "问题2"]
        assert update_calls == []

    def test_optimize_prompt_should_stream_events(self, monkeypatch):
        class _FakePipe:
            def __or__(self, _other):
                return self

            def stream(self, _payload):
                return iter(["step-1", "step-2"])

        monkeypatch.setattr(
            "internal.service.ai_service.ChatPromptTemplate.from_messages",
            lambda _messages: _FakePipe(),
        )
        monkeypatch.setattr("internal.service.ai_service.Chat", lambda **_kwargs: object())
        monkeypatch.setattr("internal.service.ai_service.StrOutputParser", lambda: object())

        events = list(AIService.optimize_prompt("make it better"))

        assert len(events) == 2
        assert events[0].startswith("event: optimize_prompt")
        assert "step-1" in events[0]
        assert "step-2" in events[1]

    def test_code_assistant_chat_should_stream_events(self, monkeypatch):
        class _FakePipe:
            def __or__(self, _other):
                return self

            def stream(self, _payload):
                return iter(["part-1", "", "part-2"])

        monkeypatch.setattr(
            "internal.service.ai_service.ChatPromptTemplate.from_messages",
            lambda _messages: _FakePipe(),
        )
        monkeypatch.setattr("internal.service.ai_service.Chat", lambda **_kwargs: object())
        monkeypatch.setattr("internal.service.ai_service.PythonMarkdownOutputParser", lambda: object())

        events = list(AIService.code_assistant_chat("请生成代码"))

        assert len(events) == 2
        assert events[0].startswith("event: message")
        assert "part-1" in events[0]
        assert "part-2" in events[1]

    def test_openapi_schema_assistant_chat_should_stream_events(self, monkeypatch):
        class _FakePipe:
            def __or__(self, _other):
                return self

            def stream(self, _payload):
                return iter(["{\"server\":", "", "\"https://a.com\"}"])

        monkeypatch.setattr(
            "internal.service.ai_service.ChatPromptTemplate.from_messages",
            lambda _messages: _FakePipe(),
        )
        monkeypatch.setattr("internal.service.ai_service.Chat", lambda **_kwargs: object())
        monkeypatch.setattr("internal.service.ai_service.StrOutputParser", lambda: object())

        events = list(AIService.openapi_schema_assistant_chat("请生成天气schema"))

        assert len(events) == 2
        assert events[0].startswith("event: message")
        assert "server" in events[0]
        assert "https://a.com" in events[1]
