from types import SimpleNamespace

import pytest
from flask import Flask

from internal.handler.workflow_handler import WorkflowHandler
from pkg.response import HttpCode


def _handler(workflow_service):
    return WorkflowHandler(workflow_service=workflow_service)


@pytest.mark.parametrize("name", [None, 123])
def test_generate_icon_preview_should_validate_non_string_name(name):
    handler = _handler(object())
    test_app = Flask(__name__)

    with test_app.test_request_context(
        "/workflows/generate-icon-preview", method="POST", json={"name": name}
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
        "/workflows/generate-icon-preview",
        method="POST",
        json={"name": " workflow ", "description": None},
    ):
        response, status_code = handler.generate_icon_preview.__wrapped__(handler)

    assert status_code == 200
    assert response.get_json()["code"] == HttpCode.SUCCESS
    assert captured == {"name": "workflow", "description": ""}


@pytest.mark.parametrize("payload", ["invalid", 1])
def test_generate_icon_preview_should_validate_non_object_json(payload):
    handler = _handler(object())
    test_app = Flask(__name__)

    with test_app.test_request_context(
        "/workflows/generate-icon-preview", method="POST", json=payload
    ):
        response, status_code = handler.generate_icon_preview.__wrapped__(handler)

    assert status_code == 200
    assert response.get_json()["code"] == HttpCode.VALIDATE_ERROR
