from types import SimpleNamespace

import pytest
from flask import Flask

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


def test_a2a_message_should_stream_object_payload():
    service = SimpleNamespace(stream_message=lambda *_args: iter(["data: ok\n\n"]))
    handler = PublicAppHandler(None, service)
    test_app = Flask(__name__)

    with test_app.test_request_context(
        "/public/apps/app-id/a2a/messages",
        method="POST",
        json={"query": "hello"},
    ):
        response = handler.send_public_app_a2a_message("app-id")

    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"
