from types import SimpleNamespace

import pytest
from flask import Flask

from internal.handler.mcp_handler import McpHandler
from pkg.response import HttpCode


def _handler(mcp_service):
    return McpHandler(mcp_service=mcp_service)


@pytest.mark.parametrize("name", [None, 123])
def test_generate_icon_preview_should_validate_non_string_name(name):
    handler = _handler(
        SimpleNamespace(generate_icon_preview=lambda *_args: pytest.fail("invalid name reached service"))
    )
    test_app = Flask(__name__)

    with test_app.test_request_context(
        "/mcp-providers/generate-icon-preview", method="POST", json={"name": name}
    ):
        response, status_code = handler.generate_icon_preview.__wrapped__(handler)

    assert status_code == 200
    assert response.get_json()["code"] == HttpCode.VALIDATE_ERROR


def test_generate_icon_preview_should_treat_null_description_as_empty():
    captured = {}
    service = SimpleNamespace(
        generate_icon_preview=lambda name, description: captured.update(
            name=name, description=description
        ) or "https://icon.example/preview.png"
    )
    handler = _handler(service)
    test_app = Flask(__name__)

    with test_app.test_request_context(
        "/mcp-providers/generate-icon-preview",
        method="POST",
        json={"name": " mcp ", "description": None},
    ):
        response, status_code = handler.generate_icon_preview.__wrapped__(handler)

    assert status_code == 200
    assert response.get_json()["code"] == HttpCode.SUCCESS
    assert captured == {"name": "mcp", "description": ""}
