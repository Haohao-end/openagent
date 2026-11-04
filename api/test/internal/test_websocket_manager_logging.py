from uuid import uuid4

import internal.extension.socketio_extension as socketio_extension
from internal.lib.websocket_manager import WebSocketManager


def test_emit_to_account_failure_log_omits_identifiers_and_error_text(monkeypatch, caplog):
    account_id = uuid4()
    manager = WebSocketManager()
    manager.add_connection("private-session-id", account_id)
    caplog.clear()

    class _Socket:
        def emit(self, *_args, **_kwargs):
            raise RuntimeError("PRIVATE_NOTIFICATION_PAYLOAD")

    monkeypatch.setattr(socketio_extension, "socketio", _Socket())
    manager.emit_to_account(account_id, "notification", {})

    assert str(account_id) not in caplog.text
    assert "private-session-id" not in caplog.text
    assert "PRIVATE_NOTIFICATION_PAYLOAD" not in caplog.text


def test_emit_notification_to_user_failure_log_omits_user_and_error_text(monkeypatch, caplog):
    user_id = "private-user-room"
    manager = WebSocketManager()

    class _Socket:
        def emit(self, *_args, **_kwargs):
            raise RuntimeError("PRIVATE_NOTIFICATION_PAYLOAD")

    monkeypatch.setattr(socketio_extension, "socketio", _Socket())
    manager.emit_notification_to_user(user_id, {"secret": "payload"})

    assert user_id not in caplog.text
    assert "PRIVATE_NOTIFICATION_PAYLOAD" not in caplog.text
    assert "error_type=RuntimeError" in caplog.text
