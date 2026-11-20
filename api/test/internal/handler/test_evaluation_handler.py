from types import SimpleNamespace
from uuid import UUID

import pytest

from pkg.response import HttpCode


APP_ID = "00000000-0000-0000-0000-000000000010"
EVAL_ID = "00000000-0000-0000-0000-000000000020"


@pytest.fixture
def http_client(app):
    with app.test_client() as client:
        yield client


@pytest.fixture
def eval_user(monkeypatch):
    user = SimpleNamespace(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        is_authenticated=True,
    )
    monkeypatch.setattr("internal.handler.evaluation_handler.current_user", user)
    return user


def test_get_evaluations_should_return_list(http_client, eval_user, monkeypatch):
    expected_data = [
        {
            "id": EVAL_ID,
            "app_id": APP_ID,
            "name": "Benchmark v1",
            "created_by": str(eval_user.id),
            "created_at": 1700000000,
            "updated_at": 1700000000,
        }
    ]
    monkeypatch.setattr(
        "internal.service.evaluation_service.EvaluationService.get_evaluations",
        lambda _self, _app_id, _req, _account: expected_data,
    )

    resp = http_client.get(f"/apps/{APP_ID}/evaluations", query_string={"page": 1, "limit": 20})
    assert resp.status_code == 200
    json_data = resp.get_json()
    assert json_data["code"] == HttpCode.SUCCESS
    assert json_data["data"] == expected_data


def test_get_evaluations_should_validate_page(http_client, eval_user):
    resp = http_client.get(f"/apps/{APP_ID}/evaluations", query_string={"page": 0})
    assert resp.status_code == 200
    json_data = resp.get_json()
    assert json_data["code"] == HttpCode.VALIDATE_ERROR
    assert "page" in json_data["data"]


def test_create_evaluation_should_return_created(http_client, eval_user, monkeypatch):
    expected_data = {
        "id": EVAL_ID,
        "app_id": APP_ID,
        "name": "New Benchmark",
        "created_by": str(eval_user.id),
        "created_at": 1700000000,
        "updated_at": 1700000000,
    }
    monkeypatch.setattr(
        "internal.service.evaluation_service.EvaluationService.create_evaluation",
        lambda _self, _app_id, _req, _account: expected_data,
    )

    resp = http_client.post(f"/apps/{APP_ID}/evaluations", json={"name": "New Benchmark"})
    assert resp.status_code == 200
    json_data = resp.get_json()
    assert json_data["code"] == HttpCode.SUCCESS
    assert json_data["data"] == expected_data


def test_create_evaluation_should_validate_empty_name(http_client, eval_user):
    resp = http_client.post(f"/apps/{APP_ID}/evaluations", json={"name": ""})
    assert resp.status_code == 200
    json_data = resp.get_json()
    assert json_data["code"] == HttpCode.VALIDATE_ERROR
    assert "name" in json_data["data"]
