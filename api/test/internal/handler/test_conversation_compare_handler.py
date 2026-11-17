from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID
import pytest


class TestConversationCompareHandler:
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

    def test_compare_messages_delegates_to_service(self, http_client, current_user, monkeypatch):
        target_id = "00000000-0000-0000-0000-000000000002"
        base_id = "00000000-0000-0000-0000-000000000003"
        mock_service = MagicMock()
        mock_service.compare_messages.return_value = {
            "diff": {"latency_diff": 0.5, "answer_match": True}
        }
        monkeypatch.setattr(
            "internal.handler.conversation_handler.ConversationService.compare_messages",
            mock_service.compare_messages,
        )

        resp = http_client.post(
            "/conversations/messages/compare",
            json={"target_message_id": target_id, "base_message_id": base_id},
        )
        assert resp.status_code == 200
        assert resp.json["code"] == "success"
        assert resp.json["data"]["diff"]["answer_match"] is True

    def test_get_message_trace_delegates_to_service(self, http_client, current_user, monkeypatch):
        msg_id = "00000000-0000-0000-0000-000000000002"
        mock_service = MagicMock()
        mock_service.get_message_trace.return_value = {
            "message_id": msg_id,
            "timeline": [{"position": 1, "tool": "search"}],
        }
        monkeypatch.setattr(
            "internal.handler.conversation_handler.ConversationService.get_message_trace",
            mock_service.get_message_trace,
        )

        resp = http_client.get(f"/conversations/messages/{msg_id}/trace")
        assert resp.status_code == 200
        assert resp.json["code"] == "success"
        assert resp.json["data"]["message_id"] == msg_id
        assert len(resp.json["data"]["timeline"]) == 1
