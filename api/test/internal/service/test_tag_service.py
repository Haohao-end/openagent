from types import SimpleNamespace
from uuid import uuid4

from internal.entity.tag_entity import TagType
from internal.model import AppTag, Tag, WorkflowTag
from internal.service.tag_service import TagService


class _QueryStub:
    def __init__(self, *, one_or_none_result=None, all_result=None):
        self.one_or_none_result = one_or_none_result
        self.all_result = list(all_result or [])
        self.filters = []
        self.order_bys = []
        self.group_bys = []

    def filter(self, condition):
        self.filters.append(condition)
        return self

    def order_by(self, order):
        self.order_bys.append(order)
        return self

    def group_by(self, column):
        self.group_bys.append(column)
        return self

    def one_or_none(self):
        return self.one_or_none_result

    def all(self):
        return self.all_result


def _page_req(current_page: int = 1, page_size: int = 20):
    return SimpleNamespace(
        current_page=SimpleNamespace(data=current_page),
        page_size=SimpleNamespace(data=page_size),
    )


def test_get_tag_by_id_should_scope_to_account():
    tag_id = uuid4()
    account_id = uuid4()
    tag = SimpleNamespace(id=tag_id, account_id=account_id)
    query = _QueryStub(one_or_none_result=tag)
    service = TagService(db=SimpleNamespace(session=SimpleNamespace(query=lambda *_args: query)))

    result = service.get_tag_by_id(tag_id, account_id)

    assert result is tag
    assert len(query.filters) == 1
    condition = str(query.filters[0])
    assert "tag.id" in condition
    assert "tag.account_id" in condition


def test_update_tag_should_refuse_cross_account_update(monkeypatch):
    service = TagService(db=SimpleNamespace(session=SimpleNamespace()))
    update_calls = []
    monkeypatch.setattr(service, "_get_owned_tag", lambda *_args: None)
    monkeypatch.setattr(service, "update", lambda *_args, **_kwargs: update_calls.append(True))

    result = service.update_tag(uuid4(), uuid4(), name="hacked")

    assert result is None
    assert update_calls == []


def test_delete_tag_should_refuse_cross_account_delete(monkeypatch):
    service = TagService(db=SimpleNamespace(session=SimpleNamespace()))
    delete_calls = []
    monkeypatch.setattr(service, "_get_owned_tag", lambda *_args: None)
    monkeypatch.setattr(service, "delete", lambda *_args, **_kwargs: delete_calls.append(True))

    result = service.delete_tag(uuid4(), uuid4())

    assert result is None
    assert delete_calls == []


def test_get_tags_with_page_should_filter_owner_and_build_paginator(monkeypatch):
    owner_id = uuid4()
    query = _QueryStub()
    expected_tags = [SimpleNamespace(name="tag-a"), SimpleNamespace(name="tag-b")]
    created_paginators = []

    class _FakePaginator:
        def __init__(self, db, req):
            self.db = db
            self.current_page = req.current_page.data
            self.page_size = req.page_size.data
            self.total_record = 0
            self.total_page = 0
            self.query = None
            created_paginators.append(self)

        def paginate(self, select):
            self.query = select
            self.total_record = len(expected_tags)
            self.total_page = 1
            return expected_tags

    service = TagService(db=SimpleNamespace(session=SimpleNamespace(query=lambda *_args: query)))
    monkeypatch.setattr("internal.service.tag_service.Paginator", _FakePaginator)

    tags, paginator = service.get_tags_with_page(_page_req(), owner_id)

    assert tags == expected_tags
    assert paginator is created_paginators[0]
    assert paginator.current_page == 1
    assert paginator.page_size == 20
    assert paginator.total_record == 2
    assert paginator.total_page == 1
    assert len(query.filters) == 1
    condition = str(query.filters[0])
    assert "tag.account_id" in condition
    assert "tag.status" in condition
    assert query.order_bys


def test_get_hot_tags_should_group_by_dimension_and_count_usage():
    hot_tag_id = uuid4()
    system_tag_id = uuid4()
    category_tag_id = uuid4()
    hot_tag = SimpleNamespace(id=hot_tag_id, name="hot-tag", tag_type=TagType.CUSTOM.value)
    system_tag = SimpleNamespace(id=system_tag_id, name="system-tag", tag_type=TagType.SYSTEM.value)
    category_tag = SimpleNamespace(id=category_tag_id, name="category-tag", tag_type=TagType.CATEGORY.value)

    app_counts_query = _QueryStub(all_result=[(hot_tag_id, 1)])
    workflow_counts_query = _QueryStub(all_result=[(hot_tag_id, 2), (system_tag_id, 1)])
    tags_query = _QueryStub(all_result=[system_tag, hot_tag, category_tag])

    def _query(*args):
        target = args[0]
        if getattr(target, "class_", None) is AppTag:
            return app_counts_query
        if getattr(target, "class_", None) is WorkflowTag:
            return workflow_counts_query
        if target is Tag:
            return tags_query
        raise AssertionError(f"unexpected query target: {args}")

    service = TagService(db=SimpleNamespace(session=SimpleNamespace(query=_query)))

    hot_tags = service.get_hot_tags(limit_per_dimension=5)

    assert hot_tags["custom"] == [
        {
            "id": str(hot_tag_id),
            "name": "hot-tag",
            "dimension": TagType.CUSTOM.value,
            "use_count": 3,
        }
    ]
    assert hot_tags["system"] == [
        {
            "id": str(system_tag_id),
            "name": "system-tag",
            "dimension": TagType.SYSTEM.value,
            "use_count": 1,
        }
    ]
    assert hot_tags["category"] == [
        {
            "id": str(category_tag_id),
            "name": "category-tag",
            "dimension": TagType.CATEGORY.value,
            "use_count": 0,
        }
    ]
    assert len(tags_query.filters) == 1
    assert "tag.status" in str(tags_query.filters[0])
    assert app_counts_query.group_bys == [AppTag.tag_id]
    assert workflow_counts_query.group_bys == [WorkflowTag.tag_id]


def test_get_tag_dimensions_should_return_expected_labels():
    service = TagService(db=SimpleNamespace(session=SimpleNamespace()))

    dimensions = service.get_tag_dimensions()

    assert dimensions == [
        {"value": "custom", "label": "自定义标签"},
        {"value": "system", "label": "系统标签"},
        {"value": "category", "label": "分类标签"},
    ]
