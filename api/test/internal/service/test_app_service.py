from contextlib import contextmanager
import random
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from flask import Flask

from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.entity.app_entity import AppStatus
from internal.entity.conversation_entity import InvokeFrom
from internal.entity.audio_entity import ALLOWED_AUDIO_VOICES
from internal.core.language_model.entities.model_entity import ModelParameterType
from internal.exception import FailException, ForbiddenException, NotFoundException, ValidateErrorException
from internal.model import ApiTool, Workflow, Dataset
from internal.service.app_service import AppService


class _DummyQuery:
    def __init__(self):
        self.filtered = False
        self.deleted = False

    def filter(self, *_args):
        self.filtered = True
        return self

    def order_by(self, *_args):
        return self

    def delete(self):
        self.deleted = True


class _DummySession:
    def __init__(self):
        self.query_model = None
        self.query_instance = _DummyQuery()

    def query(self, model):
        self.query_model = model
        return self.query_instance


class _DummyDB:
    def __init__(self):
        self.session = _DummySession()
        self.auto_commit_count = 0

    @contextmanager
    def auto_commit(self):
        self.auto_commit_count += 1
        yield


def _new_app_service(**kwargs) -> AppService:
    kwargs.setdefault("icon_generator_service", SimpleNamespace())
    return AppService(**kwargs)


def _build_service() -> AppService:
    return _new_app_service(
        db=_DummyDB(),
        redis_client=SimpleNamespace(),
        cos_service=SimpleNamespace(),
        retrieval_service=SimpleNamespace(),
        app_config_service=SimpleNamespace(),
        api_provider_manager=SimpleNamespace(),
        conversation_service=SimpleNamespace(),
        language_model_manager=SimpleNamespace(),
        language_model_service=SimpleNamespace(),
        builtin_provider_manager=SimpleNamespace(),
    )


