from types import SimpleNamespace
from uuid import uuid4

from internal.exception import UnauthorizedException
from internal.handler.websocket_handler import (
    handle_connect,
    handle_subscribe_agent_notification,
    handle_subscribe_document_index_notification,
    register_socketio_handlers,
)


def test_handle_connect_should_bind_authenticated_sid(monkeypatch):
    account_id = uuid4()
    add_calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        "internal.handler.websocket_handler._resolve_socket_account_id",
        lambda auth=None: account_id,
    )
    monkeypatch.setattr(
        "internal.handler.websocket_handler.request",
        SimpleNamespace(sid="sid-1"),
    )
    monkeypatch.setattr(
        "internal.handler.websocket_handler.ws_manager",
        SimpleNamespace(add_connection=lambda sid, resolved_account_id: add_calls.append((sid, resolved_account_id))),
    )

    result = handle_connect({"token": "jwt-token"})

    assert result is None
    assert add_calls == [("sid-1", account_id)]


def test_handle_connect_should_reject_invalid_token(monkeypatch):
    monkeypatch.setattr(
        "internal.handler.websocket_handler._resolve_socket_account_id",
        lambda auth=None: (_ for _ in ()).throw(UnauthorizedException("bad token")),
    )
    monkeypatch.setattr(
        "internal.handler.websocket_handler.request",
        SimpleNamespace(sid="sid-2"),
    )
    monkeypatch.setattr(
        "internal.handler.websocket_handler.ws_manager",
        SimpleNamespace(add_connection=lambda *_args, **_kwargs: None),
    )

    result = handle_connect({"token": "bad-token"})

    assert result is False


def test_handle_subscribe_document_notification_should_ack_with_server_channel(monkeypatch):
    account_id = uuid4()
    subscribe_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "internal.handler.websocket_handler.request",
        SimpleNamespace(sid="sid-3"),
    )
    monkeypatch.setattr(
        "internal.handler.websocket_handler.ws_manager",
        SimpleNamespace(
            get_connection=lambda sid: SimpleNamespace(account_id=account_id, sid=sid),
            subscribe_notification=lambda sid, channel: subscribe_calls.append((sid, channel)),
        ),
    )

    result = handle_subscribe_document_index_notification()

    assert result == {"ok": True, "channel": str(account_id)}
    assert subscribe_calls == [("sid-3", str(account_id))]


def test_handle_subscribe_agent_notification_should_ack_with_prefixed_channel(monkeypatch):
    account_id = uuid4()
    subscribe_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "internal.handler.websocket_handler.request",
        SimpleNamespace(sid="sid-4"),
    )
    monkeypatch.setattr(
        "internal.handler.websocket_handler.ws_manager",
        SimpleNamespace(
            get_connection=lambda sid: SimpleNamespace(account_id=account_id, sid=sid),
            subscribe_notification=lambda sid, channel: subscribe_calls.append((sid, channel)),
        ),
    )

    result = handle_subscribe_agent_notification()

    expected_channel = f"agent:{account_id}"
    assert result == {"ok": True, "channel": expected_channel}
    assert subscribe_calls == [("sid-4", expected_channel)]


def test_handle_subscribe_document_notification_should_reject_unauthenticated_sid(monkeypatch):
    monkeypatch.setattr(
        "internal.handler.websocket_handler.request",
        SimpleNamespace(sid="sid-5"),
    )
    monkeypatch.setattr(
        "internal.handler.websocket_handler.ws_manager",
        SimpleNamespace(
            get_connection=lambda _sid: None,
            subscribe_notification=lambda *_args, **_kwargs: None,
        ),
    )

    result = handle_subscribe_document_index_notification()

    assert result == {"ok": False, "error": "unauthorized"}


def test_register_socketio_handlers_should_bind_expected_events():
    event_calls: list[tuple[str, str]] = []

    class FakeSocketIO:
        def on_event(self, event: str, handler):
            event_calls.append((event, handler.__name__))

    register_socketio_handlers(FakeSocketIO())

    assert event_calls == [
        ("connect", "handle_connect"),
        ("disconnect", "handle_disconnect"),
        ("subscribe_message", "handle_subscribe_message"),
        ("unsubscribe_message", "handle_unsubscribe_message"),
        ("subscribe_document_index_notification", "handle_subscribe_document_index_notification"),
        ("unsubscribe_document_index_notification", "handle_unsubscribe_document_index_notification"),
        ("subscribe_agent_notification", "handle_subscribe_agent_notification"),
        ("unsubscribe_agent_notification", "handle_unsubscribe_agent_notification"),
    ]
