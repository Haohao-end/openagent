from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID
import pytest

from internal.model import App, Message


class TestTraceHandler:
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
        monkeypatch.setattr("internal.handler.trace_handler.current_user", account)
        return account

    def test_get_message_timeline_unauthorized(self, http_client, monkeypatch):
        monkeypatch.setattr("internal.handler.trace_handler.current_user", None)
        app_id = "00000000-0000-0000-0000-000000000010"
        msg_id = "00000000-0000-0000-0000-000000000020"

        resp = http_client.get(f"/apps/{app_id}/messages/{msg_id}/timeline")
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "Unauthorized"}

    def test_get_message_timeline_app_not_found_or_not_owned(
        self, http_client, current_user, monkeypatch
    ):
        app_id = "00000000-0000-0000-0000-000000000010"
        msg_id = "00000000-0000-0000-0000-000000000020"

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        monkeypatch.setattr("internal.handler.trace_handler.db.session.query", lambda model: mock_query)

        resp = http_client.get(f"/apps/{app_id}/messages/{msg_id}/timeline")
        assert resp.status_code == 404
        assert resp.get_json() == {"error": "App not found"}

    def test_get_message_timeline_message_not_found(
        self, http_client, current_user, monkeypatch
    ):
        app_id = UUID("00000000-0000-0000-0000-000000000010")
        msg_id = UUID("00000000-0000-0000-0000-000000000020")

        def _mock_query(model):
            mock = MagicMock()
            if model is App:
                mock.filter.return_value.first.return_value = SimpleNamespace(id=app_id, account_id=current_user.id)
            elif model is Message:
                mock.filter.return_value.first.return_value = None
            return mock

        monkeypatch.setattr("internal.handler.trace_handler.db.session.query", _mock_query)

        resp = http_client.get(f"/apps/{app_id}/messages/{msg_id}/timeline")
        assert resp.status_code == 404
        assert resp.get_json() == {"error": "Message not found"}

    def test_get_message_timeline_success(
        self, http_client, current_user, monkeypatch
    ):
        app_id = UUID("00000000-0000-0000-0000-000000000010")
        msg_id = UUID("00000000-0000-0000-0000-000000000020")

        def _mock_query(model):
            mock = MagicMock()
            if model is App:
                mock.filter.return_value.first.return_value = SimpleNamespace(id=app_id, account_id=current_user.id)
            elif model is Message:
                mock.filter.return_value.first.return_value = SimpleNamespace(id=msg_id, app_id=app_id)
            return mock

        monkeypatch.setattr("internal.handler.trace_handler.db.session.query", _mock_query)
        mock_timeline = [
            SimpleNamespace(
                id=UUID("00000000-0000-0000-0000-000000000030"),
                thought="thinking",
                observation="done",
                tool="google_search",
                latency=0.12,
            )
        ]
        monkeypatch.setattr(
            "internal.handler.trace_handler.TraceService.get_message_timeline",
            lambda _app_id, _msg_id: mock_timeline,
        )

        resp = http_client.get(f"/apps/{app_id}/messages/{msg_id}/timeline")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["thought"] == "thinking"
        assert data[0]["observation"] == "done"
        assert data[0]["tool"] == "google_search"
        assert data[0]["latency"] == 0.12
