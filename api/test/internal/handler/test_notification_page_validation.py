from types import SimpleNamespace

import pytest
from flask import Flask

from internal.handler.notification_handler import NotificationHandler
from pkg.response import HttpCode


@pytest.mark.parametrize("requested_page", [0, -5])
def test_get_notifications_should_clamp_page_to_one(monkeypatch, requested_page):
    received = {}
    service = SimpleNamespace(
        get_user_notifications=lambda _user_id, limit, offset, notification_type=None: (
            received.update(limit=limit, offset=offset) or [],
            0,
        )
    )
    handler = NotificationHandler(notification_service=service)
    monkeypatch.setattr(
        "internal.handler.notification_handler.current_user", SimpleNamespace(id="user")
    )
    test_app = Flask(__name__)

    with test_app.test_request_context(
        "/notifications", query_string={"page": requested_page}
    ):
        response, status_code = handler.get_notifications.__wrapped__(handler)

    assert status_code == 200
    assert response.get_json()["code"] == HttpCode.SUCCESS
    assert response.get_json()["data"]["paginator"]["page"] == 1
    assert received["offset"] == 0
