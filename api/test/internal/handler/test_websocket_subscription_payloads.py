from types import SimpleNamespace

import pytest

from internal.handler.websocket_handler import (
    handle_subscribe_message,
    handle_unsubscribe_message,
)


@pytest.mark.parametrize(
    "handler",
    [handle_subscribe_message, handle_unsubscribe_message],
)
def test_message_subscription_should_ignore_non_object_payload(monkeypatch, handler):
    manager = SimpleNamespace(
        get_connection=lambda _sid: SimpleNamespace(account_id="user"),
        subscribe_message=lambda *_args: pytest.fail("invalid payload subscribed"),
        unsubscribe_message=lambda *_args: pytest.fail("invalid payload unsubscribed"),
    )
    monkeypatch.setattr("internal.handler.websocket_handler.request", SimpleNamespace(sid="sid"))
    monkeypatch.setattr("internal.handler.websocket_handler.ws_manager", manager)

    handler("malformed")
