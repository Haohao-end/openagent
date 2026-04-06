from types import SimpleNamespace
from uuid import UUID

import pytest

from pkg.response import HttpCode


class TestHomeHandler:
    @pytest.fixture
    def http_client(self, app):
        with app.test_client() as client:
            yield client

    @pytest.fixture
    def home_user(self, monkeypatch):
        user = SimpleNamespace(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            is_authenticated=True,
            name="tester",
        )
        monkeypatch.setattr("internal.handler.home_handler.current_user", user)
        return user

    def test_get_intent_route_should_dump_stable_core_fields(self, http_client, home_user, monkeypatch):
        monkeypatch.setattr(
            "internal.service.home_service.HomeService.get_user_intent",
            lambda _service, account: {
                "intent": "build_app",
                "confidence": 0.92,
                "suggested_actions": [
                    {"label": "创建应用", "action": "create_app", "icon": "sparkles"}
                ],
                "is_default": False,
            },
        )

        resp = http_client.get("/home/intent")

        assert resp.status_code == 200
        assert resp.json["code"] == HttpCode.SUCCESS
        assert resp.json["data"]["intent"] == "build_app"
        assert resp.json["data"]["confidence"] == pytest.approx(0.92)
        assert resp.json["data"]["suggested_actions"][0]["action"] == "create_app"
        assert resp.json["data"]["is_default"] is False
