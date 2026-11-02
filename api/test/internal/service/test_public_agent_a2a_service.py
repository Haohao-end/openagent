import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from flask import Flask, has_app_context

from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.entity.conversation_entity import MessageStatus
from internal.exception import NotFoundException, ValidateErrorException
from internal.service.public_agent_a2a_service import PublicAgentA2AService
from internal.service.public_agent_registry_service import PublicAgentRegistryService


def _build_service(**kwargs) -> PublicAgentA2AService:
    kwargs.setdefault("db", SimpleNamespace(session=SimpleNamespace(query=lambda *_args, **_kwargs: None)))
    kwargs.setdefault("app_service", SimpleNamespace())
    kwargs.setdefault("app_config_service", SimpleNamespace())
    kwargs.setdefault("language_model_service", SimpleNamespace())
    kwargs.setdefault("public_agent_registry_service", SimpleNamespace())
    return PublicAgentA2AService(**kwargs)


class TestPublicAgentA2AService:
    @pytest.mark.parametrize("method", ["_extract_query_from_payload", "_extract_answer_text"])
    def test_extracts_all_text_parts_in_order(self, method):
        payload = {"message": {"parts": [
            {"type": "text", "text": " first "},
            {"type": "image", "url": "https://example.com/image.png"},
            {"type": "text", "text": "second"},
        ]}}
        assert getattr(PublicAgentA2AService, method)(payload) == "first\nsecond"

    def test_agent_card_should_advertise_streaming_support(self, monkeypatch):
        app = SimpleNamespace(id=uuid4(), account_id=uuid4(), name="Public", description="", tags=[])
        service = _build_service(
            app_config_service=SimpleNamespace(get_app_config=lambda *_args, **_kwargs: {}),
            public_agent_registry_service=SimpleNamespace(
                build_agent_message_url=lambda _app_id: "https://example.com/messages",
                build_agent_card_url=lambda _app_id: "https://example.com/card",
            ),
        )
        monkeypatch.setattr(service, "_get_public_app", lambda _app_id: app)

        card = service.get_agent_card(app.id)

        assert card["capabilities"]["streaming"] is True

    def test_invalid_context_should_be_rejected_before_runtime_setup(self, monkeypatch):
        setup_calls = []
        context_id = str(uuid4())
        service = _build_service(
            app_service=SimpleNamespace(
                _build_runtime_tools=lambda *_args, **_kwargs: setup_calls.append("tools") or [],
                _create_runtime_agent=lambda *_args, **_kwargs: setup_calls.append("agent"),
            ),
            app_config_service=SimpleNamespace(
                get_app_config=lambda _app: setup_calls.append("config") or {},
            ),
            language_model_service=SimpleNamespace(
                load_language_model=lambda _config: setup_calls.append("model"),
            ),
        )

        def reject_context(_app, _context_id):
            raise NotFoundException("A2A会话不存在")

        monkeypatch.setattr(service, "_resolve_public_conversation", reject_context)

        with pytest.raises(NotFoundException):
            list(service._stream_public_agent_events(
                SimpleNamespace(id=uuid4(), account_id=uuid4()), "hello", context_id, {}
            ))

        assert setup_calls == []

    @pytest.mark.parametrize("execution_path", ["invoke", "stream"])
    def test_public_agent_execution_should_create_one_runtime_agent(self, monkeypatch, execution_path):
        runtime_agent_calls = []
        runtime_agent = SimpleNamespace(invoke=lambda _state: None, stream=lambda _state: iter(()))
        app_service = SimpleNamespace(
            _build_runtime_tools=lambda *_args, **_kwargs: [],
            _create_runtime_agent=lambda *_args, **_kwargs: runtime_agent_calls.append(True) or runtime_agent,
        )
        llm = SimpleNamespace(convert_to_human_message=lambda query, _images: query)
        service = _build_service(
            app_service=app_service,
            app_config_service=SimpleNamespace(get_app_config=lambda _app: {}),
            language_model_service=SimpleNamespace(load_language_model=lambda _config: llm),
        )
        app = SimpleNamespace(id=uuid4(), account_id=uuid4())

        if execution_path == "invoke":
            service._invoke_public_agent(app, "hello")
        else:
            monkeypatch.setattr(
                "internal.service.public_agent_a2a_service.TokenBufferMemory",
                lambda **_kwargs: SimpleNamespace(get_history_prompt_messages=lambda: []),
            )
            conversation = SimpleNamespace(id=uuid4(), summary="", name="Existing")
            monkeypatch.setattr(service, "_resolve_public_conversation", lambda *_args: conversation)
            monkeypatch.setattr(service, "create", lambda *_args, **_kwargs: SimpleNamespace(id=uuid4()))
            monkeypatch.setattr(service, "_save_public_agent_thoughts", lambda **_kwargs: None)
            events = list(service._stream_public_agent_events(app, "hello", "ctx", {}))
            assert [set(json.loads(event.split("data:", 1)[1].strip())) for event in events] == [
                {"task"}, {"statusUpdate"},
            ]

        assert runtime_agent_calls == [True]

    def test_public_agent_search_should_hide_foreign_mcp_targets(self, monkeypatch):
        owner_id, caller_id = uuid4(), uuid4()
        url = "https://mcp.example/api?access_token=SYNTHETIC_SENTINEL"
        command = "mcp-server --token SYNTHETIC_COMMAND_SENTINEL"
        public_app = SimpleNamespace(
            id=uuid4(), account_id=owner_id, name="Clinic Agent", description="medical advice",
            tags=[], is_public=True, published_at=None,
            app_config=SimpleNamespace(
                opening_statement="", tools=[], workflows=[],
                mcp_bindings=[
                    {"name": "clinic", "transport": "streamable_http", "url": url},
                    {"name": "stdio", "transport": "stdio", "command": command},
                ],
            ),
        )

        class _Query:
            def filter(self, *_args, **_kwargs):
                return self

            def all(self):
                return [public_app]

        registry = PublicAgentRegistryService(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda *_args, **_kwargs: _Query())),
            faiss_service=SimpleNamespace(),
        )
        document = registry.build_public_agent_document(public_app)
        registry.faiss_service.search_public_agents = lambda **_kwargs: [document]
        service = _build_service(public_agent_registry_service=registry)
        monkeypatch.setattr(service, "send_message", lambda **_kwargs: {
            "message": {"parts": []}, "metadata": {"status": "success", "error": ""}
        })

        result = service.route_public_agents("clinic agent", caller_account_id=caller_id)

        assert owner_id != caller_id
        assert result["matches"][0]["app_id"] == str(public_app.id)
        content = result["matches"][0]["page_content"]
        assert url not in content and command not in content
        assert "clinic:streamable_http" in content and "stdio:stdio" in content
        assert public_app.app_config.mcp_bindings[0]["url"] == url

    def test_route_public_agents_should_search_and_delegate(self, monkeypatch):
        caller_account_id = uuid4()
        app_id = str(uuid4())
        search_calls = []
        send_calls = []
        service = _build_service(
            public_agent_registry_service=SimpleNamespace(
                search_public_apps=lambda **kwargs: search_calls.append(kwargs)
                or [
                    {
                        "app_id": app_id,
                        "name": "客服Agent",
                        "description": "处理售后与工单",
                        "a2a_card_url": f"/public/apps/{app_id}/a2a/agent-card",
                        "a2a_message_url": f"/public/apps/{app_id}/a2a/messages",
                        "page_content": "Agent名称: 客服Agent",
                    }
                ]
            )
        )
        monkeypatch.setattr(
            service,
            "send_message",
            lambda app_id, payload, flask_app=None: send_calls.append((app_id, payload, flask_app))
            or {
                "message": {
                    "parts": [{"type": "text", "text": "这是委派回答"}],
                },
                "metadata": {"status": "success", "error": ""},
            },
        )

        result = service.route_public_agents(
            "帮我处理退款投诉",
            caller_account_id=caller_account_id,
            assistant_agent_id="assistant-app-id",
        )

        assert search_calls[0]["exclude_app_ids"] == ["assistant-app-id"]
        assert result["matches"][0]["app_id"] == app_id
        assert result["selected_matches"][0]["app_id"] == app_id
        assert result["filtered_out_matches"] == []
        assert result["delegated_results"][0]["answer"] == "这是委派回答"
        assert result["delegated_results"][0]["status"] == "success"
        assert send_calls[0][0] == app_id
        assert send_calls[0][1]["metadata"]["caller_account_id"] == str(caller_account_id)

    def test_route_public_agents_should_delegate_only_llm_selected_matches(self, monkeypatch):
        caller_account_id = uuid4()
        app_ids = [str(uuid4()) for _ in range(3)]
        send_calls = []
        matches = [
            {
                "app_id": app_ids[0],
                "name": "护肤智能体",
                "description": "专业护肤建议",
                "a2a_card_url": f"/public/apps/{app_ids[0]}/a2a/agent-card",
                "a2a_message_url": f"/public/apps/{app_ids[0]}/a2a/messages",
                "page_content": "Agent名称: 护肤智能体",
            },
            {
                "app_id": app_ids[1],
                "name": "天气智能体",
                "description": "天气与穿衣建议",
                "a2a_card_url": f"/public/apps/{app_ids[1]}/a2a/agent-card",
                "a2a_message_url": f"/public/apps/{app_ids[1]}/a2a/messages",
                "page_content": "Agent名称: 天气智能体",
            },
            {
                "app_id": app_ids[2],
                "name": "美股专业分析Agent",
                "description": "美股市场分析",
                "a2a_card_url": f"/public/apps/{app_ids[2]}/a2a/agent-card",
                "a2a_message_url": f"/public/apps/{app_ids[2]}/a2a/messages",
                "page_content": "Agent名称: 美股专业分析Agent",
            },
        ]
        service = _build_service(
            public_agent_registry_service=SimpleNamespace(
                search_public_apps=lambda **_kwargs: matches
            )
        )
        monkeypatch.setattr(
            service,
            "_select_relevant_agent_ids_with_llm",
            lambda **_kwargs: ([app_ids[0]], "只保留护肤相关候选"),
        )
        monkeypatch.setattr(
            service,
            "send_message",
            lambda app_id, payload, flask_app=None: send_calls.append((app_id, payload, flask_app))
            or {
                "message": {
                    "parts": [{"type": "text", "text": f"已委派 {app_id}"}],
                },
                "metadata": {"status": "success", "error": ""},
            },
        )

        result = service.route_public_agents(
            "我该怎么护肤？",
            caller_account_id=caller_account_id,
            assistant_agent_id="assistant-app-id",
        )

        assert [match["app_id"] for match in result["selected_matches"]] == [app_ids[0]]
        assert [match["app_id"] for match in result["filtered_out_matches"]] == [app_ids[1], app_ids[2]]
        assert [delegated["app_id"] for delegated in result["delegated_results"]] == [app_ids[0]]
        assert [call[0] for call in send_calls] == [app_ids[0]]

    def test_route_public_agents_should_prefer_explicit_name_matches(self, monkeypatch):
        caller_account_id = uuid4()
        app_ids = [str(uuid4()) for _ in range(2)]
        send_calls = []
        matches = [
            {
                "app_id": app_ids[0],
                "name": "护肤智能体",
                "description": "专业护肤建议",
                "a2a_card_url": f"/public/apps/{app_ids[0]}/a2a/agent-card",
                "a2a_message_url": f"/public/apps/{app_ids[0]}/a2a/messages",
                "page_content": "Agent名称: 护肤智能体",
            },
            {
                "app_id": app_ids[1],
                "name": "天气智能体",
                "description": "天气与穿衣建议",
                "a2a_card_url": f"/public/apps/{app_ids[1]}/a2a/agent-card",
                "a2a_message_url": f"/public/apps/{app_ids[1]}/a2a/messages",
                "page_content": "Agent名称: 天气智能体",
            },
        ]
        service = _build_service(
            public_agent_registry_service=SimpleNamespace(
                search_public_apps=lambda **_kwargs: matches
            )
        )
        monkeypatch.setattr(
            service,
            "_select_relevant_agent_ids_with_llm",
            lambda **_kwargs: pytest.fail("explicit name match should bypass llm selection"),
        )
        monkeypatch.setattr(
            service,
            "send_message",
            lambda app_id, payload, flask_app=None: send_calls.append((app_id, payload, flask_app))
            or {
                "message": {
                    "parts": [{"type": "text", "text": f"已委派 {app_id}"}],
                },
                "metadata": {"status": "success", "error": ""},
            },
        )

        result = service.route_public_agents(
            "请使用护肤智能体回答我该怎么护肤",
            caller_account_id=caller_account_id,
            assistant_agent_id="assistant-app-id",
        )

        assert [match["app_id"] for match in result["selected_matches"]] == [app_ids[0]]
        assert [match["app_id"] for match in result["filtered_out_matches"]] == [app_ids[1]]
        assert [call[0] for call in send_calls] == [app_ids[0]]

    def test_route_public_agents_should_not_delegate_when_nothing_is_selected(self, monkeypatch):
        caller_account_id = uuid4()
        app_ids = [str(uuid4()) for _ in range(2)]
        matches = [
            {
                "app_id": app_ids[0],
                "name": "天气智能体",
                "description": "天气与穿衣建议",
                "a2a_card_url": f"/public/apps/{app_ids[0]}/a2a/agent-card",
                "a2a_message_url": f"/public/apps/{app_ids[0]}/a2a/messages",
                "page_content": "Agent名称: 天气智能体",
            },
            {
                "app_id": app_ids[1],
                "name": "美股专业分析Agent",
                "description": "美股市场分析",
                "a2a_card_url": f"/public/apps/{app_ids[1]}/a2a/agent-card",
                "a2a_message_url": f"/public/apps/{app_ids[1]}/a2a/messages",
                "page_content": "Agent名称: 美股专业分析Agent",
            },
        ]
        service = _build_service(
            public_agent_registry_service=SimpleNamespace(
                search_public_apps=lambda **_kwargs: matches
            )
        )
        monkeypatch.setattr(
            service,
            "_select_relevant_agent_ids_with_llm",
            lambda **_kwargs: ([], "没有足够相关的公共Agent"),
        )
        monkeypatch.setattr(
            service,
            "send_message",
            lambda *_args, **_kwargs: pytest.fail("no agent should be delegated"),
        )

        result = service.route_public_agents(
            "我该怎么护肤？",
            caller_account_id=caller_account_id,
            assistant_agent_id="assistant-app-id",
        )

        assert result["selected_matches"] == []
        assert [match["app_id"] for match in result["filtered_out_matches"]] == app_ids
        assert result["delegated_results"] == []
        assert result["message"] == "未找到足够相关的公共Agent"
        assert result["selection_reason"] == "没有足够相关的公共Agent"

    def test_send_message_should_wrap_agent_response_as_a2a_payload(self, monkeypatch):
        app_id = uuid4()
        service = _build_service()
        monkeypatch.setattr(
            service,
            "_get_public_app",
            lambda _app_id: SimpleNamespace(id=app_id),
        )
        monkeypatch.setattr(
            service,
            "_invoke_public_agent",
            lambda _app, query, flask_app=None, runtime_context=None: SimpleNamespace(
                answer=f"已处理: {query}",
                status="success",
                error="",
            ),
        )

        result = service.send_message(
            app_id,
            {
                "contextId": "ctx-1",
                "message": {"parts": [{"type": "text", "text": "查询天气"}]},
            },
        )

        assert result["contextId"] == "ctx-1"
        assert result["message"]["parts"][0]["text"] == "已处理: 查询天气"
        assert result["metadata"]["app_id"] == str(app_id)
        assert result["metadata"]["status"] == "success"

    def test_send_message_should_return_multimodal_parts_and_artifacts(self, monkeypatch):
        app_id = uuid4()
        service = _build_service()
        monkeypatch.setattr(
            service,
            "_get_public_app",
            lambda _app_id: SimpleNamespace(id=app_id),
        )
        monkeypatch.setattr(
            service,
            "_invoke_public_agent",
            lambda _app, query, flask_app=None: SimpleNamespace(
                answer=f"已处理: {query}",
                status="success",
                error="",
                agent_thoughts=[
                    SimpleNamespace(
                        event="deep_artifact_created",
                        thought="cover.png",
                        observation="https://example.com/cover.png",
                        tool_input={
                            "artifact": {
                                "name": "cover.png",
                                "url": "https://example.com/cover.png",
                                "mime_type": "image/png",
                                "extension": "png",
                            }
                        },
                    )
                ],
            ),
        )

        result = service.send_message(
            app_id,
            {
                "contextId": "ctx-2",
                "message": {"parts": [{"type": "text", "text": "生成封面"}]},
            },
        )

        assert result["message"]["parts"] == [
            {"type": "text", "text": "已处理: 生成封面"},
            {
                "type": "image",
                "url": "https://example.com/cover.png",
                "name": "cover.png",
                "mime_type": "image/png",
                "extension": "png",
            },
        ]
        assert result["artifacts"] == [
            {
                "name": "cover.png",
                "url": "https://example.com/cover.png",
                "mime_type": "image/png",
                "extension": "png",
            }
        ]

    def test_stream_message_should_delegate_to_streaming_pipeline(self, monkeypatch):
        app_id = uuid4()
        captured = {}
        service = _build_service()
        monkeypatch.setattr(
            service,
            "_get_public_app",
            lambda _app_id: SimpleNamespace(id=app_id, account_id=uuid4()),
        )
        monkeypatch.setattr(
            service,
            "_extract_query_from_payload",
            lambda payload: str(payload.get("query", "")).strip(),
        )
        monkeypatch.setattr(
            service,
            "_stream_public_agent_events",
            lambda **kwargs: captured.update(kwargs) or iter(
                [
                    'event: message\ndata: {"content":"streamed"}\n\n',
                ]
            ),
        )

        result = list(
            service.stream_message(
                app_id,
                {"query": "hello", "contextId": "ctx-2"},
            )
        )

        assert result == ['event: message\ndata: {"content":"streamed"}\n\n']
        assert captured["query"] == "hello"
        assert captured["context_id"] == "ctx-2"
        assert captured["request_payload"]["query"] == "hello"

    def test_convert_public_agent_route_to_tool_should_capture_app_context(self, monkeypatch):
        flask_app = Flask(__name__)
        flask_app.config["ASSISTANT_AGENT_ID"] = "assistant-app-id"
        caller_account_id = uuid4()
        captured = {}
        service = _build_service()

        monkeypatch.setattr(
            service,
            "route_public_agents",
            lambda **kwargs: captured.update(kwargs) or {"delegated_results": []},
        )

        with flask_app.app_context():
            tool = service.convert_public_agent_route_to_tool(caller_account_id)

        result = tool.invoke({"query": "油痘肌怎么护肤"})

        assert result == {"delegated_results": []}
        assert captured["caller_account_id"] == caller_account_id
        assert captured["assistant_agent_id"] == "assistant-app-id"
        assert captured["flask_app"] is flask_app

    def test_convert_public_agent_route_to_tool_should_reenter_app_context(self, monkeypatch):
        flask_app = Flask(__name__)
        caller_account_id = uuid4()
        captured = {}
        service = _build_service()

        def _fake_route_public_agents(**kwargs):
            captured.update(kwargs)
            captured["has_app_context"] = has_app_context()
            return {"delegated_results": []}

        monkeypatch.setattr(service, "route_public_agents", _fake_route_public_agents)

        with flask_app.app_context():
            tool = service.convert_public_agent_route_to_tool(caller_account_id)

        result = tool.invoke({"query": "油痘肌怎么护肤"})

        assert result == {"delegated_results": []}
        assert captured["flask_app"] is flask_app
        assert captured["has_app_context"] is True

    def test_send_message_should_raise_when_payload_has_no_query(self):
        service = _build_service()
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(
            service,
            "_get_public_app",
            lambda _app_id: SimpleNamespace(id=uuid4()),
        )

        try:
            with pytest.raises(ValidateErrorException):
                service.send_message(uuid4(), {"message": {"parts": []}})
        finally:
            monkeypatch.undo()

    def test_send_message_should_reject_image_parts_explicitly(self):
        service = _build_service()
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(
            service,
            "_get_public_app",
            lambda _app_id: SimpleNamespace(id=uuid4()),
        )

        try:
            with pytest.raises(ValidateErrorException) as exc:
                service.send_message(
                    uuid4(),
                    {
                        "message": {
                            "parts": [
                                {"type": "text", "text": "请分析这张图"},
                                {"type": "image", "url": "https://example.com/cat.png"},
                            ]
                        }
                    },
                )
        finally:
            monkeypatch.undo()

        assert exc.value.data["capabilities"]["image_input"]["enabled"] is False
        assert exc.value.data["capabilities"]["image_input"]["reason_code"] == "PUBLIC_A2A_IMAGE_INPUT_UNSUPPORTED"

    def test_stream_message_should_pass_existing_conversation_history_to_agent(self, monkeypatch):
        history = [object()]
        captured = {}
        conversation = SimpleNamespace(id=uuid4(), summary="saved summary", name="Existing")
        runtime_agent = SimpleNamespace(stream=lambda state: captured.update(state) or iter(()))

        def _fake_token_buffer_memory(*, conversation, **_kwargs):
            captured["memory_conversation"] = conversation
            return SimpleNamespace(get_history_prompt_messages=lambda: history)

        monkeypatch.setattr(
            "internal.service.public_agent_a2a_service.TokenBufferMemory",
            _fake_token_buffer_memory,
        )
        service = _build_service(
            app_service=SimpleNamespace(
                _build_runtime_tools=lambda *_args, **_kwargs: [],
                _create_runtime_agent=lambda *_args, **_kwargs: runtime_agent,
            ),
            app_config_service=SimpleNamespace(get_app_config=lambda _app: {}),
            language_model_service=SimpleNamespace(
                load_language_model=lambda _config: SimpleNamespace(
                    convert_to_human_message=lambda query, _images: query
                )
            ),
        )
        monkeypatch.setattr(service, "_resolve_public_conversation", lambda *_args: conversation)
        monkeypatch.setattr(service, "create", lambda *_args, **_kwargs: SimpleNamespace(id=uuid4()))
        monkeypatch.setattr(service, "_save_public_agent_thoughts", lambda **_kwargs: None)

        list(service._stream_public_agent_events(SimpleNamespace(id=uuid4(), account_id=uuid4()), "follow up", "ctx", {}))

        assert captured["history"] == history
        assert captured["memory_conversation"] is conversation

    def test_stream_public_agent_should_save_partial_history_when_client_disconnects(self, monkeypatch):
        thought = AgentThought(
            id=uuid4(), task_id=uuid4(), event=QueueEvent.AGENT_MESSAGE, answer="partial answer"
        )
        conversation = SimpleNamespace(id=uuid4(), summary="", name="Existing")
        message = SimpleNamespace(id=uuid4())
        saved, updates = [], []
        llm = SimpleNamespace(convert_to_human_message=lambda query, _images: query)
        runtime_agent = SimpleNamespace(stream=lambda _state: iter([thought]))
        monkeypatch.setattr(
            "internal.service.public_agent_a2a_service.TokenBufferMemory",
            lambda **_kwargs: SimpleNamespace(get_history_prompt_messages=lambda: []),
        )
        service = _build_service(
            app_service=SimpleNamespace(
                _build_runtime_tools=lambda *_args, **_kwargs: [],
                _create_runtime_agent=lambda *_args, **_kwargs: runtime_agent,
            ),
            app_config_service=SimpleNamespace(get_app_config=lambda _app: {}),
            language_model_service=SimpleNamespace(load_language_model=lambda _config: llm),
        )
        monkeypatch.setattr(service, "_resolve_public_conversation", lambda *_args: conversation)
        monkeypatch.setattr(service, "create", lambda *_args, **_kwargs: message)
        monkeypatch.setattr(service, "_save_public_agent_thoughts", lambda **kwargs: saved.append(kwargs))
        monkeypatch.setattr(service, "update", lambda target, **kwargs: updates.append((target, kwargs)))

        events = service._stream_public_agent_events(
            SimpleNamespace(id=uuid4(), account_id=uuid4()), "question", "ctx", {}
        )
        task_event = next(events)
        artifact_event = next(events)
        assert set(json.loads(task_event.split("data:", 1)[1].strip())) == {"task"}
        assert set(json.loads(artifact_event.split("data:", 1)[1].strip())) == {"artifactUpdate"}
        events.close()

        assert len(saved) == 1 and saved[0]["agent_thoughts"] == [thought]
        assert updates == [(message, {"status": MessageStatus.STOP.value})]

    @pytest.mark.parametrize(
        ("context_id", "error_type"),
        [("client-session", ValidateErrorException), (str(uuid4()), NotFoundException)],
    )
    def test_resolve_public_conversation_should_reject_unavailable_supplied_context(self, monkeypatch, context_id, error_type):
        class _Query:
            def filter(self, *_args):
                return self

            def one_or_none(self):
                return None

        create_calls = []
        service = _build_service(db=SimpleNamespace(session=SimpleNamespace(query=lambda *_args: _Query())))
        monkeypatch.setattr(service, "create", lambda *_args, **_kwargs: create_calls.append(True))

        with pytest.raises(error_type):
            service._resolve_public_conversation(SimpleNamespace(id=uuid4(), account_id=uuid4()), context_id)

        assert create_calls == []

    def test_resolve_public_conversation_should_create_when_context_is_omitted(self, monkeypatch):
        conversation = SimpleNamespace(id=uuid4())
        service = _build_service()
        monkeypatch.setattr(service, "create", lambda *_args, **_kwargs: conversation)

        assert service._resolve_public_conversation(SimpleNamespace(id=uuid4(), account_id=uuid4()), "") is conversation
