import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from flask import Flask

from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.core.language_model.entities.model_entity import ModelFeature
from internal.entity.app_entity import AppStatus
from internal.entity.conversation_entity import InvokeFrom
from internal.exception import ForbiddenException, NotFoundException
from internal.model import Conversation, EndUser, Message
from internal.service.openapi_service import OpenAPIService


def _build_req(app_id, end_user_id: str = "", conversation_id: str = ""):
    return SimpleNamespace(
        app_id=SimpleNamespace(data=str(app_id)),
        end_user_id=SimpleNamespace(data=end_user_id),
        conversation_id=SimpleNamespace(data=conversation_id),
        query=SimpleNamespace(data="hello"),
        image_urls=SimpleNamespace(data=[]),
        stream=SimpleNamespace(data=False),
    )


def _build_service() -> OpenAPIService:
    return OpenAPIService(
        db=SimpleNamespace(),
        app_service=SimpleNamespace(),
        retrieval_service=SimpleNamespace(),
        app_config_service=SimpleNamespace(),
        conversation_service=SimpleNamespace(),
        language_model_service=SimpleNamespace(),
    )


class TestOpenAPIService:
    def test_chat_should_raise_not_found_when_app_not_published(self):
        service = _build_service()
        app = SimpleNamespace(id=uuid4(), status=AppStatus.DRAFT.value)
        service.app_service = SimpleNamespace(get_app=lambda _app_id, _account: app)

        with pytest.raises(NotFoundException):
            service.chat(_build_req(app.id), SimpleNamespace(id=uuid4()))

    def test_chat_should_raise_forbidden_when_end_user_invalid(self, monkeypatch):
        service = _build_service()
        app = SimpleNamespace(id=uuid4(), status=AppStatus.PUBLISHED.value)
        service.app_service = SimpleNamespace(get_app=lambda _app_id, _account: app)
        monkeypatch.setattr(service, "get", lambda _model, _id: None)

        with pytest.raises(ForbiddenException):
            service.chat(
                _build_req(app.id, end_user_id=str(uuid4())),
                SimpleNamespace(id=uuid4()),
            )

    def test_chat_should_raise_forbidden_when_conversation_not_owned(self, monkeypatch):
        service = _build_service()
        app = SimpleNamespace(id=uuid4(), status=AppStatus.PUBLISHED.value)
        end_user = SimpleNamespace(id=uuid4(), app_id=app.id)
        bad_conversation = SimpleNamespace(
            app_id=uuid4(),
            invoke_from=InvokeFrom.SERVICE_API.value,
            created_by=end_user.id,
        )
        service.app_service = SimpleNamespace(get_app=lambda _app_id, _account: app)

        def fake_get(model, _id):
            if model is EndUser:
                return end_user
            if model is Conversation:
                return bad_conversation
            return None

        monkeypatch.setattr(service, "get", fake_get)

        with pytest.raises(ForbiddenException):
            service.chat(
                _build_req(
                    app.id,
                    end_user_id=str(end_user.id),
                    conversation_id=str(uuid4()),
                ),
                SimpleNamespace(id=uuid4()),
            )

    def test_chat_should_return_block_response_when_stream_disabled(self, monkeypatch):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(id=uuid4(), status=AppStatus.PUBLISHED.value)
        req = _build_req(app.id)
        service.app_service = SimpleNamespace(get_app=lambda _app_id, _account: app)

        app_config = {
            "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
            "dialog_round": 3,
            "tools": [],
            "datasets": [],
            "retrieval_config": {"retrieval_strategy": "semantic", "k": 2, "score": 0.5},
            "workflows": [],
            "preset_prompt": "preset",
            "long_term_memory": {"enable": True},
            "review_config": {"enable": False},
        }
        capture = {}
        service.app_config_service = SimpleNamespace(
            get_app_config=lambda _app, persist_changes=True: capture.update({"persist_changes": persist_changes})
            or app_config,
            get_langchain_tools_by_tools_config=lambda _tools: [],
        )

        created_records = []
        end_user_id = uuid4()
        conversation_id = uuid4()
        message_id = uuid4()

        def fake_create(model, **kwargs):
            created_records.append((model, kwargs))
            if model is EndUser:
                return SimpleNamespace(id=end_user_id, app_id=app.id)
            if model is Conversation:
                return SimpleNamespace(
                    id=conversation_id,
                    app_id=app.id,
                    created_by=end_user_id,
                    invoke_from=InvokeFrom.SERVICE_API.value,
                    summary="",
                )
            if model is Message:
                return SimpleNamespace(id=message_id)
            raise AssertionError(f"unexpected model: {model}")

        monkeypatch.setattr(service, "create", fake_create)

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
                return ["history-message"]

        monkeypatch.setattr("internal.service.openapi_service.TokenBufferMemory", _FakeTokenBufferMemory)

        agent_thought = AgentThought(
            id=uuid4(),
            task_id=uuid4(),
            event=QueueEvent.AGENT_MESSAGE,
            thought="thinking",
            answer="answer",
            latency=0.2,
        )
        artifact_thought = AgentThought(
            id=uuid4(),
            task_id=uuid4(),
            event=QueueEvent.DEEP_ARTIFACT_CREATED,
            thought="trip-plan.docx",
            observation="https://cos.example.com/trip-plan.docx",
            tool="artifact",
            tool_input={
                "artifact": {
                    "name": "trip-plan.docx",
                    "url": "https://cos.example.com/trip-plan.docx",
                    "extension": "docx",
                }
            },
            latency=0.1,
        )
        artifact_thought = AgentThought(
            id=uuid4(),
            task_id=uuid4(),
            event=QueueEvent.DEEP_ARTIFACT_CREATED,
            thought="trip-plan.docx",
            observation="https://cos.example.com/trip-plan.docx",
            tool="artifact",
            tool_input={
                "artifact": {
                    "name": "trip-plan.docx",
                    "url": "https://cos.example.com/trip-plan.docx",
                    "extension": "docx",
                }
            },
            latency=0.1,
        )
        captured_state = {}

        class _FakeFunctionCallAgent:
            def __init__(self, llm, agent_config):
                self._llm = llm
                self._agent_config = agent_config

            def invoke(self, agent_state):
                captured_state["agent_state"] = agent_state
                return SimpleNamespace(
                    answer="final-answer",
                    latency=0.6,
                    agent_thoughts=[agent_thought],
                )

        monkeypatch.setattr("internal.service.openapi_service.FunctionCallAgent", _FakeFunctionCallAgent)
        save_payload = {}
        service.conversation_service = SimpleNamespace(
            save_agent_thoughts=lambda **kwargs: save_payload.update(kwargs)
        )

        response = service.chat(req, account)

        assert response.data["id"] == str(message_id)
        assert response.data["end_user_id"] == str(end_user_id)
        assert response.data["conversation_id"] == str(conversation_id)
        assert response.data["answer"] == "final-answer"
        assert created_records[0][0] is EndUser
        assert created_records[1][0] is Conversation
        assert created_records[2][0] is Message
        assert captured_state["agent_state"]["history"] == ["history-message"]
        assert save_payload["message_id"] == message_id
        assert len(save_payload["agent_thoughts"]) == 1
        assert capture["persist_changes"] is False

    def test_chat_should_return_runtime_capabilities_and_parts_when_resolution_available(
        self, monkeypatch
    ):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(id=uuid4(), status=AppStatus.PUBLISHED.value)
        req = _build_req(app.id)
        req.image_urls.data = ["https://a.com/1.png"]
        service.app_service = SimpleNamespace(get_app=lambda _app_id, _account: app)

        app_config = {
            "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
            "dialog_round": 1,
            "tools": [],
            "datasets": [],
            "retrieval_config": {"retrieval_strategy": "semantic", "k": 2, "score": 0.5},
            "workflows": [],
            "preset_prompt": "preset",
            "long_term_memory": {"enable": True},
            "review_config": {"enable": False},
        }
        service.app_config_service = SimpleNamespace(
            get_app_config=lambda _app: app_config,
            get_langchain_tools_by_tools_config=lambda _tools: [],
        )

        created_records = []
        end_user_id = uuid4()
        conversation_id = uuid4()
        message_id = uuid4()

        def fake_create(model, **kwargs):
            created_records.append((model, kwargs))
            if model is EndUser:
                return SimpleNamespace(id=end_user_id, app_id=app.id)
            if model is Conversation:
                return SimpleNamespace(
                    id=conversation_id,
                    app_id=app.id,
                    created_by=end_user_id,
                    invoke_from=InvokeFrom.SERVICE_API.value,
                    summary="",
                )
            if model is Message:
                return SimpleNamespace(id=message_id)
            raise AssertionError(f"unexpected model: {model}")

        monkeypatch.setattr(service, "create", fake_create)

        llm = SimpleNamespace(
            features=[ModelFeature.TOOL_CALL.value],
            convert_to_human_message=lambda query, image_urls: f"{query}:{len(image_urls)}",
        )
        capabilities = {"image_input": {"enabled": True, "via_fallback": False}}
        resolution_capture = {}
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
                return ["history-message"]

        monkeypatch.setattr("internal.service.openapi_service.TokenBufferMemory", _FakeTokenBufferMemory)

        agent_thought = AgentThought(
            id=uuid4(),
            task_id=uuid4(),
            event=QueueEvent.AGENT_MESSAGE,
            thought="thinking",
            answer="answer",
            latency=0.2,
        )
        artifact_thought = AgentThought(
            id=uuid4(),
            task_id=uuid4(),
            event=QueueEvent.DEEP_ARTIFACT_CREATED,
            thought="trip-plan.docx",
            observation="https://cos.example.com/trip-plan.docx",
            tool="artifact",
            tool_input={
                "artifact": {
                    "name": "trip-plan.docx",
                    "url": "https://cos.example.com/trip-plan.docx",
                    "extension": "docx",
                }
            },
            latency=0.1,
        )

        class _FakeFunctionCallAgent:
            def __init__(self, llm, agent_config):
                self._llm = llm
                self._agent_config = agent_config

            def invoke(self, agent_state):
                assert agent_state["messages"] == ["hello:1"]
                return SimpleNamespace(
                    answer="final-answer",
                    latency=0.6,
                    agent_thoughts=[agent_thought, artifact_thought],
                )

        monkeypatch.setattr("internal.service.openapi_service.FunctionCallAgent", _FakeFunctionCallAgent)
        save_payload = {}
        service.conversation_service = SimpleNamespace(
            save_agent_thoughts=lambda **kwargs: save_payload.update(kwargs)
        )

        response = service.chat(req, account)

        assert response.data["input_parts"] == [
            {"type": "text", "text": "hello"},
            {"type": "image", "url": "https://a.com/1.png"},
        ]
        assert response.data["answer_parts"] == [
            {"type": "text", "text": "final-answer"},
            {
                "type": "artifact",
                "name": "trip-plan.docx",
                "url": "https://cos.example.com/trip-plan.docx",
                "extension": "docx",
            },
        ]
        assert response.data["artifacts"] == [
            {
                "name": "trip-plan.docx",
                "url": "https://cos.example.com/trip-plan.docx",
                "extension": "docx",
            }
        ]
        assert response.data["capabilities"] == capabilities
        assert save_payload["app_config"]["capabilities"] == capabilities
        assert resolution_capture == {
            "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
            "image_urls": req.image_urls.data,
            "entrypoint": "openapi",
        }

    def test_chat_should_return_runtime_capabilities_and_parts_when_resolution_available(
        self, monkeypatch
    ):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(id=uuid4(), status=AppStatus.PUBLISHED.value)
        req = _build_req(app.id)
        req.image_urls.data = ["https://a.com/1.png"]
        service.app_service = SimpleNamespace(get_app=lambda _app_id, _account: app)

        app_config = {
            "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
            "dialog_round": 1,
            "tools": [],
            "datasets": [],
            "retrieval_config": {"retrieval_strategy": "semantic", "k": 2, "score": 0.5},
            "workflows": [],
            "preset_prompt": "preset",
            "long_term_memory": {"enable": True},
            "review_config": {"enable": False},
        }
        service.app_config_service = SimpleNamespace(
            get_app_config=lambda _app: app_config,
            get_langchain_tools_by_tools_config=lambda _tools: [],
        )

        created_records = []
        end_user_id = uuid4()
        conversation_id = uuid4()
        message_id = uuid4()

        def fake_create(model, **kwargs):
            created_records.append((model, kwargs))
            if model is EndUser:
                return SimpleNamespace(id=end_user_id, app_id=app.id)
            if model is Conversation:
                return SimpleNamespace(
                    id=conversation_id,
                    app_id=app.id,
                    created_by=end_user_id,
                    invoke_from=InvokeFrom.SERVICE_API.value,
                    summary="",
                )
            if model is Message:
                return SimpleNamespace(id=message_id)
            raise AssertionError(f"unexpected model: {model}")

        monkeypatch.setattr(service, "create", fake_create)

        llm = SimpleNamespace(
            features=[ModelFeature.TOOL_CALL.value],
            convert_to_human_message=lambda query, image_urls: f"{query}:{len(image_urls)}",
        )
        capabilities = {"image_input": {"enabled": True, "via_fallback": False}}
        resolution_capture = {}
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
                return ["history-message"]

        monkeypatch.setattr("internal.service.openapi_service.TokenBufferMemory", _FakeTokenBufferMemory)

        agent_thought = AgentThought(
            id=uuid4(),
            task_id=uuid4(),
            event=QueueEvent.AGENT_MESSAGE,
            thought="thinking",
            answer="answer",
            latency=0.2,
        )
        artifact_thought = AgentThought(
            id=uuid4(),
            task_id=uuid4(),
            event=QueueEvent.DEEP_ARTIFACT_CREATED,
            thought="trip-plan.docx",
            observation="https://cos.example.com/trip-plan.docx",
            tool="artifact",
            tool_input={
                "artifact": {
                    "name": "trip-plan.docx",
                    "url": "https://cos.example.com/trip-plan.docx",
                    "extension": "docx",
                }
            },
            latency=0.1,
        )

        class _FakeFunctionCallAgent:
            def __init__(self, llm, agent_config):
                self._llm = llm
                self._agent_config = agent_config

            def invoke(self, agent_state):
                assert agent_state["messages"] == ["hello:1"]
                return SimpleNamespace(
                    answer="final-answer",
                    latency=0.6,
                    agent_thoughts=[agent_thought, artifact_thought],
                )

        monkeypatch.setattr("internal.service.openapi_service.FunctionCallAgent", _FakeFunctionCallAgent)
        save_payload = {}
        service.conversation_service = SimpleNamespace(
            save_agent_thoughts=lambda **kwargs: save_payload.update(kwargs)
        )

        response = service.chat(req, account)

        assert response.data["input_parts"] == [
            {"type": "text", "text": "hello"},
            {"type": "image", "url": "https://a.com/1.png"},
        ]
        assert response.data["answer_parts"] == [
            {"type": "text", "text": "final-answer"},
            {
                "type": "artifact",
                "name": "trip-plan.docx",
                "url": "https://cos.example.com/trip-plan.docx",
                "extension": "docx",
            },
        ]
        assert response.data["artifacts"] == [
            {
                "name": "trip-plan.docx",
                "url": "https://cos.example.com/trip-plan.docx",
                "extension": "docx",
            }
        ]
        assert response.data["capabilities"] == capabilities
        assert save_payload["app_config"]["capabilities"] == capabilities
        assert resolution_capture == {
            "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
            "image_urls": req.image_urls.data,
            "entrypoint": "openapi",
        }

    def test_chat_should_stream_and_aggregate_agent_message_chunks(self, monkeypatch, caplog):
        service = _build_service()
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(id=uuid4(), status=AppStatus.PUBLISHED.value)
        end_user = SimpleNamespace(id=uuid4(), app_id=app.id)
        conversation = SimpleNamespace(
            id=uuid4(),
            app_id=app.id,
            invoke_from=InvokeFrom.SERVICE_API.value,
            created_by=end_user.id,
            summary="long-memory",
        )
        req = _build_req(
            app.id,
            end_user_id=str(end_user.id),
            conversation_id=str(conversation.id),
        )
        req.stream.data = True
        req.image_urls.data = ["https://a.com/1.png"]
        service.app_service = SimpleNamespace(get_app=lambda _app_id, _account: app)

        def fake_get(model, _id):
            if model is EndUser:
                return end_user
            if model is Conversation:
                return conversation
            return None

        monkeypatch.setattr(service, "get", fake_get)
        message_id = uuid4()
        monkeypatch.setattr(
            service,
            "create",
            lambda model, **_kwargs: SimpleNamespace(id=message_id) if model is Message else None,
        )

        app_config = {
            "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
            "dialog_round": 2,
            "tools": [{"type": "builtin_tool"}],
            "datasets": [{"id": "dataset-1"}],
            "retrieval_config": {"retrieval_strategy": "semantic", "k": 2, "score": 0.7},
            "workflows": [{"id": "workflow-1"}],
            "preset_prompt": "preset",
            "long_term_memory": {"enable": True},
            "review_config": {"enable": False},
        }
        service.app_config_service = SimpleNamespace(
            get_app_config=lambda _app: app_config,
            get_langchain_tools_by_tools_config=lambda _tools: ["builtin-tool"],
            get_langchain_tools_by_workflow_ids=lambda _ids: ["workflow-tool"],
        )

        retrieval_call = {}
        service.retrieval_service = SimpleNamespace(
            create_langchain_tool_from_search=lambda **kwargs: retrieval_call.update(kwargs) or "dataset-tool"
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
                assert message_limit == 2
                return ["history-1"]

        monkeypatch.setattr("internal.service.openapi_service.TokenBufferMemory", _FakeTokenBufferMemory)

        shared_event_id = uuid4()
        shared_task_id = uuid4()
        action_event_id = uuid4()
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
                id=action_event_id,
                task_id=shared_task_id,
                event=QueueEvent.AGENT_ACTION,
                tool="search",
                tool_input={"q": "weather"},
                observation="tool-result",
                latency=0.3,
            ),
        ]
        captured_agent_tools = {}
        trace_capture = {}

        class _FakeFunctionCallAgent:
            def __init__(self, llm, agent_config):
                captured_agent_tools["tools"] = agent_config.tools
                queued_events = []
                self.agent_queue_manager = SimpleNamespace(
                    events=queued_events,
                    publish=lambda _task_id, thought: queued_events.append(thought),
                )

            def stream(self, _agent_state, config=None):
                if config is None:
                    return iter(stream_events)

                trace_capture["handler"] = config["callbacks"][0]
                trace_capture["queue_manager"] = self.agent_queue_manager
                child_run_id = uuid4()
                parent_run_id = uuid4()
                trace_capture["parent_run_id"] = str(parent_run_id)
                trace_capture["handler"].on_tool_start(
                    {"name": "search"},
                    '{"api_key":"private-tool-input"}',
                    run_id=child_run_id,
                    parent_run_id=parent_run_id,
                )
                trace_capture["handler"].on_tool_end(
                    {"result": "private-tool-output"},
                    run_id=child_run_id,
                    parent_run_id=parent_run_id,
                )

                def generate_events():
                    try:
                        trace_events = self.agent_queue_manager.events
                        yield trace_events[0]
                        yield stream_events[0]
                        yield stream_events[1]
                        yield trace_events[1]
                        yield from stream_events[2:]
                    finally:
                        trace_capture["stream_closed"] = True

                return generate_events()

        # AgentConfig 的 tools 字段要求 BaseTool 实例；这里聚焦服务编排逻辑，因此用轻量对象替代。
        monkeypatch.setattr(
            "internal.service.openapi_service.AgentConfig",
            lambda **kwargs: SimpleNamespace(**kwargs),
        )
        monkeypatch.setattr("internal.service.openapi_service.FunctionCallAgent", _FakeFunctionCallAgent)
        save_payload = {}
        service.conversation_service = SimpleNamespace(
            save_agent_thoughts=lambda **kwargs: save_payload.update(kwargs)
        )

        with Flask(__name__).app_context():
            events = list(service.chat(req, account))

        trace_events = [event for event in events if event.startswith("event: callable_trace")]
        assert len(trace_events) == 2
        trace_payload = json.loads(trace_events[0].split("data:", maxsplit=1)[1].strip())
        assert trace_payload["run_type"] == "tool"
        assert trace_payload["phase"] == "start"
        assert trace_payload["parent_run_id"] == trace_capture["parent_run_id"]
        assert "private-tool-input" not in trace_events[0]
        assert "private-tool-output" not in trace_events[1]
        assert events[1].startswith("event: ping")
        assert events[2].startswith("event: agent_message")
        assert len(captured_agent_tools["tools"]) == 3
        assert retrieval_call["dataset_ids"] == ["dataset-1"]
        assert retrieval_call["account_id"] == account.id
        assert len(save_payload["agent_thoughts"]) == 2
        assert save_payload["agent_thoughts"][0].thought == "AB"
        assert save_payload["agent_thoughts"][0].answer == "AB"
        assert save_payload["message_id"] == str(message_id)
        assert all(thought.event != QueueEvent.CALLABLE_TRACE for thought in save_payload["agent_thoughts"])

        save_payload.clear()
        with Flask(__name__).app_context():
            events = service.chat(req, account)
            next(events)
            next(events)
            next(events)
            next(events)
            closed_handler = trace_capture["handler"]
            queue_manager = trace_capture["queue_manager"]
            events.close()

        assert save_payload["agent_thoughts"][0].answer == "A"
        assert trace_capture["stream_closed"] is True
        queued_event_count = len(queue_manager.events)
        closed_handler.on_chain_start({"name": "late"}, {}, run_id=uuid4())
        assert len(queue_manager.events) == queued_event_count

        def fail_save(**_kwargs):
            raise RuntimeError("synthetic database failure")

        service.conversation_service.save_agent_thoughts = fail_save
        with Flask(__name__).app_context():
            events = service.chat(req, account)
            next(events)
            next(events)
            next(events)
            next(events)
            events.close()
        assert "error_type=RuntimeError" in caplog.text
