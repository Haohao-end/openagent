from datetime import datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from pkg.paginator import Paginator
from pkg.response import HttpCode


TAG_ID = "00000000-0000-0000-0000-000000000101"


def _paginator(current_page: int = 1, page_size: int = 20, total_record: int = 1):
    paginator = Paginator(db=SimpleNamespace())
    paginator.current_page = current_page
    paginator.page_size = page_size
    paginator.total_record = total_record
    paginator.total_page = 1
    return paginator


@pytest.fixture
def http_client(app):
    with app.test_client() as client:
        yield client


@pytest.fixture
def tag_user(monkeypatch):
    user = SimpleNamespace(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        is_authenticated=True,
    )
    monkeypatch.setattr("internal.handler.tag_handler.current_user", user)
    return user


def test_create_tag_should_delegate_and_return_id(http_client, tag_user, monkeypatch):
    captures = {}

    def _create_tag(_self, account_id, name, description="", tag_type="custom"):
        captures["account_id"] = account_id
        captures["name"] = name
        captures["description"] = description
        captures["tag_type"] = tag_type
        return SimpleNamespace(id=UUID(TAG_ID))

    monkeypatch.setattr(
        "internal.service.tag_service.TagService.create_tag",
        _create_tag,
    )

    resp = http_client.post(
        "/tags",
        json={"name": "important", "description": "desc", "tag_type": "system"},
    )

    assert resp.status_code == 200
    assert resp.json["code"] == HttpCode.SUCCESS
    assert resp.json["data"]["id"] == TAG_ID
    assert captures["account_id"] is tag_user.id
    assert captures["name"] == "important"
    assert captures["description"] == "desc"
    assert captures["tag_type"] == "system"


def test_create_tag_should_validate_invalid_tag_type(http_client, tag_user):
    resp = http_client.post(
        "/tags",
        json={"name": "important", "description": "desc", "tag_type": "invalid-type"},
    )

    assert resp.status_code == 200
    assert resp.json["code"] == HttpCode.VALIDATE_ERROR
    assert resp.json["message"] == "标签类型不支持"


def test_list_tags_should_validate_and_return_page_model(http_client, tag_user, monkeypatch):
    captures = {}

    def _get_tags_with_page(_self, req, account_id, status="active"):
        captures["req"] = req
        captures["account_id"] = account_id
        captures["status"] = status
        tags = [
            SimpleNamespace(
                id=UUID(TAG_ID),
                name="important",
                description="desc",
                tag_type="custom",
                status="active",
                created_at=datetime(2024, 1, 1, 0, 0, 0),
                updated_at=datetime(2024, 1, 2, 0, 0, 0),
            )
        ]
        return tags, _paginator(current_page=2, page_size=10, total_record=1)

    monkeypatch.setattr(
        "internal.service.tag_service.TagService.get_tags_with_page",
        _get_tags_with_page,
    )

    resp = http_client.get("/tags", query_string={"current_page": 2, "page_size": 10})

    assert resp.status_code == 200
    assert resp.json["code"] == HttpCode.SUCCESS
    assert resp.json["data"]["paginator"]["current_page"] == 2
    assert resp.json["data"]["paginator"]["page_size"] == 10
    assert resp.json["data"]["list"][0]["id"] == TAG_ID
    assert resp.json["data"]["list"][0]["name"] == "important"
    assert captures["account_id"] is tag_user.id
    assert captures["req"].current_page.data == 2
    assert captures["req"].page_size.data == 10


def test_get_tag_should_return_not_found_when_missing(http_client, tag_user, monkeypatch):
    monkeypatch.setattr(
        "internal.service.tag_service.TagService.get_tag_by_id",
        lambda _self, _tag_id, _account_id: None,
    )

    resp = http_client.get(f"/tags/{TAG_ID}")

    assert resp.status_code == 200
    assert resp.json["code"] == HttpCode.NOT_FOUND
    assert resp.json["message"] == "标签不存在"


def test_update_tag_should_delegate_and_return_success(http_client, tag_user, monkeypatch):
    captures = {}

    def _update_tag(_self, tag_id, account_id, **kwargs):
        captures["tag_id"] = tag_id
        captures["account_id"] = account_id
        captures["kwargs"] = kwargs
        return SimpleNamespace(id=tag_id)

    monkeypatch.setattr(
        "internal.service.tag_service.TagService.update_tag",
        _update_tag,
    )

    resp = http_client.post(
        f"/tags/{TAG_ID}",
        json={"name": "updated", "description": "new-desc"},
    )

    assert resp.status_code == 200
    assert resp.json["code"] == HttpCode.SUCCESS
    assert resp.json["data"] == {}
    assert resp.json["message"] == "更新标签成功"
    assert captures["tag_id"] == UUID(TAG_ID)
    assert captures["account_id"] is tag_user.id
    assert captures["kwargs"] == {"name": "updated", "description": "new-desc"}


def test_delete_tag_should_delegate_and_return_success(http_client, tag_user, monkeypatch):
    captures = {}

    def _delete_tag(_self, tag_id, account_id):
        captures["tag_id"] = tag_id
        captures["account_id"] = account_id
        return SimpleNamespace(id=tag_id)

    monkeypatch.setattr(
        "internal.service.tag_service.TagService.delete_tag",
        _delete_tag,
    )

    resp = http_client.post(f"/tags/{TAG_ID}/delete", json={})

    assert resp.status_code == 200
    assert resp.json["code"] == HttpCode.SUCCESS
    assert resp.json["data"] == {}
    assert resp.json["message"] == "删除标签成功"
    assert captures["tag_id"] == UUID(TAG_ID)
    assert captures["account_id"] is tag_user.id


def test_get_hot_tags_should_return_expected_structure(http_client, monkeypatch):
    monkeypatch.setattr(
        "internal.service.tag_service.TagService.get_hot_tags",
        lambda _self: {
            "custom": [
                {
                    "id": TAG_ID,
                    "name": "important",
                    "dimension": "custom",
                    "use_count": 3,
                }
            ],
            "system": [],
            "category": [],
        },
    )

    resp = http_client.get("/tags/hot")

    assert resp.status_code == 200
    assert resp.json["code"] == HttpCode.SUCCESS
    assert resp.json["data"]["hot_tags"]["custom"][0]["id"] == TAG_ID
    assert resp.json["data"]["hot_tags"]["custom"][0]["dimension"] == "custom"
    assert resp.json["data"]["hot_tags"]["custom"][0]["use_count"] == 3


def test_get_tag_dimensions_should_return_expected_structure(http_client, monkeypatch):
    monkeypatch.setattr(
        "internal.service.tag_service.TagService.get_tag_dimensions",
        lambda _self: [
            {"value": "custom", "label": "自定义标签"},
            {"value": "system", "label": "系统标签"},
            {"value": "category", "label": "分类标签"},
        ],
    )

    resp = http_client.get("/tags/dimensions")

    assert resp.status_code == 200
    assert resp.json["code"] == HttpCode.SUCCESS
    assert resp.json["data"]["dimensions"] == [
        {"value": "custom", "label": "自定义标签"},
        {"value": "system", "label": "系统标签"},
        {"value": "category", "label": "分类标签"},
    ]
