from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID
import pytest

from internal.model import App, Message, MessageAgentThought


class TestFeedbackHandler:
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
        monkeypatch.setattr("internal.handler.feedback_handler.current_user", account)
        return account

    def test_create_feedback_app_not_found(self, http_client, current_user, monkeypatch):
        app_id = "00000000-0000-0000-0000-000000000010"
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        monkeypatch.setattr("internal.handler.feedback_handler.db.session.query", lambda _m: mock_query)

        resp = http_client.post(
            f"/apps/{app_id}/feedbacks",
            json={"target_id": "00000000-0000-0000-0000-000000000020", "target_type": "message", "rating": 1},
        )
        assert resp.status_code == 404
        assert resp.get_json() == {"error": "App not found"}

    def test_create_feedback_invalid_target_type(self, http_client, current_user, monkeypatch):
        app_id = UUID("00000000-0000-0000-0000-000000000010")
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = SimpleNamespace(id=app_id, account_id=current_user.id)
        monkeypatch.setattr("internal.handler.feedback_handler.db.session.query", lambda _m: mock_query)

        resp = http_client.post(
            f"/apps/{app_id}/feedbacks",
            json={"target_id": "00000000-0000-0000-0000-000000000020", "target_type": "invalid_type"},
        )
        assert resp.status_code == 400
        assert "Invalid request" in resp.get_json()["error"]

    def test_create_feedback_nonexistent_message(self, http_client, current_user, monkeypatch):
        app_id = UUID("00000000-0000-0000-0000-000000000010")
        msg_id = UUID("00000000-0000-0000-0000-000000000020")

        def _mock_query(model):
            mock = MagicMock()
            if model is App:
                mock.filter.return_value.first.return_value = SimpleNamespace(id=app_id, account_id=current_user.id)
            elif model is Message:
                mock.filter.return_value.first.return_value = None
            return mock

        monkeypatch.setattr("internal.handler.feedback_handler.db.session.query", _mock_query)
        monkeypatch.setattr("internal.service.feedback_service.db.session.query", _mock_query)

        resp = http_client.post(
            f"/apps/{app_id}/feedbacks",
            json={"target_id": str(msg_id), "target_type": "message", "rating": 1},
        )
        assert resp.status_code == 404
        assert "Message not found" in resp.get_json()["error"]

    def test_create_feedback_nonexistent_span(self, http_client, current_user, monkeypatch):
        app_id = UUID("00000000-0000-0000-0000-000000000010")
        span_id = UUID("00000000-0000-0000-0000-000000000030")

        def _mock_query(model):
            mock = MagicMock()
            if model is App:
                mock.filter.return_value.first.return_value = SimpleNamespace(id=app_id, account_id=current_user.id)
            elif model is MessageAgentThought:
                mock.filter.return_value.first.return_value = None
            return mock

        monkeypatch.setattr("internal.handler.feedback_handler.db.session.query", _mock_query)
        monkeypatch.setattr("internal.service.feedback_service.db.session.query", _mock_query)

        resp = http_client.post(
            f"/apps/{app_id}/feedbacks",
            json={"target_id": str(span_id), "target_type": "span", "rating": -1},
        )
        assert resp.status_code == 404
        assert "Span not found" in resp.get_json()["error"]

    def test_create_feedback_cross_app_target(self, http_client, current_user, monkeypatch):
        app_id = UUID("00000000-0000-0000-0000-000000000010")
        msg_id = UUID("00000000-0000-0000-0000-000000000020")
        other_app_id = UUID("00000000-0000-0000-0000-000000000099")

        def _mock_query(model):
            mock = MagicMock()
            if model is App:
                mock.filter.return_value.first.return_value = SimpleNamespace(id=app_id, account_id=current_user.id)
            elif model is Message:
                # Message belongs to other_app_id, so filter(Message.id == msg_id, Message.app_id == app.id) returns None
                mock.filter.return_value.first.return_value = None
            return mock

        monkeypatch.setattr("internal.handler.feedback_handler.db.session.query", _mock_query)
        monkeypatch.setattr("internal.service.feedback_service.db.session.query", _mock_query)

        resp = http_client.post(
            f"/apps/{app_id}/feedbacks",
            json={"target_id": str(msg_id), "target_type": "message", "rating": 1},
        )
        assert resp.status_code == 404
        assert "Message not found" in resp.get_json()["error"]

    def test_create_feedback_message_target_success(self, http_client, current_user, monkeypatch):
        app_id = UUID("00000000-0000-0000-0000-000000000010")
        msg_id = UUID("00000000-0000-0000-0000-000000000020")
        conv_id = UUID("00000000-0000-0000-0000-000000000050")
        feedback_id = UUID("00000000-0000-0000-0000-000000000060")

        def _mock_query(model):
            mock = MagicMock()
            if model is App:
                mock.filter.return_value.first.return_value = SimpleNamespace(id=app_id, account_id=current_user.id)
            elif model is Message:
                mock.filter.return_value.first.return_value = SimpleNamespace(id=msg_id, app_id=app_id, conversation_id=conv_id)
            return mock

        monkeypatch.setattr("internal.handler.feedback_handler.db.session.query", _mock_query)
        monkeypatch.setattr("internal.service.feedback_service.db.session.query", _mock_query)
        monkeypatch.setattr("internal.service.feedback_service.db.session.add", lambda _obj: None)
        monkeypatch.setattr("internal.service.feedback_service.db.session.commit", lambda: None)
        monkeypatch.setattr("internal.model.Feedback.id", feedback_id)

        resp = http_client.post(
            f"/apps/{app_id}/feedbacks",
            json={"target_id": str(msg_id), "target_type": "message", "rating": 1, "content": "Great!"},
        )
        assert resp.status_code == 201
        assert resp.get_json() == {"id": str(feedback_id)}

    def test_create_feedback_span_target_success(self, http_client, current_user, monkeypatch):
        app_id = UUID("00000000-0000-0000-0000-000000000010")
        span_id = UUID("00000000-0000-0000-0000-000000000030")
        conv_id = UUID("00000000-0000-0000-0000-000000000050")
        feedback_id = UUID("00000000-0000-0000-0000-000000000061")

        def _mock_query(model):
            mock = MagicMock()
            if model is App:
                mock.filter.return_value.first.return_value = SimpleNamespace(id=app_id, account_id=current_user.id)
            elif model is MessageAgentThought:
                mock.filter.return_value.first.return_value = SimpleNamespace(id=span_id, app_id=app_id, conversation_id=conv_id)
            return mock

        monkeypatch.setattr("internal.handler.feedback_handler.db.session.query", _mock_query)
        monkeypatch.setattr("internal.service.feedback_service.db.session.query", _mock_query)
        monkeypatch.setattr("internal.service.feedback_service.db.session.add", lambda _obj: None)
        monkeypatch.setattr("internal.service.feedback_service.db.session.commit", lambda: None)
        monkeypatch.setattr("internal.model.Feedback.id", feedback_id)

        resp = http_client.post(
            f"/apps/{app_id}/feedbacks",
            json={"target_id": str(span_id), "target_type": "span", "rating": -1, "content": "Slow response"},
        )
        assert resp.status_code == 201
        assert resp.get_json() == {"id": str(feedback_id)}

    def test_get_feedbacks_app_not_found(self, http_client, current_user, monkeypatch):
        app_id = "00000000-0000-0000-0000-000000000010"
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        monkeypatch.setattr("internal.handler.feedback_handler.db.session.query", lambda _m: mock_query)

        resp = http_client.get(f"/apps/{app_id}/feedbacks")
        assert resp.status_code == 404
        assert resp.get_json() == {"error": "App not found"}

    def test_get_feedbacks_invalid_target_type(self, http_client, current_user, monkeypatch):
        app_id = UUID("00000000-0000-0000-0000-000000000010")
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = SimpleNamespace(id=app_id, account_id=current_user.id)
        monkeypatch.setattr("internal.handler.feedback_handler.db.session.query", lambda _m: mock_query)

        resp = http_client.get(f"/apps/{app_id}/feedbacks?target_type=invalid")
        assert resp.status_code == 400
        assert "Invalid request" in resp.get_json()["error"]

    def test_get_feedbacks_invalid_page_or_limit(self, http_client, current_user, monkeypatch):
        app_id = UUID("00000000-0000-0000-0000-000000000010")
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = SimpleNamespace(id=app_id, account_id=current_user.id)
        monkeypatch.setattr("internal.handler.feedback_handler.db.session.query", lambda _m: mock_query)

        resp = http_client.get(f"/apps/{app_id}/feedbacks?page=0")
        assert resp.status_code == 400

        resp = http_client.get(f"/apps/{app_id}/feedbacks?limit=101")
        assert resp.status_code == 400

    def test_get_feedbacks_success_empty(self, http_client, current_user, monkeypatch):
        app_id = UUID("00000000-0000-0000-0000-000000000010")
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = SimpleNamespace(id=app_id, account_id=current_user.id)
        monkeypatch.setattr("internal.handler.feedback_handler.db.session.query", lambda _m: mock_query)
        monkeypatch.setattr("internal.handler.feedback_handler.FeedbackService.get_feedbacks", lambda *_args: [])

        resp = http_client.get(f"/apps/{app_id}/feedbacks")
        assert resp.status_code == 200
        assert resp.get_json() == {"data": []}

    def test_get_feedbacks_success_with_data(self, http_client, current_user, monkeypatch):
        app_id = UUID("00000000-0000-0000-0000-000000000010")
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = SimpleNamespace(id=app_id, account_id=current_user.id)
        monkeypatch.setattr("internal.handler.feedback_handler.db.session.query", lambda _m: mock_query)

        fake_feedback = SimpleNamespace(
            id=UUID("00000000-0000-0000-0000-000000000070"),
            target_id=UUID("00000000-0000-0000-0000-000000000020"),
            target_type="message",
            rating=1,
            content="Great work",
        )
        monkeypatch.setattr("internal.handler.feedback_handler.FeedbackService.get_feedbacks", lambda _aid, _tt, _p, _l: [fake_feedback])

        resp = http_client.get(f"/apps/{app_id}/feedbacks?target_type=message&page=1&limit=10")
        assert resp.status_code == 200
        assert resp.get_json() == {
            "data": [
                {
                    "id": "00000000-0000-0000-0000-000000000070",
                    "target_id": "00000000-0000-0000-0000-000000000020",
                    "target_type": "message",
                    "rating": 1,
                    "content": "Great work",
                }
            ]
        }
