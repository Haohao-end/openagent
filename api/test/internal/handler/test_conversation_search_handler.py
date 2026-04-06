from types import SimpleNamespace
from uuid import UUID

import pytest

from pkg.response import HttpCode


def _search_result(
    *,
    conversation_id: str = "00000000-0000-0000-0000-000000000101",
    app_id: str = "00000000-0000-0000-0000-000000000201",
    name: str = "Python编程教程",
    human_message: str = "",
    ai_message: str = "",
    matched_fields: list[str] | None = None,
):
    return {
        "id": UUID(conversation_id),
        "name": name,
        "source_type": "assistant_agent",
        "app_id": UUID(app_id),
        "app_name": "测试应用",
        "human_message": human_message,
        "ai_message": ai_message,
        "matched_fields": matched_fields or [],
        "latest_message_at": 1700000000,
        "created_at": 1699999999,
    }


class TestConversationSearchHandler:
    @pytest.fixture
    def http_client(self, app):
        with app.test_client() as client:
            yield client

    @pytest.fixture
    def current_user(self, monkeypatch):
        account = SimpleNamespace(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            is_authenticated=True,
            email="tester@example.com",
            name="tester",
        )
        monkeypatch.setattr("internal.handler.conversation_handler.current_user", account)
        return account

    def test_search_conversations_should_delegate_empty_query_to_service(
        self,
        http_client,
        current_user,
        monkeypatch,
    ):
        called = {}

        def _fake_search(_service, account, query, limit):
            called["account"] = account
            called["query"] = query
            called["limit"] = limit
            return [_search_result(name="最近会话")]

        monkeypatch.setattr(
            "internal.service.conversation_service.ConversationService.search_conversations",
            _fake_search,
        )

        resp = http_client.get("/conversations/search", query_string={"query": "", "limit": 10})

        assert resp.status_code == 200
        assert resp.json["code"] == HttpCode.SUCCESS
        assert called == {"account": current_user, "query": "", "limit": 10}
        assert resp.json["data"][0]["name"] == "最近会话"

    def test_search_conversations_should_dump_stable_search_fields(
        self,
        http_client,
        current_user,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "internal.service.conversation_service.ConversationService.search_conversations",
            lambda _service, *_args, **_kwargs: [
                _search_result(
                    human_message="如何学习Python",
                    ai_message="Python是一门很好的编程语言",
                    matched_fields=["name", "human_message", "ai_message"],
                )
            ],
        )

        resp = http_client.get("/conversations/search", query_string={"query": "Python", "limit": 10})

        assert resp.status_code == 200
        assert resp.json["code"] == HttpCode.SUCCESS
        data = resp.json["data"][0]
        assert data["name"] == "Python编程教程"
        assert data["human_message"] == "如何学习Python"
        assert data["ai_message"] == "Python是一门很好的编程语言"
        assert data["matched_fields"] == ["name", "human_message", "ai_message"]
        assert data["source_type"] == "assistant_agent"
        assert data["app_name"] == "测试应用"

    def test_search_conversations_should_return_empty_list_when_service_has_no_results(
        self,
        http_client,
        current_user,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "internal.service.conversation_service.ConversationService.search_conversations",
            lambda _service, *_args, **_kwargs: [],
        )

        resp = http_client.get("/conversations/search", query_string={"query": "不存在的内容xyz", "limit": 10})

        assert resp.status_code == 200
        assert resp.json["code"] == HttpCode.SUCCESS
        assert resp.json["data"] == []

    def test_search_conversations_should_validate_limit_range(
        self,
        http_client,
        current_user,
        monkeypatch,
    ):
        called = {"count": 0}

        def _fake_search(_service, *_args, **_kwargs):
            called["count"] += 1
            return []

        monkeypatch.setattr(
            "internal.service.conversation_service.ConversationService.search_conversations",
            _fake_search,
        )

        resp = http_client.get("/conversations/search", query_string={"query": "test", "limit": 200})

        assert resp.status_code == 200
        assert resp.json["code"] == HttpCode.VALIDATE_ERROR
        assert "limit" in resp.json["message"]
        assert called["count"] == 0