class TestAppService:
    def test_create_app_should_create_app_and_draft_config(self):
        class _CreateSession:
            def __init__(self):
                self.added = []

            def add(self, obj):
                self.added.append(obj)

            def flush(self):
                if self.added and getattr(self.added[-1], "id", None) is None:
                    self.added[-1].id = uuid4()

        class _CreateDB:
            def __init__(self):
                self.session = _CreateSession()
                self.auto_commit_count = 0

            @contextmanager
            def auto_commit(self):
                self.auto_commit_count += 1
                yield

        create_db = _CreateDB()
        service = _new_app_service(
            db=create_db,
            redis_client=SimpleNamespace(),
            cos_service=SimpleNamespace(),
            retrieval_service=SimpleNamespace(),
            app_config_service=SimpleNamespace(),
            api_provider_manager=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            language_model_manager=SimpleNamespace(),
            language_model_service=SimpleNamespace(),
            builtin_provider_manager=SimpleNamespace(),
        )
        account = SimpleNamespace(id=uuid4())
        req = SimpleNamespace(
            name=SimpleNamespace(data="测试应用"),
            icon=SimpleNamespace(data="https://a.com/icon.png"),
            description=SimpleNamespace(data="应用描述"),
        )

        app = service.create_app(req, account)

        assert create_db.auto_commit_count == 1
        assert len(create_db.session.added) == 2
        assert app.account_id == account.id
        assert app.name == "测试应用"
        assert app.icon == "https://a.com/icon.png"
        assert app.description == "应用描述"
        assert app.draft_app_config_id == create_db.session.added[1].id

    def test_auto_create_app_should_create_agent_with_generated_config(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())

        class _AccountQuery:
            def get(self, account_id):
                assert account_id == account.id
                return account

        class _AutoCreateSession:
            def __init__(self):
                self.added = []

            def query(self, _model):
                return _AccountQuery()

            def add(self, obj):
                self.added.append(obj)

            def flush(self):
                if self.added and getattr(self.added[-1], "id", None) is None:
                    self.added[-1].id = uuid4()

        class _AutoCreateDB:
            def __init__(self):
                self.session = _AutoCreateSession()
                self.auto_commit_count = 0

            @contextmanager
            def auto_commit(self):
                self.auto_commit_count += 1
                yield

        class _Pipe:
            def __or__(self, _other):
                return self

        class _ParallelChain:
            def __init__(self, _mapping):
                self.mapping = _mapping

            def invoke(self, _payload):
                return {
                    "icon": "https://image.example.com/generated-icon.png",
                    "preset_prompt": "你是一个专业助手",
                }

        monkeypatch.setattr("internal.service.app_service.Chat", lambda **_kwargs: object())
        monkeypatch.setattr("internal.service.app_service.ChatPromptTemplate.from_template", lambda _template: _Pipe())
        monkeypatch.setattr("internal.service.app_service.ChatPromptTemplate.from_messages", lambda _messages: _Pipe())
        monkeypatch.setattr("internal.service.app_service.StrOutputParser", lambda: object())
        monkeypatch.setattr(
            "internal.service.app_service.DallEAPIWrapper",
            lambda **_kwargs: SimpleNamespace(run=lambda _prompt: "https://image.example.com/generated-icon.png"),
        )
        monkeypatch.setattr("internal.service.app_service.RunnableParallel", _ParallelChain)
        monkeypatch.setattr(
            "internal.service.app_service.requests.get",
            lambda _url: SimpleNamespace(status_code=200, content=b"icon-bytes"),
        )

        upload_calls = []
        cos_service = SimpleNamespace(
            upload_file=lambda file, only_image, account_obj: upload_calls.append((file.filename, only_image, account_obj))
            or SimpleNamespace(key="icons/demo.png"),
            get_file_url=lambda key: f"https://cos.example.com/{key}",
        )
        service = _new_app_service(
            db=_AutoCreateDB(),
            redis_client=SimpleNamespace(),
            cos_service=cos_service,
            retrieval_service=SimpleNamespace(),
            app_config_service=SimpleNamespace(),
            api_provider_manager=SimpleNamespace(),
            conversation_service=SimpleNamespace(
                generate_suggested_questions=lambda _histories: [" 你好 ", "", "你好", "问题2", "问题3", "问题4"]
            ),
            language_model_manager=SimpleNamespace(),
            language_model_service=SimpleNamespace(),
            builtin_provider_manager=SimpleNamespace(),
        )

        service.auto_create_app(" 智能助手 ", " 负责回答问题 ", account.id)

        assert service.db.auto_commit_count == 1
        assert len(service.db.session.added) == 2
        app_record, draft_config = service.db.session.added
        assert app_record.name == "智能助手"
        assert app_record.description == "负责回答问题"
        assert app_record.icon == "https://cos.example.com/icons/demo.png"
        assert draft_config.preset_prompt == "你是一个专业助手"
        assert draft_config.tools == AppService.AUTO_CREATE_DEFAULT_TOOLS
        assert draft_config.opening_statement == "负责回答问题"
        assert draft_config.opening_questions == ["你好", "问题2", "问题3"]
        assert draft_config.speech_to_text["enable"] is True
        assert draft_config.text_to_speech["enable"] is True
        assert upload_calls[0][0] == "icon.png"
        assert upload_calls[0][1] is True
        assert upload_calls[0][2] is account

    def test_normalize_opening_questions_should_filter_invalid_and_fill_fallback(self):
        questions = AppService._normalize_opening_questions([123, " ", "问题A", "问题A"])

        assert len(questions) == 3
        assert questions[0] == "问题A"
        assert questions[1] == "这个Agent可以帮我做什么？"
        assert questions[2] == "我先提供哪些信息会更高效？"

    def test_normalize_opening_questions_should_skip_existing_fallback_question(self):
        # 当用户问题已包含兜底题时，不应重复插入同一题目。
        questions = AppService._normalize_opening_questions(["这个Agent可以帮我做什么？"])

        assert len(questions) == 3
        assert questions[0] == "这个Agent可以帮我做什么？"
        assert questions[1] == "我先提供哪些信息会更高效？"
        assert questions[2] == "可以先给我一个示例任务吗？"

    @pytest.mark.parametrize("seed", [7, 19, 43])
    def test_normalize_opening_questions_property_should_hold_invariants_under_random_inputs(self, seed):
        fallback_questions = [
            "这个Agent可以帮我做什么？",
            "我先提供哪些信息会更高效？",
            "可以先给我一个示例任务吗？",
        ]
        candidate_values = [
            None,
            0,
            {},
            "",
            " ",
            "  ",
            "问题A",
            "问题B",
            "问题C",
            " 问题D ",
            fallback_questions[0],
            fallback_questions[1],
            fallback_questions[2],
        ]
        rng = random.Random(seed)

        for _ in range(120):
            raw_questions = [
                rng.choice(candidate_values)
                for _ in range(rng.randint(0, 12))
            ]
            normalized_questions = AppService._normalize_opening_questions(raw_questions)

            assert len(normalized_questions) == 3
            assert len(set(normalized_questions)) == 3
            assert all(
                isinstance(question, str) and question and question.strip() == question
                for question in normalized_questions
            )

            expected_prefix = []
            for raw_question in raw_questions:
                if not isinstance(raw_question, str):
                    continue
                question = raw_question.strip()
                if not question:
                    continue
                if question in expected_prefix:
                    continue
                expected_prefix.append(question)
                if len(expected_prefix) >= 3:
                    break

            assert normalized_questions[:len(expected_prefix)] == expected_prefix
            assert all(
                question in expected_prefix or question in fallback_questions
                for question in normalized_questions
            )

    def test_auto_create_app_should_fallback_opening_statement_when_description_empty(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())

        class _AccountQuery:
            def get(self, account_id):
                assert account_id == account.id
                return account

        class _AutoCreateSession:
            def __init__(self):
                self.added = []

            def query(self, _model):
                return _AccountQuery()

            def add(self, obj):
                self.added.append(obj)

            def flush(self):
                if self.added and getattr(self.added[-1], "id", None) is None:
                    self.added[-1].id = uuid4()

        class _AutoCreateDB:
            def __init__(self):
                self.session = _AutoCreateSession()

            @contextmanager
            def auto_commit(self):
                yield

        class _Pipe:
            def __or__(self, _other):
                return self

        class _ParallelChain:
            def __init__(self, _mapping):
                self.mapping = _mapping

            def invoke(self, _payload):
                return {
                    "icon": "https://image.example.com/generated-icon.png",
                    "preset_prompt": "你是一个专业助手",
                }

        monkeypatch.setattr("internal.service.app_service.Chat", lambda **_kwargs: object())
        monkeypatch.setattr("internal.service.app_service.ChatPromptTemplate.from_template", lambda _template: _Pipe())
        monkeypatch.setattr("internal.service.app_service.ChatPromptTemplate.from_messages", lambda _messages: _Pipe())
        monkeypatch.setattr("internal.service.app_service.StrOutputParser", lambda: object())
        monkeypatch.setattr(
            "internal.service.app_service.DallEAPIWrapper",
            lambda **_kwargs: SimpleNamespace(run=lambda _prompt: "https://image.example.com/generated-icon.png"),
        )
        monkeypatch.setattr("internal.service.app_service.RunnableParallel", _ParallelChain)
        monkeypatch.setattr(
            "internal.service.app_service.requests.get",
            lambda _url: SimpleNamespace(status_code=200, content=b"icon-bytes"),
        )

        service = _new_app_service(
            db=_AutoCreateDB(),
            redis_client=SimpleNamespace(),
            cos_service=SimpleNamespace(
                upload_file=lambda *_args, **_kwargs: SimpleNamespace(key="icons/demo.png"),
                get_file_url=lambda key: f"https://cos.example.com/{key}",
            ),
            retrieval_service=SimpleNamespace(),
            app_config_service=SimpleNamespace(),
            api_provider_manager=SimpleNamespace(),
            conversation_service=SimpleNamespace(
                generate_suggested_questions=lambda _histories: (_ for _ in ()).throw(RuntimeError("llm failed"))
            ),
            language_model_manager=SimpleNamespace(),
            language_model_service=SimpleNamespace(),
            builtin_provider_manager=SimpleNamespace(),
        )

        service.auto_create_app("助手", "", account.id)

        draft_config = service.db.session.added[1]
        assert draft_config.opening_statement.startswith("你好，我是助手")
        assert len(draft_config.opening_questions) == 3

    def test_auto_create_app_should_raise_when_icon_generation_failed(self, monkeypatch):
        class _Pipe:
            def __or__(self, _other):
                return self

        class _ParallelChain:
            def __init__(self, _mapping):
                self.mapping = _mapping

            def invoke(self, _payload):
                return {
                    "icon": "https://image.example.com/generated-icon.png",
                    "preset_prompt": "你是一个专业助手",
                }

        monkeypatch.setattr("internal.service.app_service.Chat", lambda **_kwargs: object())
        monkeypatch.setattr("internal.service.app_service.ChatPromptTemplate.from_template", lambda _template: _Pipe())
        monkeypatch.setattr("internal.service.app_service.ChatPromptTemplate.from_messages", lambda _messages: _Pipe())
        monkeypatch.setattr("internal.service.app_service.StrOutputParser", lambda: object())
        monkeypatch.setattr(
            "internal.service.app_service.DallEAPIWrapper",
            lambda **_kwargs: SimpleNamespace(run=lambda _prompt: "https://image.example.com/generated-icon.png"),
        )
        monkeypatch.setattr("internal.service.app_service.RunnableParallel", _ParallelChain)
        monkeypatch.setattr(
            "internal.service.app_service.requests.get",
            lambda _url: SimpleNamespace(status_code=500, content=b""),
        )
        service = _build_service()
        service.conversation_service = SimpleNamespace(generate_suggested_questions=lambda _histories: [])

        with pytest.raises(FailException):
            service.auto_create_app("助手", "x" * 2101, uuid4())

    def test_cancel_publish_should_raise_when_app_is_not_published(self, monkeypatch):
        service = _build_service()
        app = SimpleNamespace(status=AppStatus.DRAFT.value)
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)

        with pytest.raises(FailException):
            service.cancel_publish_app_config(uuid4(), SimpleNamespace(id=uuid4()))

    def test_cancel_publish_should_update_status_and_delete_joins(self, monkeypatch):
        service = _build_service()
        app = SimpleNamespace(status=AppStatus.PUBLISHED.value, app_config_id=uuid4())
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)

        update_calls = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: update_calls.append((target, kwargs)) or target,
        )

        result = service.cancel_publish_app_config(uuid4(), SimpleNamespace(id=uuid4()))

        assert result is app
        assert update_calls[0][0] is app
        assert update_calls[0][1]["status"] == AppStatus.DRAFT.value
        assert update_calls[0][1]["app_config_id"] is None
        assert update_calls[0][1]["is_public"] is False
        assert update_calls[0][1]["published_at"] is None
        assert service.db.session.query_instance.filtered is False
        assert service.db.session.query_instance.deleted is False
        assert service.db.auto_commit_count == 0

    def test_get_debug_conversation_summary_should_raise_when_long_term_memory_disabled(self, monkeypatch):
        service = _build_service()
        app = SimpleNamespace(debug_conversation=SimpleNamespace(summary="old"))
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)
        monkeypatch.setattr(
            service,
            "get_draft_app_config",
            lambda *_args, **_kwargs: {"long_term_memory": {"enable": False}},
        )

        with pytest.raises(FailException):
            service.get_debug_conversation_summary(uuid4(), SimpleNamespace(id=uuid4()))

    def test_get_debug_conversation_summary_should_return_summary_when_enabled(self, monkeypatch):
        service = _build_service()
        app = SimpleNamespace(debug_conversation=SimpleNamespace(summary="new-summary"))
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)
        monkeypatch.setattr(
            service,
            "get_draft_app_config",
            lambda *_args, **_kwargs: {"long_term_memory": {"enable": True}},
        )

        result = service.get_debug_conversation_summary(uuid4(), SimpleNamespace(id=uuid4()))

        assert result == "new-summary"

    def test_update_debug_conversation_summary_should_update_when_enabled(self, monkeypatch):
        service = _build_service()
        debug_conversation = SimpleNamespace(summary="old-summary")
        app = SimpleNamespace(debug_conversation=debug_conversation)
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)
        monkeypatch.setattr(
            service,
            "get_draft_app_config",
            lambda *_args, **_kwargs: {"long_term_memory": {"enable": True}},
        )

        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.update_debug_conversation_summary(
            uuid4(),
            "fresh-summary",
            SimpleNamespace(id=uuid4()),
        )

        assert result is debug_conversation
        assert updates[0][0] is debug_conversation
        assert updates[0][1]["summary"] == "fresh-summary"

    def test_update_debug_conversation_summary_should_raise_when_long_term_memory_disabled(self, monkeypatch):
        service = _build_service()
        app = SimpleNamespace(debug_conversation=SimpleNamespace(summary="old-summary"))
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)
        monkeypatch.setattr(
            service,
            "get_draft_app_config",
            lambda *_args, **_kwargs: {"long_term_memory": {"enable": False}},
        )

        with pytest.raises(FailException):
            service.update_debug_conversation_summary(uuid4(), "fresh-summary", SimpleNamespace(id=uuid4()))

    def test_delete_debug_conversation_should_noop_when_not_exists(self, monkeypatch):
        service = _build_service()
        app = SimpleNamespace(debug_conversation_id=None)
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)

        update_calls = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: update_calls.append((target, kwargs)) or target,
        )

        result = service.delete_debug_conversation(uuid4(), SimpleNamespace(id=uuid4()))

        assert result is app
        assert update_calls == []

    def test_delete_debug_conversation_should_clear_debug_conversation_id(self, monkeypatch):
        service = _build_service()
        app = SimpleNamespace(debug_conversation_id=uuid4())
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)

        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.delete_debug_conversation(uuid4(), SimpleNamespace(id=uuid4()))

        assert result is app
        assert updates[0][0] is app
        assert updates[0][1]["debug_conversation_id"] is None

    def test_regenerate_web_app_token_should_raise_when_not_published(self, monkeypatch):
        service = _build_service()
        app = SimpleNamespace(status=AppStatus.DRAFT.value)
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)

        with pytest.raises(FailException):
            service.regenerate_web_app_token(uuid4(), SimpleNamespace(id=uuid4()))

    def test_regenerate_web_app_token_should_update_token_when_published(self, monkeypatch):
        service = _build_service()
        app = SimpleNamespace(status=AppStatus.PUBLISHED.value, token="")
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)
        monkeypatch.setattr("internal.service.app_service.generate_random_string", lambda _length: "fixed-token-1234")

        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        token = service.regenerate_web_app_token(uuid4(), SimpleNamespace(id=uuid4()))

        assert token == "fixed-token-1234"
        assert updates[0][0] is app
        assert updates[0][1]["token"] == "fixed-token-1234"

    def test_delete_app_should_delegate_delete_and_return_app(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(id=uuid4(), account_id=account.id)
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)
        deleted = []
        monkeypatch.setattr(service, "delete", lambda target: deleted.append(target))

        result = service.delete_app(app.id, account)

        assert result is app
        assert deleted == [app]

    def test_update_app_should_delegate_update_and_return_app(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(id=uuid4(), account_id=account.id, name="old")
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.update_app(app.id, account, name="new")

        assert result is app
        assert updates == [(app, {"name": "new"})]

    def test_get_app_should_raise_when_not_found(self, monkeypatch):
        service = _build_service()
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)

        with pytest.raises(NotFoundException):
            service.get_app(uuid4(), SimpleNamespace(id=uuid4()))

    def test_get_app_should_raise_when_account_has_no_permission(self, monkeypatch):
        service = _build_service()
        monkeypatch.setattr(
            service,
            "get",
            lambda *_args, **_kwargs: SimpleNamespace(id=uuid4(), account_id=uuid4()),
        )

        with pytest.raises(ForbiddenException):
            service.get_app(uuid4(), SimpleNamespace(id=uuid4()))

    def test_get_app_should_return_record_when_owned(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(id=uuid4(), account_id=account.id)
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: app)

        result = service.get_app(app.id, account)

        assert result is app

    def test_get_draft_app_config_should_delegate_to_app_config_service(self, monkeypatch):
        service = _build_service()
        app = SimpleNamespace(id=uuid4())
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)
        service.app_config_service = SimpleNamespace(
            get_draft_app_config=lambda target_app: {"app_id": target_app.id, "preset_prompt": "prompt"}
        )

        result = service.get_draft_app_config(app.id, SimpleNamespace(id=uuid4()))

        assert result["app_id"] == app.id

    def test_copy_app_should_clone_app_and_draft_config(self, monkeypatch):
        class _Session:
            def __init__(self):
                self.added = []

            def add(self, obj):
                self.added.append(obj)

            def flush(self):
                if self.added and getattr(self.added[-1], "id", None) is None:
                    self.added[-1].id = uuid4()

        class _DB:
            def __init__(self):
                self.session = _Session()

            @contextmanager
            def auto_commit(self):
                yield

        class _FakeApp:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
                self.id = getattr(self, "id", None)

        class _FakeAppConfigVersion:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
                self.id = getattr(self, "id", None)

        service = _new_app_service(
            db=_DB(),
            redis_client=SimpleNamespace(),
            cos_service=SimpleNamespace(),
            retrieval_service=SimpleNamespace(),
            app_config_service=SimpleNamespace(),
            api_provider_manager=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            language_model_manager=SimpleNamespace(),
            language_model_service=SimpleNamespace(),
            builtin_provider_manager=SimpleNamespace(),
        )
        account = SimpleNamespace(id=uuid4())
        draft_config = SimpleNamespace(
            id=uuid4(),
            app_id=uuid4(),
            version=5,
            updated_at=None,
            created_at=None,
            dialog_round=3,
            preset_prompt="prompt",
            model_config={"provider": "openai", "model": "gpt-4o-mini"},
            tools=[],
            workflows=[],
            datasets=[],
            retrieval_config={},
            long_term_memory={"enable": True},
            opening_statement="hello",
            opening_questions=["q1"],
            speech_to_text={"enable": False},
            text_to_speech={"enable": False},
            suggested_after_answer={"enable": True},
            review_config={"enable": False},
        )
        app = SimpleNamespace(
            id=uuid4(),
            app_config_id=uuid4(),
            draft_app_config_id=draft_config.id,
            debug_conversation_id=uuid4(),
            status=AppStatus.PUBLISHED.value,
            updated_at=None,
            created_at=None,
            account_id=account.id,
            name="原应用",
            icon="https://a.com/app.png",
            description="desc",
            draft_app_config=draft_config,
        )

        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)
        monkeypatch.setattr("internal.service.app_service.App", _FakeApp)
        monkeypatch.setattr("internal.service.app_service.AppConfigVersion", _FakeAppConfigVersion)

        new_app = service.copy_app(app.id, account)

        assert new_app.status == AppStatus.DRAFT.value
        assert len(service.db.session.added) == 2
        copied_draft = service.db.session.added[1]
        assert copied_draft.app_id == new_app.id
        assert copied_draft.version == 0
        assert new_app.draft_app_config_id == copied_draft.id

    def test_get_apps_with_page_should_use_paginator(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        captures = {}

        class _Paginator:
            def __init__(self, db, req):
                captures["db"] = db
                captures["req"] = req

            def paginate(self, query):
                captures["query"] = query
                return ["app-1"]

        monkeypatch.setattr("internal.service.app_service.Paginator", _Paginator)
        req = SimpleNamespace(
            current_page=SimpleNamespace(data=1),
            page_size=SimpleNamespace(data=20),
            search_word=SimpleNamespace(data="demo"),
        )

        apps, paginator = service.get_apps_with_page(req, account)

        assert apps == ["app-1"]
        assert captures["req"] is req
        assert captures["db"] is service.db
        assert captures["query"] is not None
        assert isinstance(paginator, _Paginator)

    def test_get_apps_with_page_should_build_default_filter_when_search_word_empty(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        captured = {}

        class _Query:
            def __init__(self):
                self.filter_calls = []

            def filter(self, *args, **_kwargs):
                self.filter_calls.append(args)
                return self

            def order_by(self, *_args, **_kwargs):
                return self

        query = _Query()
        service.db.session = SimpleNamespace(query=lambda _model: query)

        class _Paginator:
            def __init__(self, db, req):
                pass

            def paginate(self, query_obj):
                captured["query"] = query_obj
                return ["app-a"]

        monkeypatch.setattr("internal.service.app_service.Paginator", _Paginator)
        req = SimpleNamespace(
            current_page=SimpleNamespace(data=1),
            page_size=SimpleNamespace(data=20),
            search_word=SimpleNamespace(data=""),
        )

        apps, _paginator = service.get_apps_with_page(req, account)

        assert apps == ["app-a"]
        assert captured["query"] is query
        assert len(query.filter_calls[0]) == 1

    def test_update_draft_app_config_should_validate_and_update_record(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        draft_record = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(id=uuid4(), draft_app_config=draft_record)
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)
        monkeypatch.setattr(
            service,
            "_validate_draft_app_config",
            lambda draft_config, _account: {"model_config": draft_config["model_config"]},
        )
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.update_draft_app_config(
            app.id,
            {"model_config": {"provider": "openai", "model": "gpt-4o-mini", "parameters": {}}},
            account,
        )

        assert result is draft_record
        assert updates[0][0] is draft_record
        assert "updated_at" in updates[0][1]
        assert updates[0][1]["model_config"]["model"] == "gpt-4o-mini"

    def test_publish_draft_app_config_should_create_runtime_config_and_history(self, monkeypatch):
        class _DeleteQuery:
            def __init__(self):
                self.deleted = False

            def filter(self, *_args):
                return self

            def delete(self):
                self.deleted = True

        class _ScalarQuery:
            def __init__(self, value):
                self.value = value

            def filter(self, *_args):
                return self

            def scalar(self):
                return self.value

        class _Session:
            def __init__(self, delete_query, scalar_query):
                self.delete_query = delete_query
                self.scalar_query = scalar_query
                self.calls = 0

            def query(self, _model):
                self.calls += 1
                return self.delete_query if self.calls == 1 else self.scalar_query

        class _DB:
            def __init__(self, session):
                self.session = session
                self.auto_commit_count = 0

            @contextmanager
            def auto_commit(self):
                self.auto_commit_count += 1
                yield

        delete_query = _DeleteQuery()
        scalar_query = _ScalarQuery(2)
        service = _new_app_service(
            db=_DB(_Session(delete_query, scalar_query)),
            redis_client=SimpleNamespace(),
            cos_service=SimpleNamespace(),
            retrieval_service=SimpleNamespace(),
            app_config_service=SimpleNamespace(),
            api_provider_manager=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            language_model_manager=SimpleNamespace(),
            language_model_service=SimpleNamespace(),
            builtin_provider_manager=SimpleNamespace(),
        )
        account = SimpleNamespace(id=uuid4())
        app_id = uuid4()
        app = SimpleNamespace(
            id=app_id,
            published_at=None,
            draft_app_config=SimpleNamespace(
                id=uuid4(),
                app_id=app_id,
                version=0,
                config_type="draft",
                updated_at=None,
                created_at=None,
                model_config={"provider": "openai", "model": "gpt-4o-mini"},
                dialog_round=3,
                preset_prompt="prompt",
                tools=[],
                workflows=[],
                datasets=[],
                retrieval_config={},
                long_term_memory={"enable": True},
                opening_statement="hello",
                opening_questions=["q1"],
                speech_to_text={"enable": False},
                text_to_speech={"enable": False},
                suggested_after_answer={"enable": True},
                review_config={"enable": False},
            ),
        )
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)
        monkeypatch.setattr(
            service,
            "get_draft_app_config",
            lambda *_args, **_kwargs: {
                "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
                "dialog_round": 3,
                "preset_prompt": "prompt",
                "tools": [
                    {
                        "type": "builtin_tool",
                        "provider": {"id": "search"},
                        "tool": {"name": "web_search", "params": {"query": "weather"}},
                    }
                ],
                "workflows": [{"id": "wf-1"}],
                "datasets": [{"id": "dataset-1"}],
                "retrieval_config": {},
                "long_term_memory": {"enable": True},
                "opening_statement": "hello",
                "opening_questions": ["q1"],
                "speech_to_text": {"enable": False},
                "text_to_speech": {"enable": False},
                "suggested_after_answer": {"enable": True},
                "review_config": {"enable": False},
            },
        )

        create_calls = []

        def _create(model, **kwargs):
            create_calls.append((model, kwargs))
            return SimpleNamespace(id=uuid4(), **kwargs)

        monkeypatch.setattr(service, "create", _create)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.publish_draft_app_config(app_id, account)

        assert result is app
        assert delete_query.deleted is True
        assert service.db.auto_commit_count == 1
        assert any(payload.get("status") == AppStatus.PUBLISHED.value for _, payload in updates)
        assert sum(1 for model, _ in create_calls if model.__name__ == "AppDatasetJoin") == 1
        history_call = [payload for model, payload in create_calls if model.__name__ == "AppConfigVersion"][0]
        assert history_call["version"] == 3

    def test_publish_draft_app_config_should_skip_public_and_published_at_when_not_shared_and_already_published(self, monkeypatch):
        class _DeleteQuery:
            def __init__(self):
                self.deleted = False

            def filter(self, *_args):
                return self

            def delete(self):
                self.deleted = True

        class _ScalarQuery:
            def __init__(self, value):
                self.value = value

            def filter(self, *_args):
                return self

            def scalar(self):
                return self.value

        class _Session:
            def __init__(self, delete_query, scalar_query):
                self.delete_query = delete_query
                self.scalar_query = scalar_query
                self.calls = 0

            def query(self, _model):
                self.calls += 1
                return self.delete_query if self.calls == 1 else self.scalar_query

        class _DB:
            def __init__(self, session):
                self.session = session
                self.auto_commit_count = 0

            @contextmanager
            def auto_commit(self):
                self.auto_commit_count += 1
                yield

        delete_query = _DeleteQuery()
        scalar_query = _ScalarQuery(5)
        service = _new_app_service(
            db=_DB(_Session(delete_query, scalar_query)),
            redis_client=SimpleNamespace(),
            cos_service=SimpleNamespace(),
            retrieval_service=SimpleNamespace(),
            app_config_service=SimpleNamespace(),
            api_provider_manager=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            language_model_manager=SimpleNamespace(),
            language_model_service=SimpleNamespace(),
            builtin_provider_manager=SimpleNamespace(),
        )
        account = SimpleNamespace(id=uuid4())
        app_id = uuid4()
        app = SimpleNamespace(
            id=app_id,
            published_at=object(),
            draft_app_config=SimpleNamespace(
                id=uuid4(),
                app_id=app_id,
                version=0,
                config_type="draft",
                updated_at=None,
                created_at=None,
                model_config={"provider": "openai", "model": "gpt-4o-mini"},
                dialog_round=3,
                preset_prompt="prompt",
                tools=[],
                workflows=[],
                datasets=[],
                retrieval_config={},
                long_term_memory={"enable": False},
                opening_statement="hello",
                opening_questions=["q1"],
                speech_to_text={"enable": False},
                text_to_speech={"enable": False},
                suggested_after_answer={"enable": True},
                review_config={"enable": False},
            ),
        )
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)
        monkeypatch.setattr(
            service,
            "get_draft_app_config",
            lambda *_args, **_kwargs: {
                "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
                "dialog_round": 3,
                "preset_prompt": "prompt",
                "tools": [],
                "workflows": [],
                "datasets": [],
                "retrieval_config": {},
                "long_term_memory": {"enable": False},
                "opening_statement": "hello",
                "opening_questions": ["q1"],
                "speech_to_text": {"enable": False},
                "text_to_speech": {"enable": False},
                "suggested_after_answer": {"enable": True},
                "review_config": {"enable": False},
            },
        )

        create_calls = []

        def _create(model, **kwargs):
            create_calls.append((model, kwargs))
            return SimpleNamespace(id=uuid4(), **kwargs)

        monkeypatch.setattr(service, "create", _create)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.publish_draft_app_config(app_id, account, share_to_square=False)

        assert result is app
        assert delete_query.deleted is True
        assert service.db.auto_commit_count == 1
        update_payload = updates[0][1]
        assert update_payload["status"] == AppStatus.PUBLISHED.value
        assert "is_public" not in update_payload
        assert "published_at" not in update_payload
        assert any(model.__name__ == "AppConfigVersion" for model, _ in create_calls)

    def test_get_publish_histories_with_page_should_use_paginator(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app_id = uuid4()
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: SimpleNamespace(id=app_id))
        captures = {}

        class _Paginator:
            def __init__(self, db, req):
                captures["db"] = db
                captures["req"] = req

            def paginate(self, query):
                captures["query"] = query
                return ["history-1"]

        monkeypatch.setattr("internal.service.app_service.Paginator", _Paginator)
        req = SimpleNamespace(current_page=SimpleNamespace(data=1), page_size=SimpleNamespace(data=20))

        histories, paginator = service.get_publish_histories_with_page(app_id, req, account)

        assert histories == ["history-1"]
        assert captures["req"] is req
        assert captures["db"] is service.db
        assert captures["query"] is not None
        assert isinstance(paginator, _Paginator)

    def test_fallback_history_to_draft_should_validate_and_update_draft_record(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        draft_record = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(id=uuid4(), draft_app_config=draft_record)
        history = SimpleNamespace(
            id=uuid4(),
            app_id=app.id,
            version=2,
            config_type="published",
            updated_at=None,
            created_at=None,
            model_config={"provider": "openai"},
            dialog_round=3,
            preset_prompt="prompt",
            tools=[],
            workflows=[],
            datasets=[],
            retrieval_config={},
            long_term_memory={"enable": True},
            opening_statement="hello",
            opening_questions=["q1"],
            speech_to_text={"enable": False},
            text_to_speech={"enable": False},
            suggested_after_answer={"enable": True},
            review_config={"enable": False},
        )
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: history)
        monkeypatch.setattr(service, "_validate_draft_app_config", lambda payload, _account: payload)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.fallback_history_to_draft(app.id, history.id, account)

        assert result is draft_record
        assert updates[0][0] is draft_record
        assert "updated_at" in updates[0][1]
        assert updates[0][1]["preset_prompt"] == "prompt"

    def test_fallback_history_to_draft_should_raise_when_history_not_found(self, monkeypatch):
        service = _build_service()
        app = SimpleNamespace(id=uuid4(), draft_app_config=SimpleNamespace(id=uuid4()))
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)

        with pytest.raises(NotFoundException):
            service.fallback_history_to_draft(app.id, uuid4(), SimpleNamespace(id=uuid4()))

    def test_debug_chat_should_stream_agent_events_and_persist_thoughts(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app_id = uuid4()
        conversation = SimpleNamespace(id=uuid4(), summary="memory")
        app = SimpleNamespace(id=app_id, debug_conversation=conversation)
        message = SimpleNamespace(id=uuid4())
        req = SimpleNamespace(
            query=SimpleNamespace(data="你好"),
            image_urls=SimpleNamespace(data=[]),
            conversation_id=SimpleNamespace(data=""),
        )
        draft_config = {
            "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
            "dialog_round": 3,
            "tools": [],
            "datasets": [],
            "workflows": [],
            "retrieval_config": {},
            "preset_prompt": "prompt",
            "long_term_memory": {"enable": True},
            "review_config": {"enable": False},
        }

        class _Event:
            def __init__(self, value):
                self.value = value

            def __eq__(self, other):
                return self.value == getattr(other, "value", other)

        class _Thought:
            def __init__(self):
                self.id = uuid4()
                self.task_id = uuid4()
                self.event = _Event("agent_message")
                self.thought = "思考"
                self.observation = ""
                self.tool = ""
                self.tool_input = ""
                self.answer = "最终答案"
                self.total_token_count = 10
                self.total_price = 0.0
                self.latency = 0.1
                self.message = [{"role": "assistant", "content": "最终答案"}]
                self.message_token_count = 5
                self.message_unit_price = 0.0
                self.message_price_unit = 0.0
                self.answer_token_count = 5
                self.answer_unit_price = 0.0
                self.answer_price_unit = 0.0

            def model_dump(self, include=None):
                payload = {
                    "event": self.event.value,
                    "thought": self.thought,
                    "observation": self.observation,
                    "tool": self.tool,
                    "tool_input": self.tool_input,
                    "answer": self.answer,
                    "total_token_count": self.total_token_count,
                    "total_price": self.total_price,
                    "latency": self.latency,
                }
                if include is None:
                    return payload
                return {key: payload[key] for key in include}

            def model_copy(self, update):
                copied = _Thought()
                copied.__dict__.update(self.__dict__)
                copied.__dict__.update(update)
                return copied

        class _Agent:
            def __init__(self, **_kwargs):
                pass

            @staticmethod
            def stream(_payload):
                return [_Thought()]

        llm = SimpleNamespace(
            features=["tool_call"],
            convert_to_human_message=lambda query, image_urls: {"query": query, "image_urls": image_urls},
        )
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)
        monkeypatch.setattr(service, "get_draft_app_config", lambda *_args, **_kwargs: draft_config)
        monkeypatch.setattr(service, "create", lambda *_args, **_kwargs: message)
        service.language_model_service = SimpleNamespace(load_language_model=lambda _config: llm)
        service.app_config_service = SimpleNamespace(
            get_langchain_tools_by_tools_config=lambda _tools: [],
            get_langchain_tools_by_workflow_ids=lambda _workflow_ids: [],
        )
        monkeypatch.setattr(
            "internal.service.app_service.TokenBufferMemory",
            lambda **_kwargs: SimpleNamespace(get_history_prompt_messages=lambda **_args: []),
        )
        monkeypatch.setattr("internal.service.app_service.FunctionCallAgent", _Agent)
        save_calls = []
        service.conversation_service = SimpleNamespace(
            save_agent_thoughts=lambda **kwargs: save_calls.append(kwargs),
        )

        events = list(service.debug_chat(app_id, req, account))

        assert len(events) == 1
        assert events[0].startswith("event: agent_message")
        assert save_calls[0]["app_id"] == app_id
        assert save_calls[0]["message_id"] == message.id
        assert len(save_calls[0]["agent_thoughts"]) == 1

    def test_debug_chat_should_attach_dataset_workflow_tools_and_merge_agent_messages(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app_id = uuid4()
        conversation = SimpleNamespace(id=uuid4(), summary="memory")
        app = SimpleNamespace(id=app_id, debug_conversation=conversation)
        message = SimpleNamespace(id=uuid4())
        dataset_id = str(uuid4())
        workflow_id = str(uuid4())
        req = SimpleNamespace(
            query=SimpleNamespace(data="你好"),
            image_urls=SimpleNamespace(data=[]),
            conversation_id=SimpleNamespace(data=""),
        )
        draft_config = {
            "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
            "dialog_round": 3,
            "tools": [],
            "datasets": [{"id": dataset_id}],
            "workflows": [{"id": workflow_id}],
            "retrieval_config": {"retrieval_strategy": "semantic", "k": 2, "score": 0.3},
            "preset_prompt": "prompt",
            "long_term_memory": {"enable": True},
            "review_config": {"enable": False},
        }

        llm = SimpleNamespace(
            features=["tool_call"],
            convert_to_human_message=lambda query, image_urls: {"query": query, "image_urls": image_urls},
        )
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)
        monkeypatch.setattr(service, "get_draft_app_config", lambda *_args, **_kwargs: draft_config)
        monkeypatch.setattr(service, "create", lambda *_args, **_kwargs: message)
        service.language_model_service = SimpleNamespace(load_language_model=lambda _config: llm)

        retrieval_capture = {}
        service.retrieval_service = SimpleNamespace(
            create_langchain_tool_from_search=lambda **kwargs: retrieval_capture.update(kwargs) or "dataset-tool"
        )
        workflow_capture = {}
        service.app_config_service = SimpleNamespace(
            get_langchain_tools_by_tools_config=lambda _tools: ["builtin-tool"],
            get_langchain_tools_by_workflow_ids=lambda workflow_ids: workflow_capture.update({"ids": workflow_ids})
            or ["workflow-tool"],
        )
        monkeypatch.setattr(
            "internal.service.app_service.TokenBufferMemory",
            lambda **_kwargs: SimpleNamespace(get_history_prompt_messages=lambda **_args: ["history"]),
        )
        monkeypatch.setattr(
            "internal.service.app_service.AgentConfig",
            lambda **kwargs: SimpleNamespace(**kwargs),
        )

        shared_event_id = uuid4()
        shared_task_id = uuid4()
        stream_events = [
            AgentThought(id=uuid4(), task_id=shared_task_id, event=QueueEvent.PING),
            AgentThought(
                id=shared_event_id,
                task_id=shared_task_id,
                event=QueueEvent.AGENT_MESSAGE,
                thought="A",
                answer="A",
                latency=0.1,
            ),
            AgentThought(
                id=shared_event_id,
                task_id=shared_task_id,
                event=QueueEvent.AGENT_MESSAGE,
                thought="B",
                answer="B",
                latency=0.2,
            ),
            AgentThought(
                id=uuid4(),
                task_id=shared_task_id,
                event=QueueEvent.AGENT_ACTION,
                tool="tool-x",
                tool_input={"q": "weather"},
                observation="ok",
                latency=0.3,
            ),
        ]
        agent_capture = {}

        class _Agent:
            def __init__(self, llm, agent_config):
                agent_capture["tools"] = agent_config.tools

            @staticmethod
            def stream(_payload):
                return iter(stream_events)

        monkeypatch.setattr("internal.service.app_service.FunctionCallAgent", _Agent)
        save_calls = []
        service.conversation_service = SimpleNamespace(
            save_agent_thoughts=lambda **kwargs: save_calls.append(kwargs),
        )

        with Flask(__name__).app_context():
            events = list(service.debug_chat(app_id, req, account))

        assert len(events) == 4
        assert events[0].startswith("event: ping")
        assert retrieval_capture["dataset_ids"] == [dataset_id]
        assert retrieval_capture["retrieval_source"] == "app"
        assert workflow_capture["ids"] == [workflow_id]
        assert len(agent_capture["tools"]) == 3
        assert len(save_calls[0]["agent_thoughts"]) == 2
        merged = [item for item in save_calls[0]["agent_thoughts"] if item.event == QueueEvent.AGENT_MESSAGE][0]
        assert merged.thought == "AB"
        assert merged.answer == "AB"

    def test_stop_debug_chat_should_validate_app_then_set_stop_flag(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app_id = uuid4()
        task_id = uuid4()
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: SimpleNamespace(id=app_id))
        captures = {}
        monkeypatch.setattr(
            "internal.service.app_service.AgentQueueManager.set_stop_flag",
            lambda _task_id, invoke_from, account_id: captures.update(
                {"task_id": _task_id, "invoke_from": invoke_from, "account_id": account_id}
            ),
        )

        service.stop_debug_chat(app_id, task_id, account)

        assert captures["task_id"] == task_id
        assert captures["account_id"] == account.id

    def test_get_debug_conversation_messages_with_page_should_paginate_and_fetch_full_messages(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(id=uuid4(), debug_conversation=SimpleNamespace(id=uuid4()))
        message = SimpleNamespace(id=uuid4())
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)

        class _Query:
            def __init__(self, all_result=None):
                self.filter_calls = []
                self._all_result = all_result if all_result is not None else []

            def filter(self, *args, **_kwargs):
                self.filter_calls.append(args)
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def options(self, *_args, **_kwargs):
                return self

            def all(self):
                return self._all_result

        id_query = _Query()
        msg_query = _Query(all_result=[message])

        class _Session:
            def query(self, model):
                return id_query if getattr(model, "key", "") == "id" else msg_query

        service.db.session = _Session()
        captures = {}

        class _Paginator:
            def __init__(self, db, req):
                captures["db"] = db
                captures["req"] = req

            def paginate(self, query):
                captures["query"] = query
                return [message.id]

        monkeypatch.setattr("internal.service.app_service.Paginator", _Paginator)
        req = SimpleNamespace(
            created_at=SimpleNamespace(data=1704067200),
            conversation_id=SimpleNamespace(data=""),
        )

        messages, paginator = service.get_debug_conversation_messages_with_page(app.id, req, account)

        assert messages == [message]
        assert captures["req"] is req
        assert captures["db"] is service.db
        assert captures["query"] is id_query
        assert isinstance(paginator, _Paginator)
        # 4 个固定过滤项 + created_at 过滤项
        assert len(id_query.filter_calls[0]) == 5

    def test_get_debug_conversation_messages_with_page_should_skip_created_at_filter_when_absent(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(id=uuid4(), debug_conversation=SimpleNamespace(id=uuid4()))
        message = SimpleNamespace(id=uuid4())
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)

        class _Query:
            def __init__(self, all_result=None):
                self.filter_calls = []
                self._all_result = all_result if all_result is not None else []

            def filter(self, *args, **_kwargs):
                self.filter_calls.append(args)
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def options(self, *_args, **_kwargs):
                return self

            def all(self):
                return self._all_result

        id_query = _Query()
        msg_query = _Query(all_result=[message])

        class _Session:
            def query(self, model):
                return id_query if getattr(model, "key", "") == "id" else msg_query

        class _Paginator:
            def __init__(self, db, req):
                pass

            def paginate(self, query):
                assert query is id_query
                return [message.id]

        service.db.session = _Session()
        monkeypatch.setattr("internal.service.app_service.Paginator", _Paginator)
        req = SimpleNamespace(
            created_at=SimpleNamespace(data=None),
            conversation_id=SimpleNamespace(data=""),
        )

        messages, _paginator = service.get_debug_conversation_messages_with_page(app.id, req, account)

        assert messages == [message]
        assert len(id_query.filter_calls[0]) == 4

    def test_get_published_config_should_return_web_app_config_view(self, monkeypatch):
        service = _build_service()
        app = SimpleNamespace(
            token_with_default="token-1",
            status=AppStatus.PUBLISHED.value,
            is_public=False,
            category="general",
        )
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)

        result = service.get_published_config(uuid4(), SimpleNamespace(id=uuid4()))

        assert result == {
            "web_app": {"token": "token-1", "status": AppStatus.PUBLISHED.value},
            "is_public": False,
            "category": "general",
        }


