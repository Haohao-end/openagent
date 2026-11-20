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


def test_get_evaluation_should_return_detail(http_client, eval_user, monkeypatch):
    expected_data = {
        "id": EVAL_ID,
        "app_id": APP_ID,
        "name": "Benchmark Detail",
        "created_by": str(eval_user.id),
        "created_at": 1700000000,
        "updated_at": 1700000000,
    }
    monkeypatch.setattr(
        "internal.service.evaluation_service.EvaluationService.get_evaluation",
        lambda _self, _app_id, _eval_id, _account: expected_data,
    )

    resp = http_client.get(f"/apps/{APP_ID}/evaluations/{EVAL_ID}")
    assert resp.status_code == 200
    json_data = resp.get_json()
    assert json_data["code"] == HttpCode.SUCCESS
    assert json_data["data"] == expected_data


def test_update_evaluation_should_return_updated(http_client, eval_user, monkeypatch):
    expected_data = {
        "id": EVAL_ID,
        "app_id": APP_ID,
        "name": "Renamed Benchmark",
        "created_by": str(eval_user.id),
        "created_at": 1700000000,
        "updated_at": 1700000000,
    }
    monkeypatch.setattr(
        "internal.service.evaluation_service.EvaluationService.update_evaluation",
        lambda _self, _app_id, _eval_id, _req, _account: expected_data,
    )

    resp = http_client.put(f"/apps/{APP_ID}/evaluations/{EVAL_ID}", json={"name": "Renamed Benchmark"})
    assert resp.status_code == 200
    json_data = resp.get_json()
    assert json_data["code"] == HttpCode.SUCCESS
    assert json_data["data"] == expected_data


def test_delete_evaluation_should_return_id(http_client, eval_user, monkeypatch):
    monkeypatch.setattr(
        "internal.service.evaluation_service.EvaluationService.delete_evaluation",
        lambda _self, _app_id, _eval_id, _account: {"id": EVAL_ID},
    )

    resp = http_client.delete(f"/apps/{APP_ID}/evaluations/{EVAL_ID}")
    assert resp.status_code == 200
    json_data = resp.get_json()
    assert json_data["code"] == HttpCode.SUCCESS
    assert json_data["data"] == {"id": EVAL_ID}


def test_get_evaluation_cases_should_return_list(http_client, eval_user, monkeypatch):
    case_id = "00000000-0000-0000-0000-000000000030"
    expected_data = [
        {
            "id": case_id,
            "evaluation_id": EVAL_ID,
            "query": "What is Python?",
            "answer": "A programming language",
            "created_at": 1700000000,
            "updated_at": 1700000000,
        }
    ]
    monkeypatch.setattr(
        "internal.service.evaluation_service.EvaluationService.get_evaluation_cases",
        lambda _self, _app_id, _eval_id, _req, _account: expected_data,
    )

    resp = http_client.get(f"/apps/{APP_ID}/evaluations/{EVAL_ID}/cases", query_string={"page": 1, "limit": 20})
    assert resp.status_code == 200
    json_data = resp.get_json()
    assert json_data["code"] == HttpCode.SUCCESS
    assert json_data["data"] == expected_data


def test_create_evaluation_case_should_return_created(http_client, eval_user, monkeypatch):
    case_id = "00000000-0000-0000-0000-000000000030"
    expected_data = {
        "id": case_id,
        "evaluation_id": EVAL_ID,
        "query": "Sample question",
        "answer": "Sample answer",
        "created_at": 1700000000,
        "updated_at": 1700000000,
    }
    monkeypatch.setattr(
        "internal.service.evaluation_service.EvaluationService.create_evaluation_case",
        lambda _self, _app_id, _eval_id, _req, _account: expected_data,
    )

    resp = http_client.post(
        f"/apps/{APP_ID}/evaluations/{EVAL_ID}/cases",
        json={"query": "Sample question", "answer": "Sample answer"},
    )
    assert resp.status_code == 200
    json_data = resp.get_json()
    assert json_data["code"] == HttpCode.SUCCESS
    assert json_data["data"] == expected_data


def test_create_evaluation_case_should_validate_empty_query(http_client, eval_user):
    resp = http_client.post(
        f"/apps/{APP_ID}/evaluations/{EVAL_ID}/cases",
        json={"query": ""},
    )
    assert resp.status_code == 200
    json_data = resp.get_json()
    assert json_data["code"] == HttpCode.VALIDATE_ERROR
    assert "query" in json_data["data"]


def test_get_evaluation_case_should_return_detail(http_client, eval_user, monkeypatch):
    case_id = "00000000-0000-0000-0000-000000000030"
    expected_data = {
        "id": case_id,
        "evaluation_id": EVAL_ID,
        "query": "What is Python?",
        "answer": "A language",
        "created_at": 1700000000,
        "updated_at": 1700000000,
    }
    monkeypatch.setattr(
        "internal.service.evaluation_service.EvaluationService.get_evaluation_case",
        lambda _self, _app_id, _eval_id, _case_id, _account: expected_data,
    )

    resp = http_client.get(f"/apps/{APP_ID}/evaluations/{EVAL_ID}/cases/{case_id}")
    assert resp.status_code == 200
    json_data = resp.get_json()
    assert json_data["code"] == HttpCode.SUCCESS
    assert json_data["data"] == expected_data


def test_update_evaluation_case_should_return_updated(http_client, eval_user, monkeypatch):
    case_id = "00000000-0000-0000-0000-000000000030"
    expected_data = {
        "id": case_id,
        "evaluation_id": EVAL_ID,
        "query": "Updated query",
        "answer": "Updated answer",
        "created_at": 1700000000,
        "updated_at": 1700000000,
    }
    monkeypatch.setattr(
        "internal.service.evaluation_service.EvaluationService.update_evaluation_case",
        lambda _self, _app_id, _eval_id, _case_id, _req, _account: expected_data,
    )

    resp = http_client.put(
        f"/apps/{APP_ID}/evaluations/{EVAL_ID}/cases/{case_id}",
        json={"query": "Updated query", "answer": "Updated answer"},
    )
    assert resp.status_code == 200
    json_data = resp.get_json()
    assert json_data["code"] == HttpCode.SUCCESS
    assert json_data["data"] == expected_data


def test_delete_evaluation_case_should_return_id(http_client, eval_user, monkeypatch):
    case_id = "00000000-0000-0000-0000-000000000030"
    monkeypatch.setattr(
        "internal.service.evaluation_service.EvaluationService.delete_evaluation_case",
        lambda _self, _app_id, _eval_id, _case_id, _account: {"id": case_id},
    )

    resp = http_client.delete(f"/apps/{APP_ID}/evaluations/{EVAL_ID}/cases/{case_id}")
    assert resp.status_code == 200
    json_data = resp.get_json()
    assert json_data["code"] == HttpCode.SUCCESS
    assert json_data["data"] == {"id": case_id}
