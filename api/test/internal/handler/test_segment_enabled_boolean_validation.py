import pytest
from uuid import UUID

from pkg.response import HttpCode


@pytest.mark.parametrize("payload", [{"enabled": "invalid"}, {"enabled": 1}, {}, []])
def test_update_segment_enabled_rejects_non_boolean_json(app, monkeypatch, payload):
    monkeypatch.setattr(
        "internal.service.segment_service.SegmentService.update_segment_enabled",
        lambda *_args, **_kwargs: pytest.fail("invalid enabled value reached service"),
    )

    with app.test_client() as client:
        response = client.post(
            f"/datasets/{UUID(int=1)}/documents/{UUID(int=2)}/segments/{UUID(int=3)}/enabled",
            json=payload,
        )

    assert response.json["code"] == HttpCode.VALIDATE_ERROR


def test_update_segment_enabled_rejects_missing_form_value(app, monkeypatch):
    monkeypatch.setattr(
        "internal.service.segment_service.SegmentService.update_segment_enabled",
        lambda *_args, **_kwargs: pytest.fail("missing enabled value reached service"),
    )

    with app.test_client() as client:
        response = client.post(
            f"/datasets/{UUID(int=1)}/documents/{UUID(int=2)}/segments/{UUID(int=3)}/enabled",
            data={},
        )

    assert response.json["code"] == HttpCode.VALIDATE_ERROR


@pytest.mark.parametrize("enabled", [True, False])
def test_update_segment_enabled_accepts_boolean_json(app, monkeypatch, enabled):
    received = {}
    monkeypatch.setattr(
        "internal.service.segment_service.SegmentService.update_segment_enabled",
        lambda _service, _dataset_id, _document_id, _segment_id, value, _user: received.update(enabled=value),
    )

    with app.test_client() as client:
        response = client.post(
            f"/datasets/{UUID(int=1)}/documents/{UUID(int=2)}/segments/{UUID(int=3)}/enabled",
            json={"enabled": enabled},
        )

    assert response.json["code"] == HttpCode.SUCCESS
    assert received["enabled"] is enabled
