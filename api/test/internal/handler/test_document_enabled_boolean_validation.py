import pytest
from uuid import UUID

from pkg.response import HttpCode


@pytest.mark.parametrize("payload", [{"enabled": "invalid"}, {"enabled": 1}, {}, []])
def test_update_document_enabled_rejects_non_boolean_json(app, monkeypatch, payload):
    monkeypatch.setattr(
        "internal.service.document_service.DocumentService.update_document_enabled",
        lambda *_args, **_kwargs: pytest.fail("invalid enabled value reached service"),
    )

    with app.test_client() as client:
        response = client.post(
            f"/datasets/{UUID(int=1)}/documents/{UUID(int=2)}/enabled",
            json=payload,
        )

    assert response.json["code"] == HttpCode.VALIDATE_ERROR


def test_update_document_enabled_rejects_missing_form_value(app, monkeypatch):
    monkeypatch.setattr(
        "internal.service.document_service.DocumentService.update_document_enabled",
        lambda *_args, **_kwargs: pytest.fail("missing enabled value reached service"),
    )

    with app.test_client() as client:
        response = client.post(f"/datasets/{UUID(int=1)}/documents/{UUID(int=2)}/enabled", data={})

    assert response.json["code"] == HttpCode.VALIDATE_ERROR


@pytest.mark.parametrize("value", ["garbage", "falsee"])
@pytest.mark.parametrize(
    ("url", "service_path"),
    [
        (
            f"/datasets/{UUID(int=1)}/documents/{UUID(int=2)}/enabled",
            "internal.service.document_service.DocumentService.update_document_enabled",
        ),
        (
            f"/datasets/{UUID(int=1)}/documents/{UUID(int=2)}/segments/{UUID(int=3)}/enabled",
            "internal.service.segment_service.SegmentService.update_segment_enabled",
        ),
    ],
)
def test_enabled_handler_rejects_invalid_form_value(
    app, monkeypatch, url, service_path, value
):
    calls = []
    monkeypatch.setattr(service_path, lambda *_args, **_kwargs: calls.append(True))

    with app.test_client() as client:
        response = client.post(url, data={"enabled": value})

    assert response.json["code"] == HttpCode.VALIDATE_ERROR
    assert calls == []


@pytest.mark.parametrize("enabled", [True, False])
def test_update_document_enabled_accepts_boolean_json(app, monkeypatch, enabled):
    received = {}
    monkeypatch.setattr(
        "internal.service.document_service.DocumentService.update_document_enabled",
        lambda _service, _dataset_id, _document_id, value, _user: received.update(enabled=value),
    )

    with app.test_client() as client:
        response = client.post(
            f"/datasets/{UUID(int=1)}/documents/{UUID(int=2)}/enabled",
            json={"enabled": enabled},
        )

    assert response.json["code"] == HttpCode.SUCCESS
    assert received["enabled"] is enabled
