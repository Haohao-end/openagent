import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from flask import Flask

from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.core.language_model.entities.model_entity import ModelFeature
from internal.entity.app_entity import AppStatus
from internal.entity.conversation_entity import InvokeFrom
from internal.entity.dataset_entity import RetrievalSource
from internal.exception import NotFoundException, ForbiddenException
from internal.model import Conversation, Message
from internal.service.web_app_service import WebAppService


class _DummyQuery:
    def __init__(self, result=None, all_result=None):
        self.result = result
        self.all_result = all_result if all_result is not None else []
        self.filter_args = ()
        self.order_by_args = ()
        self.offset_value = None
        self.limit_value = None

    def filter(self, *_args):
        self.filter_args = _args
        return self

    def one_or_none(self):
        return self.result

    def order_by(self, *_args):
        self.order_by_args = _args
        return self

    def offset(self, value):
        self.offset_value = value
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def all(self):
        return self.all_result


class _DummySession:
    def __init__(self, result=None, query_override=None):
        self.result = result
        self.query_override = query_override

    def query(self, _model):
        if self.query_override is not None:
            return self.query_override
        return _DummyQuery(result=self.result)


def _build_service(query_result=None, session=None) -> WebAppService:
    return WebAppService(
        db=SimpleNamespace(session=session or _DummySession(query_result)),
        app_config_service=SimpleNamespace(),
        conversation_service=SimpleNamespace(),
        language_model_service=SimpleNamespace(),
        retrieval_service=SimpleNamespace(),
    )