class _ValidationQuery:
    def __init__(self, *, one_or_none_result=None, all_result=None):
        self._one_or_none_result = one_or_none_result
        self._all_result = all_result if all_result is not None else []

    def filter(self, *_args, **_kwargs):
        return self

    def one_or_none(self):
        return self._one_or_none_result

    def all(self):
        return self._all_result


class _ValidationSession:
    def __init__(self, *, api_tool_results=None, workflow_records=None, dataset_records=None):
        self._api_tool_results = list(api_tool_results or [])
        self._workflow_records = list(workflow_records or [])
        self._dataset_records = list(dataset_records or [])

    def query(self, model):
        if model is ApiTool:
            result = self._api_tool_results.pop(0) if self._api_tool_results else None
            return _ValidationQuery(one_or_none_result=result)
        if model is Workflow:
            return _ValidationQuery(all_result=self._workflow_records)
        if model is Dataset:
            return _ValidationQuery(all_result=self._dataset_records)
        raise AssertionError(f"unexpected query model: {model}")


def _build_validation_service(session=None, builtin_lookup=None):
    service = _build_service()
    service.db = SimpleNamespace(session=session or _ValidationSession())
    service.builtin_provider_manager = SimpleNamespace(
        get_tool=builtin_lookup
        or (lambda provider_id, tool_id: object() if (provider_id, tool_id) == ("builtin-provider", "builtin-tool") else None)
    )
    model_entity = SimpleNamespace(
        parameters=[
            # 构造一个覆盖 required/options/min/max/type 分支的参数集合，验证参数清洗逻辑。
            SimpleNamespace(
                name="req_int",
                required=True,
                default=3,
                type=ModelParameterType.INT,
                options=[],
                min=1,
                max=5,
            ),
            SimpleNamespace(
                name="mode",
                required=False,
                default="auto",
                type=ModelParameterType.STRING,
                options=["auto", "manual"],
                min=None,
                max=None,
            ),
            SimpleNamespace(
                name="temp",
                required=False,
                default=0.7,
                type=ModelParameterType.FLOAT,
                options=[],
                min=0.1,
                max=1.0,
            ),
            SimpleNamespace(
                name="flag",
                required=False,
                default=False,
                type=ModelParameterType.BOOLEAN,
                options=[],
                min=None,
                max=None,
            ),
        ]
    )
    provider = SimpleNamespace(
        get_model_entity=lambda model_name: model_entity if model_name == "model-a" else None
    )
    service.language_model_manager = SimpleNamespace(
        get_provider=lambda provider_name: provider if provider_name == "provider-a" else None
    )
    return service


