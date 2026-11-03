from uuid import UUID

from flask import Flask
import pytest

from internal.handler.api_key_handler import ApiKeyHandler
from pkg.response import HttpCode


@pytest.mark.parametrize("payload", [{"is_active": "invalid"}, {"is_active": 1}, {}, []])
def test_update_api_key_is_active_rejects_non_boolean_json(app, monkeypatch, payload):
    with app.test_client() as client:
        monkeypatch.setattr(
            "internal.service.api_key_service.ApiKeyService.update_api_key",
            lambda *_args, **_kwargs: pytest.fail("invalid status reached service"),
        )

        response = client.post(
            f"/openapi/api-keys/{UUID(int=1)}/is-active",
            json=payload,
        )

    assert response.json["code"] == HttpCode.VALIDATE_ERROR


@pytest.mark.parametrize("is_active", [True, False])
def test_update_api_key_is_active_accepts_boolean_json(app, monkeypatch, is_active):
    received = {}
    monkeypatch.setattr(
        "internal.service.api_key_service.ApiKeyService.update_api_key",
        lambda _service, _id, _user, **values: received.update(values),
    )

    with app.test_client() as client:
        response = client.post(
            f"/openapi/api-keys/{UUID(int=1)}/is-active",
            json={"is_active": is_active},
        )

    assert response.json["code"] == HttpCode.SUCCESS
    assert received["is_active"] is is_active


def test_update_api_key_remark_only_does_not_change_active_status():
    received = {}
    service = type("Service", (), {
        "update_api_key": lambda _self, _id, _user, **values: received.update(values),
    })()
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", LOGIN_DISABLED=True, WTF_CSRF_ENABLED=False)

    with app.test_request_context(
        f"/openapi/api-keys/{UUID(int=1)}",
        method="POST",
        json={"remark": "updated"},
    ):
        response = ApiKeyHandler(service).update_api_key(UUID(int=1))

    assert response[0].get_json()["code"] == HttpCode.SUCCESS
    assert received == {"remark": "updated"}


def test_update_api_key_rejects_null_remark_before_service(app, monkeypatch):
    monkeypatch.setattr(
        "internal.service.api_key_service.ApiKeyService.update_api_key",
        lambda *_args, **_kwargs: pytest.fail("null remark reached service"),
    )

    with app.test_client() as client:
        response = client.post(
            f"/openapi/api-keys/{UUID(int=1)}",
            json={"remark": None},
        )

    assert response.json["code"] == HttpCode.VALIDATE_ERROR


def test_update_api_key_preserves_explicit_false_status():
    received = {}
    service = type("Service", (), {
        "update_api_key": lambda _self, _id, _user, **values: received.update(values),
    })()
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", LOGIN_DISABLED=True, WTF_CSRF_ENABLED=False)

    with app.test_request_context(
        f"/openapi/api-keys/{UUID(int=1)}",
        method="POST",
        json={"is_active": False},
    ):
        response = ApiKeyHandler(service).update_api_key(UUID(int=1))

    assert response[0].get_json()["code"] == HttpCode.SUCCESS
    assert received == {"is_active": False}