class TestWebAppService:
    def test_get_web_app_should_raise_when_app_not_found(self):
        service = _build_service(query_result=None)

        with pytest.raises(NotFoundException):
            service.get_web_app("token-not-found")

    def test_get_web_app_should_raise_when_app_not_published(self):
        draft_app = SimpleNamespace(status=AppStatus.DRAFT.value)
        service = _build_service(query_result=draft_app)

        with pytest.raises(NotFoundException):
            service.get_web_app("draft-token")

    def test_get_web_app_should_return_published_app(self):
        published_app = SimpleNamespace(status=AppStatus.PUBLISHED.value)
        service = _build_service(query_result=published_app)

        result = service.get_web_app("ok-token")

        assert result is published_app

    def test_get_web_app_info_should_map_fields_from_app_config_and_model(self, monkeypatch):
        service = _build_service()
        app = SimpleNamespace(
            id=uuid4(),
            icon="https://a.com/icon.png",
            name="WebApp",
            description="desc",
        )
        app_config = {
            "opening_statement": "hello",
            "opening_questions": ["q1", "q2"],
            "suggested_after_answer": {"enable": True},
            "text_to_speech": {"enable": True},
            "speech_to_text": {"enable": True},
            "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
        }
        llm = SimpleNamespace(features=["tool_call", "agent_thought"])
        capture = {}

        monkeypatch.setattr(service, "get_web_app", lambda _token: app)
        service.app_config_service = SimpleNamespace(
            get_app_config=lambda _app, persist_changes=True: capture.update({"persist_changes": persist_changes})
            or app_config
        )
        service.language_model_service = SimpleNamespace(load_language_model=lambda _model_config: llm)

        result = service.get_web_app_info("token")

        assert result["id"] == str(app.id)
        assert result["name"] == "WebApp"
        assert result["app_config"]["opening_statement"] == "hello"
        assert result["app_config"]["opening_questions"] == ["q1", "q2"]
        assert result["app_config"]["features"] == ["tool_call", "agent_thought"]
        assert capture["persist_changes"] is False

    def test_get_web_app_info_should_include_runtime_capabilities_when_available(
        self, monkeypatch
    ):
        service = _build_service()
        app = SimpleNamespace(
            id=uuid4(),
            icon="https://a.com/icon.png",
            name="WebApp",
            description="desc",
        )
        app_config = {
            "opening_statement": "hello",
            "opening_questions": ["q1"],
            "suggested_after_answer": {"enable": True},
            "text_to_speech": {"enable": True},
            "speech_to_text": {"enable": True},
            "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
        }
        capture = {}
        capabilities = {
            "features": ["tool_call", "image_input"],
            "image_input": {"enabled": True, "via_fallback": False},
        }

        monkeypatch.setattr(service, "get_web_app", lambda _token: app)
        service.app_config_service = SimpleNamespace(get_app_config=lambda _app: app_config)
        service.language_model_service = SimpleNamespace(
            describe_runtime_capabilities=lambda model_config, entrypoint: capture.update(
                {"model_config": model_config, "entrypoint": entrypoint}
            )
            or capabilities
        )

        result = service.get_web_app_info("token")

        assert result["app_config"]["features"] == ["tool_call", "image_input"]
        assert result["app_config"]["capabilities"] == capabilities
        assert capture == {
            "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
            "entrypoint": "web_app",
        }

    def test_get_web_app_info_should_include_runtime_capabilities_when_available(
        self, monkeypatch
    ):
        service = _build_service()
        app = SimpleNamespace(
            id=uuid4(),
            icon="https://a.com/icon.png",
            name="WebApp",
            description="desc",
        )
        app_config = {
            "opening_statement": "hello",
            "opening_questions": ["q1"],
            "suggested_after_answer": {"enable": True},
            "text_to_speech": {"enable": True},
            "speech_to_text": {"enable": True},
            "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
        }
        capture = {}
        capabilities = {
            "features": ["tool_call", "image_input"],
            "image_input": {"enabled": True, "via_fallback": False},
        }

        monkeypatch.setattr(service, "get_web_app", lambda _token: app)
        service.app_config_service = SimpleNamespace(get_app_config=lambda _app: app_config)
        service.language_model_service = SimpleNamespace(
            describe_runtime_capabilities=lambda model_config, entrypoint: capture.update(
                {"model_config": model_config, "entrypoint": entrypoint}
            )
            or capabilities
        )

        result = service.get_web_app_info("token")

        assert result["app_config"]["features"] == ["tool_call", "image_input"]
        assert result["app_config"]["capabilities"] == capabilities
        assert capture == {
            "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
            "entrypoint": "web_app",
        }

    def test_stop_web_app_chat_should_validate_token_then_set_stop_flag(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        task_id = uuid4()
        captures = {}

        def _get_web_app(token):
            captures["token"] = token
            return SimpleNamespace(id=uuid4(), status=AppStatus.PUBLISHED.value)

        monkeypatch.setattr(service, "get_web_app", _get_web_app)
        monkeypatch.setattr(
            "internal.service.web_app_service.AgentQueueManager.set_stop_flag",
            lambda stop_task_id, invoke_from, account_id: captures.update(
                {
                    "task_id": stop_task_id,
                    "invoke_from": invoke_from,
                    "account_id": account_id,
                }
            ),
        )

        service.stop_web_app_chat("public-token", task_id, account)

        assert captures["token"] == "public-token"
        assert captures["task_id"] == task_id
        assert captures["invoke_from"] == InvokeFrom.WEB_APP.value
        assert captures["account_id"] == account.id

    def test_get_conversations_should_filter_by_app_account_and_pin_status(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(id=uuid4(), status=AppStatus.PUBLISHED.value)
        conversations = [SimpleNamespace(id=uuid4()), SimpleNamespace(id=uuid4())]
        query = _DummyQuery(all_result=conversations)
        service = _build_service(session=_DummySession(query_override=query))
        monkeypatch.setattr(service, "get_web_app", lambda _token: app)

        result = service.get_conversations("public-token", True, account)

        assert result == conversations
        # 该查询应至少包含 app_id、created_by、invoke_from、is_pinned、is_deleted 五个过滤条件。
        assert len(query.filter_args) >= 5
        assert query.order_by_args
        assert query.offset_value == 0
        assert query.limit_value == 20

    def test_get_conversations_should_clamp_page_and_page_size(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(id=uuid4(), status=AppStatus.PUBLISHED.value)
        query = _DummyQuery(all_result=[])
        service = _build_service(session=_DummySession(query_override=query))
        monkeypatch.setattr(service, "get_web_app", lambda _token: app)

        _ = service.get_conversations("public-token", False, account, current_page=0, page_size=999)

        assert query.offset_value == 0
        assert query.limit_value == 100

    def test_web_app_chat_should_raise_when_conversation_not_owned_by_current_app_or_user(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(id=uuid4(), status=AppStatus.PUBLISHED.value)
        bad_conversation = SimpleNamespace(
            id=uuid4(),
            app_id=uuid4(),
            invoke_from=InvokeFrom.WEB_APP.value,
            created_by=account.id,
            is_deleted=False,
        )
        req = SimpleNamespace(
            conversation_id=SimpleNamespace(data=bad_conversation.id),
            query=SimpleNamespace(data="hello"),
            image_urls=SimpleNamespace(data=[]),
            enable_deep_thinking=SimpleNamespace(data=False),
        )

        monkeypatch.setattr(service, "get_web_app", lambda _token: app)
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: bad_conversation)

        with pytest.raises(ForbiddenException):
            list(service.web_app_chat("public-token", req, account))

    def test_web_app_chat_should_create_conversation_and_stream_events(self, monkeypatch, caplog):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(id=uuid4(), account_id=uuid4(), status=AppStatus.PUBLISHED.value)
        req = SimpleNamespace(
            conversation_id=SimpleNamespace(data=""),
            query=SimpleNamespace(data="hello"),
            image_urls=SimpleNamespace(data=["https://a.com/1.png"]),
            enable_deep_thinking=SimpleNamespace(data=True),
        )

        monkeypatch.setattr(service, "get_web_app", lambda _token: app)

        created = []
        conversation = SimpleNamespace(id=uuid4(), summary="", app_id=app.id)
        message = SimpleNamespace(id=uuid4())

        def _create(model, **kwargs):
            created.append((model, kwargs))
            if model is Conversation:
                return conversation
            if model is Message:
                return message
            raise AssertionError(f"unexpected model: {model}")

        monkeypatch.setattr(service, "create", _create)

        app_config = {
            "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
            "dialog_round": 3,
            "tools": [{"type": "builtin_tool"}],
            "datasets": [{"id": "dataset-1"}],
            "retrieval_config": {"retrieval_strategy": "semantic", "k": 2, "score": 0.6},
            "workflows": [{"id": "workflow-1"}],
            "preset_prompt": "preset",
            "long_term_memory": {"enable": True},
            "review_config": {"enable": False},
        }
        service.app_config_service = SimpleNamespace(
            get_app_config=lambda _app: app_config,
            get_langchain_tools_by_tools_config=lambda _tools: ["builtin-tool"],
            get_langchain_tools_by_workflow_ids=lambda _workflow_ids: ["workflow-tool"],
        )
        retrieval_capture = {}
        service.retrieval_service = SimpleNamespace(
            create_langchain_tool_from_search=lambda **kwargs: retrieval_capture.update(kwargs) or "dataset-tool"
        )
        llm = SimpleNamespace(
            features=[ModelFeature.TOOL_CALL.value],
            convert_to_human_message=lambda query, image_urls: f"{query}:{len(image_urls)}",
        )
        service.language_model_service = SimpleNamespace(load_language_model=lambda _model_config: llm)

        class _FakeTokenBufferMemory:
            def __init__(self, **_kwargs):
                pass

            def get_history_prompt_messages(self, message_limit):
                assert message_limit == 3
                return ["history"]

        monkeypatch.setattr("internal.service.web_app_service.TokenBufferMemory", _FakeTokenBufferMemory)

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
            ),
            AgentThought(
                id=shared_event_id,
                task_id=shared_task_id,
                event=QueueEvent.AGENT_MESSAGE,
                thought="B",
                answer="B",
                latency=0.3,
            ),
            AgentThought(
                id=uuid4(),
                task_id=shared_task_id,
                event=QueueEvent.AGENT_ACTION,
                tool="search",
                tool_input={"q": "weather"},
                observation="ok",
            ),
        ]
        captured_agent_factory = {}

        class _FakeAgent:
            def __init__(self):
                self.agent_queue_manager = SimpleNamespace(published=[])
                self.stream_closed = False

                def publish(task_id, thought):
                    assert task_id == self._task_id
                    self.agent_queue_manager.published.append(thought)

                self.agent_queue_manager.publish = publish

            def stream(self, state, config=None):
                self._task_id = state["task_id"]
                self.callback = config["callbacks"][0]
                self.callback.on_tool_start(
                    {"name": "fake-tool"},
                    "PRIVATE TOOL INPUT",
                    run_id=uuid4(),
                    parent_run_id=uuid4(),
                )
                try:
                    yield from self.agent_queue_manager.published
                    for event in stream_events:
                        yield event.model_copy(update={"task_id": state["task_id"]})
                finally:
                    self.stream_closed = True

        def _fake_create_runtime_agent(**kwargs):
            agent = _FakeAgent()
            captured_agent_factory.update(kwargs)
            captured_agent_factory["agent"] = agent
            return agent

        monkeypatch.setattr(
            "internal.service.web_app_service.AppService._create_runtime_agent",
            _fake_create_runtime_agent,
        )
        save_payload = {}
        service.conversation_service = SimpleNamespace(
            save_agent_thoughts=lambda **kwargs: save_payload.update(kwargs)
        )

        with Flask(__name__).app_context():
            events = list(service.web_app_chat("public-token", req, account))

        assert created[0][0] is Conversation
        assert created[1][0] is Message
        assert len(events) == 5
        assert events[0].startswith("event: callable_trace")
        trace_payload = json.loads(events[0].split("data:", 1)[1])
        assert trace_payload["run_type"] == "tool"
        assert trace_payload["parent_run_id"]
        assert "PRIVATE TOOL INPUT" not in events[0]
        assert events[1].startswith("event: ping")
        assert len(captured_agent_factory["tools"]) == 3
        assert captured_agent_factory["enable_deep_thinking"] is True
        assert captured_agent_factory["invoke_from"] == InvokeFrom.WEB_APP.value
        assert retrieval_capture["retrieval_source"] == RetrievalSource.APP.value
        assert len(save_payload["agent_thoughts"]) == 2
        assert save_payload["agent_thoughts"][0].thought == "AB"
        assert save_payload["agent_thoughts"][0].answer == "AB"

        save_payload.clear()
        with Flask(__name__).app_context():
            events = service.web_app_chat("public-token", req, account)
            next(events)
            next(events)
            next(events)
            events.close()

        assert captured_agent_factory["agent"].stream_closed is True
        published_count = len(captured_agent_factory["agent"].agent_queue_manager.published)
        captured_agent_factory["agent"].callback.on_tool_end(
            "PRIVATE TOOL OUTPUT",
            run_id=uuid4(),
        )
        assert len(captured_agent_factory["agent"].agent_queue_manager.published) == published_count
        assert save_payload["agent_thoughts"][0].answer == "A"

        def fail_save(**_kwargs):
            raise RuntimeError("synthetic database failure")

        service.conversation_service.save_agent_thoughts = fail_save
        with Flask(__name__).app_context():
            events = service.web_app_chat("public-token", req, account)
            next(events)
            next(events)
            next(events)
            events.close()
        assert "error_type=RuntimeError" in caplog.text

    def test_web_app_chat_should_use_existing_conversation_and_react_agent(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(id=uuid4(), account_id=uuid4(), status=AppStatus.PUBLISHED.value)
        conversation = SimpleNamespace(
            id=uuid4(),
            app_id=app.id,
            invoke_from=InvokeFrom.WEB_APP.value,
            created_by=account.id,
            is_deleted=False,
            summary="memory",
        )
        req = SimpleNamespace(
            conversation_id=SimpleNamespace(data=conversation.id),
            query=SimpleNamespace(data="hello"),
            image_urls=SimpleNamespace(data=[]),
            enable_deep_thinking=SimpleNamespace(data=False),
        )

        monkeypatch.setattr(service, "get_web_app", lambda _token: app)
        monkeypatch.setattr(service, "get", lambda _model, _id: conversation)
        create_models = []
        message = SimpleNamespace(id=uuid4())

        def _create(model, **_kwargs):
            create_models.append(model)
            return message

        monkeypatch.setattr(service, "create", _create)

        app_config = {
            "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
            "dialog_round": 1,
            "tools": [],
            "datasets": [],
            "retrieval_config": {"retrieval_strategy": "semantic", "k": 2, "score": 0.6},
            "workflows": [],
            "preset_prompt": "preset",
            "long_term_memory": {"enable": False},
            "review_config": {"enable": False},
        }
        service.app_config_service = SimpleNamespace(
            get_app_config=lambda _app: app_config,
            get_langchain_tools_by_tools_config=lambda _tools: [],
        )
        llm = SimpleNamespace(
            features=[],
            convert_to_human_message=lambda query, image_urls: f"{query}:{len(image_urls)}",
        )
        service.language_model_service = SimpleNamespace(load_language_model=lambda _model_config: llm)

        class _FakeTokenBufferMemory:
            def __init__(self, **_kwargs):
                pass

            def get_history_prompt_messages(self, message_limit):
                assert message_limit == 1
                return ["history"]

        monkeypatch.setattr("internal.service.web_app_service.TokenBufferMemory", _FakeTokenBufferMemory)

        captured_agent_factory = {}

        class _FakeAgent:
            def stream(self, _state):
                return iter(
                    [
                        AgentThought(
                            id=uuid4(),
                            task_id=uuid4(),
                            event=QueueEvent.AGENT_END,
                            answer="done",
                        )
                    ]
                )

        def _fake_create_runtime_agent(**kwargs):
            captured_agent_factory.update(kwargs)
            return _FakeAgent()

        monkeypatch.setattr(
            "internal.service.web_app_service.AppService._create_runtime_agent",
            _fake_create_runtime_agent,
        )
        save_payload = {}
        service.conversation_service = SimpleNamespace(
            save_agent_thoughts=lambda **kwargs: save_payload.update(kwargs)
        )

        with Flask(__name__).app_context():
            events = list(service.web_app_chat("public-token", req, account))

        assert create_models == [Message]
        assert events[0].startswith("event: agent_end")
        assert captured_agent_factory["enable_deep_thinking"] is False
        assert captured_agent_factory["invoke_from"] == InvokeFrom.WEB_APP.value
        assert save_payload["conversation_id"] == conversation.id
        assert save_payload["message_id"] == message.id

    def test_web_app_chat_should_attach_runtime_capabilities_when_resolution_available(
        self, monkeypatch
    ):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(id=uuid4(), account_id=uuid4(), status=AppStatus.PUBLISHED.value)
        conversation = SimpleNamespace(
            id=uuid4(),
            app_id=app.id,
            invoke_from=InvokeFrom.WEB_APP.value,
            created_by=account.id,
            is_deleted=False,
            summary="memory",
        )
        req = SimpleNamespace(
            conversation_id=SimpleNamespace(data=conversation.id),
            query=SimpleNamespace(data="请分析图片"),
            image_urls=SimpleNamespace(data=["https://a.com/1.png"]),
            enable_deep_thinking=SimpleNamespace(data=True),
        )

        monkeypatch.setattr(service, "get_web_app", lambda _token: app)
        monkeypatch.setattr(service, "get", lambda _model, _id: conversation)
        message = SimpleNamespace(id=uuid4())
        monkeypatch.setattr(service, "create", lambda _model, **_kwargs: message)

        app_config = {
            "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
            "dialog_round": 1,
            "tools": [],
            "datasets": [],
            "retrieval_config": {"retrieval_strategy": "semantic", "k": 2, "score": 0.6},
            "workflows": [],
            "preset_prompt": "preset",
            "long_term_memory": {"enable": False},
            "review_config": {"enable": False},
        }
        llm = SimpleNamespace(
            features=[ModelFeature.TOOL_CALL.value],
            convert_to_human_message=lambda query, image_urls: f"{query}:{len(image_urls)}",
        )
        capabilities = {"image_input": {"enabled": True, "via_fallback": False}}
        resolution_capture = {}
        service.app_config_service = SimpleNamespace(
            get_app_config=lambda _app: app_config,
            get_langchain_tools_by_tools_config=lambda _tools: [],
        )
        service.language_model_service = SimpleNamespace(
            resolve_runtime_language_model=lambda model_config, image_urls, entrypoint: resolution_capture.update(
                {
                    "model_config": model_config,
                    "image_urls": image_urls,
                    "entrypoint": entrypoint,
                }
            )
            or SimpleNamespace(llm=llm, capabilities=capabilities)
        )

        class _FakeTokenBufferMemory:
            def __init__(self, **_kwargs):
                pass

            def get_history_prompt_messages(self, message_limit):
                assert message_limit == 1
                return ["history"]

        monkeypatch.setattr("internal.service.web_app_service.TokenBufferMemory", _FakeTokenBufferMemory)

        captured_agent_factory = {}

        class _FakeAgent:
            def stream(self, _state):
                return iter(
                    [
                        AgentThought(
                            id=uuid4(),
                            task_id=uuid4(),
                            event=QueueEvent.AGENT_END,
                            answer="done",
                        )
                    ]
                )

        def _fake_create_runtime_agent(**kwargs):
            captured_agent_factory.update(kwargs)
            return _FakeAgent()

        monkeypatch.setattr(
            "internal.service.web_app_service.AppService._create_runtime_agent",
            _fake_create_runtime_agent,
        )
        save_payload = {}
        service.conversation_service = SimpleNamespace(
            save_agent_thoughts=lambda **kwargs: save_payload.update(kwargs)
        )

        with Flask(__name__).app_context():
            events = list(service.web_app_chat("public-token", req, account))

        assert events[0].startswith("event: agent_end")
        assert app_config["capabilities"] == capabilities
        assert captured_agent_factory["enable_deep_thinking"] is True
        assert save_payload["app_config"]["capabilities"] == capabilities
        assert resolution_capture == {
            "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
            "image_urls": req.image_urls.data,
            "entrypoint": "web_app",
        }
