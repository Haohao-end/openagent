from types import SimpleNamespace

import pytest
from flask import Flask

from internal.handler.app_handler import AppHandler
from pkg.response import HttpCode


def _handler(app_service):
    return AppHandler(
        app_service=app_service,
        retrieval_service=None,
        language_model_manager=None,
    )


@pytest.mark.parametrize("name", [None, 123])
def test_generate_icon_preview_should_validate_non_string_name(name):
    handler = _handler(object())
    test_app = Flask(__name__)

    with test_app.test_request_context(
        "/apps/generate-icon-preview", method="POST", json={"name": name}
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
        "/apps/generate-icon-preview",
        method="POST",
        json={"name": " app ", "description": None},
    ):
        response, status_code = handler.generate_icon_preview.__wrapped__(handler)

    assert status_code == 200
    assert response.get_json()["code"] == HttpCode.SUCCESS
    assert captured == {"name": "app", "description": ""}


@pytest.mark.parametrize("payload", ["invalid", 1])
def test_generate_icon_preview_should_validate_non_object_json(payload):
    handler = _handler(object())
    test_app = Flask(__name__)

    with test_app.test_request_context(
        "/apps/generate-icon-preview", method="POST", json=payload
    ):
        response, status_code = handler.generate_icon_preview.__wrapped__(handler)

    assert status_code == 200
    assert response.get_json()["code"] == HttpCode.VALIDATE_ERROR
