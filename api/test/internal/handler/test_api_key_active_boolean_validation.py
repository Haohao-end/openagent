from uuid import UUID

import pytest

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