class TestAppServiceDraftConfigValidation:
    @pytest.mark.parametrize(
        "payload",
        [
            None,
            [],
            {"unexpected": "x"},
        ],
    )
    def test_validate_should_raise_when_payload_shape_invalid(self, payload):
        service = _build_validation_service()

        with pytest.raises(ValidateErrorException):
            service._validate_draft_app_config(payload, SimpleNamespace(id=uuid4()))

    @pytest.mark.parametrize(
        "model_config",
        [
            "not-a-dict",
            {"provider": "provider-a"},
            {"provider": "", "model": "model-a", "parameters": {}},
            {"provider": "provider-a", "model": "", "parameters": {}},
            {"provider": "missing-provider", "model": "model-a", "parameters": {}},
            {"provider": "provider-a", "model": "missing-model", "parameters": {}},
        ],
    )
    def test_validate_should_raise_when_model_config_invalid(self, model_config):
        service = _build_validation_service()

        with pytest.raises(ValidateErrorException):
            service._validate_draft_app_config({"model_config": model_config}, SimpleNamespace(id=uuid4()))

    def test_validate_should_sanitize_model_parameters_with_defaults(self):
        service = _build_validation_service()
        payload = {
            "model_config": {
                "provider": "provider-a",
                "model": "model-a",
                "parameters": {
                    "req_int": None,
                    "mode": "invalid-option",
                    "temp": 9.9,
                    "flag": "not-bool",
                    "extra": "ignored",
                },
            }
        }

        validated = service._validate_draft_app_config(payload, SimpleNamespace(id=uuid4()))
        parameters = validated["model_config"]["parameters"]

        assert parameters["req_int"] == 3
        assert parameters["mode"] == "auto"
        assert parameters["temp"] == 0.7
        assert parameters["flag"] is False
        assert "extra" not in parameters

    def test_validate_should_reset_required_parameter_when_type_mismatched(self):
        service = _build_validation_service()
        payload = {
            "model_config": {
                "provider": "provider-a",
                "model": "model-a",
                "parameters": {
                    "req_int": "not-int",
                    "mode": "auto",
                    "temp": 0.8,
                    "flag": True,
                },
            }
        }

        validated = service._validate_draft_app_config(payload, SimpleNamespace(id=uuid4()))

        assert validated["model_config"]["parameters"]["req_int"] == 3

    def test_validate_should_keep_required_and_optional_values_when_types_valid(self):
        service = _build_validation_service()
        payload = {
            "model_config": {
                "provider": "provider-a",
                "model": "model-a",
                "parameters": {
                    "req_int": 4,
                    "mode": None,
                    "temp": 0.8,
                    "flag": True,
                },
            }
        }

        validated = service._validate_draft_app_config(payload, SimpleNamespace(id=uuid4()))
        parameters = validated["model_config"]["parameters"]

        assert parameters["req_int"] == 4
        assert parameters["mode"] == "auto"
        assert parameters["temp"] == 0.8
        assert parameters["flag"] is True

    def test_validate_should_filter_tools_workflows_and_datasets(self):
        workflow_ok = uuid4()
        workflow_skip = uuid4()
        dataset_ok = uuid4()
        dataset_skip = uuid4()
        session = _ValidationSession(
            api_tool_results=[SimpleNamespace(id=uuid4()), None],
            workflow_records=[SimpleNamespace(id=workflow_ok)],
            dataset_records=[SimpleNamespace(id=dataset_ok)],
        )
        service = _build_validation_service(session=session)
        account = SimpleNamespace(id=uuid4())
        payload = {
            "tools": [
                {
                    "type": "builtin_tool",
                    "provider_id": "builtin-provider",
                    "tool_id": "builtin-tool",
                    "params": {"k": 1},
                },
                {
                    "type": "builtin_tool",
                    "provider_id": "builtin-provider",
                    "tool_id": "missing-tool",
                    "params": {},
                },
                {
                    "type": "api_tool",
                    "provider_id": "api-provider",
                    "tool_id": "api-ok",
                    "params": {},
                },
                {
                    "type": "api_tool",
                    "provider_id": "api-provider",
                    "tool_id": "api-missing",
                    "params": {},
                },
            ],
            "workflows": [str(workflow_ok), str(workflow_skip)],
            "datasets": [str(dataset_ok), str(dataset_skip)],
        }

        validated = service._validate_draft_app_config(payload, account)

        assert len(validated["tools"]) == 2
        assert validated["tools"][0]["tool_id"] == "builtin-tool"
        assert validated["tools"][1]["tool_id"] == "api-ok"
        assert validated["workflows"] == [str(workflow_ok)]
        assert validated["datasets"] == [str(dataset_ok)]

    @pytest.mark.parametrize(
        "payload",
        [
            {
                "tools": [
                    {"type": "builtin_tool", "provider_id": "builtin-provider", "tool_id": "builtin-tool", "params": {}},
                    {"type": "builtin_tool", "provider_id": "builtin-provider", "tool_id": "builtin-tool", "params": {}},
                ]
            },
            {"workflows": [str(uuid4()), str(uuid4())[:8]]},
            {"workflows": [str(uuid4()), str(uuid4()), str(uuid4()), str(uuid4()), str(uuid4()), str(uuid4())]},
            {"datasets": [str(uuid4()), str(uuid4())[:8]]},
            {"datasets": [str(uuid4()), str(uuid4()), str(uuid4()), str(uuid4()), str(uuid4()), str(uuid4())]},
        ],
    )
    def test_validate_should_raise_for_invalid_tools_workflows_or_datasets(self, payload):
        service = _build_validation_service()

        with pytest.raises(ValidateErrorException):
            service._validate_draft_app_config(payload, SimpleNamespace(id=uuid4()))

    def test_validate_should_raise_for_duplicate_workflows_and_datasets(self):
        service = _build_validation_service()
        repeated_workflow_id = str(uuid4())
        repeated_dataset_id = str(uuid4())

        with pytest.raises(ValidateErrorException):
            service._validate_draft_app_config(
                {"workflows": [repeated_workflow_id, repeated_workflow_id]},
                SimpleNamespace(id=uuid4()),
            )

        with pytest.raises(ValidateErrorException):
            service._validate_draft_app_config(
                {"datasets": [repeated_dataset_id, repeated_dataset_id]},
                SimpleNamespace(id=uuid4()),
            )

    def test_validate_should_accept_complete_valid_misc_config(self):
        service = _build_validation_service()
        payload = {
            "dialog_round": 10,
            "preset_prompt": "你是一个助手",
            "retrieval_config": {"retrieval_strategy": "hybrid", "k": 3, "score": 0.7},
            "long_term_memory": {"enable": True},
            "opening_statement": "你好，我可以帮你分析问题。",
            "opening_questions": ["你能做什么", "如何开始"],
            "speech_to_text": {"enable": False},
            "text_to_speech": {"enable": True, "voice": ALLOWED_AUDIO_VOICES[0], "auto_play": True},
            "suggested_after_answer": {"enable": True},
            "review_config": {
                "enable": True,
                "keywords": ["敏感词"],
                "inputs_config": {"enable": True, "preset_response": "输入不合规"},
                "outputs_config": {"enable": False},
            },
        }

        validated = service._validate_draft_app_config(payload, SimpleNamespace(id=uuid4()))

        assert validated["dialog_round"] == 10
        assert validated["retrieval_config"]["retrieval_strategy"] == "hybrid"
        assert validated["text_to_speech"]["voice"] == ALLOWED_AUDIO_VOICES[0]
        assert validated["review_config"]["inputs_config"]["enable"] is True

    def test_validate_should_accept_review_config_when_disabled(self):
        service = _build_validation_service()
        payload = {
            "review_config": {
                "enable": False,
                "keywords": [],
                "inputs_config": {"enable": False, "preset_response": ""},
                "outputs_config": {"enable": False},
            }
        }

        validated = service._validate_draft_app_config(payload, SimpleNamespace(id=uuid4()))

        assert validated["review_config"]["enable"] is False
        assert validated["review_config"]["keywords"] == []

    @pytest.mark.parametrize(
        "payload",
        [
            {"dialog_round": -1},
            {"preset_prompt": 123},
            {"retrieval_config": {"retrieval_strategy": "semantic", "k": 3, "score": 1}},
            {"long_term_memory": {"enable": "yes"}},
            {"opening_statement": 123},
            {"opening_questions": ["ok", 1]},
            {"speech_to_text": {"enable": "yes"}},
            {"text_to_speech": {"enable": True, "voice": "invalid-voice", "auto_play": True}},
            {"suggested_after_answer": {"enable": "yes"}},
            {
                "review_config": {
                    "enable": True,
                    "keywords": ["敏感词"],
                    "inputs_config": {"enable": False, "preset_response": ""},
                    "outputs_config": {"enable": False},
                }
            },
            {
                "review_config": {
                    "enable": True,
                    "keywords": ["敏感词"],
                    "inputs_config": {"enable": True, "preset_response": "   "},
                    "outputs_config": {"enable": True},
                }
            },
        ],
    )
    def test_validate_should_raise_for_invalid_misc_config(self, payload):
        service = _build_validation_service()

        with pytest.raises(ValidateErrorException):
            service._validate_draft_app_config(payload, SimpleNamespace(id=uuid4()))

    @pytest.mark.parametrize(
        "payload",
        [
            {"tools": "bad"},
            {
                "tools": [
                    {"type": "builtin_tool", "provider_id": "p", "tool_id": f"t{i}", "params": {}}
                    for i in range(6)
                ]
            },
            {"tools": [None]},
            {"tools": [{"type": "builtin_tool"}]},
            {"tools": [{"type": "unknown", "provider_id": "p", "tool_id": "t", "params": {}}]},
            {"tools": [{"type": "builtin_tool", "provider_id": "", "tool_id": "t", "params": {}}]},
            {"tools": [{"type": "builtin_tool", "provider_id": "p", "tool_id": "t", "params": []}]},
            {"workflows": "bad"},
            {"datasets": "bad"},
            {"retrieval_config": []},
            {"retrieval_config": {"retrieval_strategy": "semantic", "k": 2}},
            {"retrieval_config": {"retrieval_strategy": "invalid", "k": 2, "score": 0.3}},
            {"retrieval_config": {"retrieval_strategy": "semantic", "k": 11, "score": 0.3}},
            {"long_term_memory": []},
            {"opening_questions": ["q1", "q2", "q3", "q4"]},
            {"speech_to_text": []},
            {"text_to_speech": []},
            {"suggested_after_answer": []},
            {"review_config": []},
            {"review_config": {"enable": True}},
            {
                "review_config": {
                    "enable": "yes",
                    "keywords": ["敏感词"],
                    "inputs_config": {"enable": False, "preset_response": ""},
                    "outputs_config": {"enable": True},
                }
            },
            {
                "review_config": {
                    "enable": True,
                    "keywords": [],
                    "inputs_config": {"enable": False, "preset_response": ""},
                    "outputs_config": {"enable": True},
                }
            },
            {
                "review_config": {
                    "enable": True,
                    "keywords": ["ok", 1],
                    "inputs_config": {"enable": False, "preset_response": ""},
                    "outputs_config": {"enable": True},
                }
            },
            {
                "review_config": {
                    "enable": True,
                    "keywords": ["ok"],
                    "inputs_config": {},
                    "outputs_config": {"enable": True},
                }
            },
            {
                "review_config": {
                    "enable": True,
                    "keywords": ["ok"],
                    "inputs_config": {"enable": False, "preset_response": ""},
                    "outputs_config": {},
                }
            },
        ],
    )
    def test_validate_should_raise_for_additional_invalid_branch_inputs(self, payload):
        service = _build_validation_service()

        with pytest.raises(ValidateErrorException):
            service._validate_draft_app_config(payload, SimpleNamespace(id=uuid4()))

    def test_create_app_with_auto_generated_icon(self, monkeypatch):
        """测试创建应用时自动生成图标"""
        class _CreateSession:
            def __init__(self):
                self.added = []

            def add(self, obj):
                self.added.append(obj)

            def flush(self):
                if self.added and getattr(self.added[-1], "id", None) is None:
                    self.added[-1].id = uuid4()

        class _CreateDB:
            def __init__(self):
                self.session = _CreateSession()
                self.auto_commit_count = 0

            @contextmanager
            def auto_commit(self):
                self.auto_commit_count += 1
                yield

        # Mock icon generator service
        mock_icon_generator = SimpleNamespace(
            generate_icon=Mock(return_value="https://cos.com/generated-icon.png")
        )

        create_db = _CreateDB()
        service = _new_app_service(
            db=create_db,
            redis_client=SimpleNamespace(),
            cos_service=SimpleNamespace(),
            retrieval_service=SimpleNamespace(),
            app_config_service=SimpleNamespace(),
            api_provider_manager=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            language_model_manager=SimpleNamespace(),
            language_model_service=SimpleNamespace(),
            builtin_provider_manager=SimpleNamespace(),
            icon_generator_service=mock_icon_generator,
        )

        account = SimpleNamespace(id=uuid4())
        req = SimpleNamespace(
            name=SimpleNamespace(data="测试应用"),
            icon=SimpleNamespace(data=""),  # 空图标，触发自动生成
            description=SimpleNamespace(data="应用描述"),
        )

        app = service.create_app(req, account)

        assert create_db.auto_commit_count == 1
        assert app.icon == "https://cos.com/generated-icon.png"
        mock_icon_generator.generate_icon.assert_called_once_with(
            name="测试应用",
            description="应用描述"
        )

    def test_create_app_with_icon_generation_failure_uses_default(self, monkeypatch):
        """测试图标生成失败时使用默认图标"""
        class _CreateSession:
            def __init__(self):
                self.added = []

            def add(self, obj):
                self.added.append(obj)

            def flush(self):
                if self.added and getattr(self.added[-1], "id", None) is None:
                    self.added[-1].id = uuid4()

        class _CreateDB:
            def __init__(self):
                self.session = _CreateSession()
                self.auto_commit_count = 0

            @contextmanager
            def auto_commit(self):
                self.auto_commit_count += 1
                yield

        # Mock icon generator service that fails
        mock_icon_generator = SimpleNamespace(
            generate_icon=Mock(side_effect=Exception("生成失败"))
        )

        create_db = _CreateDB()
        service = _new_app_service(
            db=create_db,
            redis_client=SimpleNamespace(),
            cos_service=SimpleNamespace(),
            retrieval_service=SimpleNamespace(),
            app_config_service=SimpleNamespace(),
            api_provider_manager=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            language_model_manager=SimpleNamespace(),
            language_model_service=SimpleNamespace(),
            builtin_provider_manager=SimpleNamespace(),
            icon_generator_service=mock_icon_generator,
        )

        account = SimpleNamespace(id=uuid4())
        req = SimpleNamespace(
            name=SimpleNamespace(data="测试应用"),
            icon=SimpleNamespace(data=None),  # None 图标，触发自动生成
            description=SimpleNamespace(data="应用描述"),
        )

        app = service.create_app(req, account)

        assert create_db.auto_commit_count == 1
        assert app.icon == "https://picsum.photos/400"  # 使用默认兜底图标

    def test_regenerate_icon_success(self):
        """测试重新生成图标成功"""
        app_id = uuid4()
        account_id = uuid4()
        app = SimpleNamespace(
            id=app_id,
            account_id=account_id,
            name="测试应用",
            description="应用描述",
            icon="https://old-icon.com/icon.png"
        )

        # Mock icon generator service
        mock_icon_generator = SimpleNamespace(
            generate_icon=Mock(return_value="https://cos.com/new-icon.png")
        )

        service = _new_app_service(
            db=_DummyDB(),
            redis_client=SimpleNamespace(),
            cos_service=SimpleNamespace(),
            retrieval_service=SimpleNamespace(),
            app_config_service=SimpleNamespace(),
            api_provider_manager=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            language_model_manager=SimpleNamespace(),
            language_model_service=SimpleNamespace(),
            builtin_provider_manager=SimpleNamespace(),
            icon_generator_service=mock_icon_generator,
        )

        # Mock get_app method
        service.get_app = Mock(return_value=app)
        service.update = Mock()

        account = SimpleNamespace(id=account_id)
        icon_url = service.regenerate_icon(app_id, account)

        assert icon_url == "https://cos.com/new-icon.png"
        mock_icon_generator.generate_icon.assert_called_once_with(
            name="测试应用",
            description="应用描述"
        )
        service.update.assert_called_once_with(app, icon="https://cos.com/new-icon.png")

    def test_regenerate_icon_failure(self):
        """测试重新生成图标失败"""
        app_id = uuid4()
        account_id = uuid4()
        app = SimpleNamespace(
            id=app_id,
            account_id=account_id,
            name="测试应用",
            description="应用描述",
            icon="https://old-icon.com/icon.png"
        )

        # Mock icon generator service that fails
        mock_icon_generator = SimpleNamespace(
            generate_icon=Mock(side_effect=Exception("生成失败"))
        )

        service = _new_app_service(
            db=_DummyDB(),
            redis_client=SimpleNamespace(),
            cos_service=SimpleNamespace(),
            retrieval_service=SimpleNamespace(),
            app_config_service=SimpleNamespace(),
            api_provider_manager=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            language_model_manager=SimpleNamespace(),
            language_model_service=SimpleNamespace(),
            builtin_provider_manager=SimpleNamespace(),
            icon_generator_service=mock_icon_generator,
        )

        # Mock get_app method
        service.get_app = Mock(return_value=app)

        account = SimpleNamespace(id=account_id)

        with pytest.raises(Exception) as exc_info:
            service.regenerate_icon(app_id, account)

        assert "生成失败" in str(exc_info.value)

    def test_resolve_debug_conversation_should_raise_when_conversation_invalid(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(id=uuid4(), debug_conversation_id=None, debug_conversation=None)
        invalid_conversation = SimpleNamespace(
            id=uuid4(),
            app_id=uuid4(),
            created_by=account.id,
            is_deleted=False,
            invoke_from=InvokeFrom.DEBUGGER.value,
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: invalid_conversation)

        with pytest.raises(NotFoundException):
            service._resolve_debug_conversation(
                app=app,
                account=account,
                conversation_id=uuid4(),
                sync_active=False,
            )

    def test_resolve_debug_conversation_should_sync_active_debug_pointer(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(id=uuid4(), debug_conversation_id=uuid4(), debug_conversation=None)
        conversation = SimpleNamespace(
            id=uuid4(),
            app_id=app.id,
            created_by=account.id,
            is_deleted=False,
            invoke_from=InvokeFrom.DEBUGGER.value,
        )
        updates = []
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: conversation)
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service._resolve_debug_conversation(
            app=app,
            account=account,
            conversation_id=conversation.id,
            sync_active=True,
        )

        assert result is conversation
        assert updates == [(app, {"debug_conversation_id": conversation.id})]

    def test_resolve_debug_conversation_should_skip_update_when_pointer_already_synced(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        conversation_id = uuid4()
        app = SimpleNamespace(id=uuid4(), debug_conversation_id=conversation_id, debug_conversation=None)
        conversation = SimpleNamespace(
            id=conversation_id,
            app_id=app.id,
            created_by=account.id,
            is_deleted=False,
            invoke_from=InvokeFrom.DEBUGGER.value,
        )
        updates = []
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: conversation)
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service._resolve_debug_conversation(
            app=app,
            account=account,
            conversation_id=conversation.id,
            sync_active=True,
        )

        assert result is conversation
        assert updates == []

    def test_generate_icon_preview_should_return_icon_url(self):
        mock_icon_generator = SimpleNamespace(
            generate_icon=Mock(return_value="https://cos.com/preview-icon.png"),
        )
        service = _new_app_service(
            db=_DummyDB(),
            redis_client=SimpleNamespace(),
            cos_service=SimpleNamespace(),
            retrieval_service=SimpleNamespace(),
            app_config_service=SimpleNamespace(),
            api_provider_manager=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            language_model_manager=SimpleNamespace(),
            language_model_service=SimpleNamespace(),
            builtin_provider_manager=SimpleNamespace(),
            icon_generator_service=mock_icon_generator,
        )

        icon_url = service.generate_icon_preview(name="预览应用", description="应用描述")

        assert icon_url == "https://cos.com/preview-icon.png"
        mock_icon_generator.generate_icon.assert_called_once_with(
            name="预览应用",
            description="应用描述",
        )

    def test_generate_icon_preview_should_raise_when_generator_failed(self):
        mock_icon_generator = SimpleNamespace(
            generate_icon=Mock(side_effect=RuntimeError("preview failed")),
        )
        service = _new_app_service(
            db=_DummyDB(),
            redis_client=SimpleNamespace(),
            cos_service=SimpleNamespace(),
            retrieval_service=SimpleNamespace(),
            app_config_service=SimpleNamespace(),
            api_provider_manager=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            language_model_manager=SimpleNamespace(),
            language_model_service=SimpleNamespace(),
            builtin_provider_manager=SimpleNamespace(),
            icon_generator_service=mock_icon_generator,
        )

        with pytest.raises(RuntimeError, match="preview failed"):
            service.generate_icon_preview(name="预览应用", description="应用描述")

    def test_publish_draft_app_config_should_not_force_public_when_share_to_square_disabled(self, monkeypatch):
        class _DeleteQuery:
            def filter(self, *_args):
                return self

            @staticmethod
            def delete():
                return None

        class _ScalarQuery:
            def filter(self, *_args):
                return self

            @staticmethod
            def scalar():
                return 1

        class _Session:
            def __init__(self):
                self.calls = 0

            def query(self, _model):
                self.calls += 1
                if self.calls == 1:
                    return _DeleteQuery()
                return _ScalarQuery()

        class _DB:
            def __init__(self):
                self.session = _Session()

            @staticmethod
            @contextmanager
            def auto_commit():
                yield

        service = _new_app_service(
            db=_DB(),
            redis_client=SimpleNamespace(),
            cos_service=SimpleNamespace(),
            retrieval_service=SimpleNamespace(),
            app_config_service=SimpleNamespace(),
            api_provider_manager=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            language_model_manager=SimpleNamespace(),
            language_model_service=SimpleNamespace(),
            builtin_provider_manager=SimpleNamespace(),
            icon_generator_service=SimpleNamespace(),
        )

        app_id = uuid4()
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(
            id=app_id,
            published_at="already-published",
            draft_app_config=SimpleNamespace(
                id=uuid4(),
                app_id=app_id,
                version=0,
                config_type="draft",
                updated_at=None,
                created_at=None,
                model_config={"provider": "openai", "model": "gpt-4o-mini"},
                dialog_round=3,
                preset_prompt="prompt",
                tools=[],
                workflows=[],
                datasets=[],
                retrieval_config={},
                long_term_memory={"enable": True},
                opening_statement="hello",
                opening_questions=["q1"],
                speech_to_text={"enable": False},
                text_to_speech={"enable": False},
                suggested_after_answer={"enable": True},
                review_config={"enable": False},
            ),
        )
        monkeypatch.setattr(service, "get_app", lambda *_args, **_kwargs: app)
        monkeypatch.setattr(
            service,
            "get_draft_app_config",
            lambda *_args, **_kwargs: {
                "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
                "dialog_round": 3,
                "preset_prompt": "prompt",
                "tools": [],
                "workflows": [],
                "datasets": [],
                "retrieval_config": {},
                "long_term_memory": {"enable": True},
                "opening_statement": "hello",
                "opening_questions": ["q1"],
                "speech_to_text": {"enable": False},
                "text_to_speech": {"enable": False},
                "suggested_after_answer": {"enable": True},
                "review_config": {"enable": False},
            },
        )
        monkeypatch.setattr(service, "create", lambda _model, **kwargs: SimpleNamespace(id=uuid4(), **kwargs))
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        service.publish_draft_app_config(app_id, account, share_to_square=False)

        update_payload = updates[0][1]
        assert "is_public" not in update_payload
        assert "published_at" not in update_payload
