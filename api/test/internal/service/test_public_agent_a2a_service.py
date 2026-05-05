from types import SimpleNamespace
from uuid import uuid4

import pytest
from flask import Flask, has_app_context

from internal.exception import ValidateErrorException
from internal.service.public_agent_a2a_service import PublicAgentA2AService


def _build_service(**kwargs) -> PublicAgentA2AService:
    kwargs.setdefault("db", SimpleNamespace(session=SimpleNamespace(query=lambda *_args, **_kwargs: None)))
    kwargs.setdefault("app_service", SimpleNamespace())
    kwargs.setdefault("app_config_service", SimpleNamespace())
    kwargs.setdefault("language_model_service", SimpleNamespace())
    kwargs.setdefault("public_agent_registry_service", SimpleNamespace())
    return PublicAgentA2AService(**kwargs)


class TestPublicAgentA2AService:
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
            lambda _app, query, flask_app=None: SimpleNamespace(
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
