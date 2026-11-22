from types import SimpleNamespace

import pytest
from flask import Flask

from internal.exception import NotFoundException, ValidateErrorException
from internal.handler.public_app_handler import PublicAppHandler


@pytest.mark.parametrize("payload", [[], "invalid", 1])
def test_a2a_message_should_reject_non_object_payload(payload):
    service = SimpleNamespace(
        stream_message=lambda *_args: pytest.fail("invalid payload reached service")
    )
    handler = PublicAppHandler(None, service)
    test_app = Flask(__name__)

    with test_app.test_request_context(
        "/public/apps/app-id/a2a/messages", method="POST", json=payload
    ):
        response, status_code = handler.send_public_app_a2a_message("app-id")

    assert status_code == 400
    assert response.get_json()["error"] == "Request body must be an object"


@pytest.mark.parametrize("context_key", ["runtimeContext", "runtime_context"])
def test_a2a_message_should_reject_non_object_runtime_context(context_key):
    service = SimpleNamespace(
        stream_message=lambda *_args: pytest.fail("invalid runtime context reached service")
    )
    handler = PublicAppHandler(None, service)
    test_app = Flask(__name__)

    with test_app.test_request_context(
        "/public/apps/app-id/a2a/messages",
        method="POST",
        json={"query": "hello", context_key: "not-an-object"},
    ):
        response, status_code = handler.send_public_app_a2a_message("app-id")

    assert status_code == 400
    assert response.get_json()["error"] == "runtimeContext must be an object"


@pytest.mark.parametrize("context_key", ["runtimeContext", "runtime_context"])
def test_a2a_message_should_stream_object_payload(context_key):
    calls = []
    service = SimpleNamespace(
        stream_message=lambda *args: (calls.append(args), iter(["data: ok\n\n"]))[1]
    )
    handler = PublicAppHandler(None, service)
    test_app = Flask(__name__)

    payload = {"query": "hello", context_key: {"user_id": "synthetic"}}
    with test_app.test_request_context(
        "/public/apps/app-id/a2a/messages",
        method="POST",
        json=payload,
    ):
        response = handler.send_public_app_a2a_message("app-id")

    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"
    assert calls == [("app-id", payload)]


def test_a2a_card_should_return_404_when_app_is_not_found():
    def raise_not_found(_app_id):
        raise NotFoundException("Agent not found")

    handler = PublicAppHandler(None, SimpleNamespace(get_agent_card=raise_not_found))
    with Flask(__name__).test_request_context("/public/apps/missing/a2a/card"):
        response = handler.get_public_app_a2a_card("missing")
    assert response[1] == 404
    assert response[0].get_json() == {"error": "Agent not found"}


def test_a2a_conversation_messages_should_log_unexpected_error_and_return_500(caplog):
    def raise_unexpected(_app_id, _conversation_id):
        raise RuntimeError("db boom")

    handler = PublicAppHandler(None, SimpleNamespace(list_public_app_conversation_messages=raise_unexpected))
    with Flask(__name__).test_request_context("/public/apps/app-id/a2a/conversations/conv-id/messages"):
        response, status_code = handler.get_public_app_a2a_conversation_messages("app-id", "conv-id")

    assert status_code == 500
    assert response.get_json() == {"error": "Failed to retrieve conversation messages"}
    assert any(
        record.levelname == "ERROR" and "读取公共应用会话消息失败" in record.message and "RuntimeError" in record.message
        for record in caplog.records
    )


def test_a2a_conversation_messages_should_return_404_and_400_without_logging(caplog):
    def raise_not_found(_app_id, _conversation_id):
        raise NotFoundException("not found")

    def raise_validate(_app_id, _conversation_id):
        raise ValidateErrorException("invalid")

    handler = PublicAppHandler(None, SimpleNamespace(list_public_app_conversation_messages=raise_not_found))
    with Flask(__name__).test_request_context("/public/apps/app-id/a2a/conversations/conv-id/messages"):
        response, status_code = handler.get_public_app_a2a_conversation_messages("app-id", "conv-id")
    assert status_code == 404

    handler = PublicAppHandler(None, SimpleNamespace(list_public_app_conversation_messages=raise_validate))
    with Flask(__name__).test_request_context("/public/apps/app-id/a2a/conversations/conv-id/messages"):
        response, status_code = handler.get_public_app_a2a_conversation_messages("app-id", "conv-id")
    assert status_code == 400

    assert not any("读取公共应用会话消息失败" in record.message for record in caplog.records)
