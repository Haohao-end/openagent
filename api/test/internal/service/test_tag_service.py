import pytest
from types import SimpleNamespace
from uuid import uuid4

from internal.entity.tag_entity import TagType
from internal.exception import ValidateErrorException
from internal.model import App, AppTag, Tag, Workflow, WorkflowTag
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

    def order_by(self, *orders):
        self.order_bys.extend(orders)
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


def test_update_tag_should_filter_unallowed_fields_and_strip_strings(monkeypatch):
    service = TagService(db=SimpleNamespace(session=SimpleNamespace()))
    tag = SimpleNamespace(id=uuid4(), name="old", description="old_desc")
    monkeypatch.setattr(service, "_get_owned_tag", lambda *_args: tag)
    updates = []
    monkeypatch.setattr(service, "update", lambda target, **kwargs: updates.append(kwargs) or target)

    result = service.update_tag(
        tag.id,
        uuid4(),
        name="  new_tag  ",
        description="  new_desc  ",
        tag_type="system",
        status="inactive",
    )

    assert result is tag
    assert updates == [{"name": "new_tag", "description": "new_desc"}]


def test_update_tag_should_validate_name_and_description(monkeypatch):
    service = TagService(db=SimpleNamespace(session=SimpleNamespace()))
    tag = SimpleNamespace(id=uuid4(), name="old", description="old_desc")
    monkeypatch.setattr(service, "_get_owned_tag", lambda *_args: tag)

    with pytest.raises(ValidateErrorException, match="标签名称不能为空"):
        service.update_tag(tag.id, uuid4(), name="   ")

    with pytest.raises(ValidateErrorException, match="标签名称长度必须在 1-50 个字符之间"):
        service.update_tag(tag.id, uuid4(), name="a" * 51)

    with pytest.raises(ValidateErrorException, match="标签描述长度不能超过 200 个字符"):
        service.update_tag(tag.id, uuid4(), description="a" * 201)


def test_update_tag_no_update_called_when_all_fields_unallowed(monkeypatch):
    service = TagService(db=SimpleNamespace(session=SimpleNamespace()))
    tag = SimpleNamespace(id=uuid4(), name="old", description="old_desc")
    monkeypatch.setattr(service, "_get_owned_tag", lambda *_args: tag)
    updates = []
    monkeypatch.setattr(service, "update", lambda target, **kwargs: updates.append(kwargs) or target)

    result = service.update_tag(tag.id, uuid4(), tag_type="system", status="inactive")

    assert result is tag
    assert updates == []


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
    assert [str(order) for order in query.order_bys] == [
        "tag.created_at DESC",
        "tag.id DESC",
    ]


def test_get_hot_tags_should_group_by_dimension_and_count_usage():
    account_id = uuid4()
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

    hot_tags = service.get_hot_tags(account_id=account_id, limit_per_dimension=5)

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
    assert "tag.account_id" in str(tags_query.filters[0])
    assert app_counts_query.group_bys == [AppTag.tag_id]
    assert workflow_counts_query.group_bys == [WorkflowTag.tag_id]
    assert "app_tag.account_id" in str(app_counts_query.filters[0])
    assert "workflow_tag.account_id" in str(workflow_counts_query.filters[0])


def test_get_tag_dimensions_should_return_expected_labels():
    service = TagService(db=SimpleNamespace(session=SimpleNamespace()))

    dimensions = service.get_tag_dimensions()

    assert dimensions == [
        {"value": "custom", "label": "自定义标签"},
        {"value": "system", "label": "系统标签"},
        {"value": "category", "label": "分类标签"},
    ]


def test_add_app_and_workflow_tag_should_validate_tag_and_resource_ownership(monkeypatch):
    account_id = uuid4()
    app_id = uuid4()
    workflow_id = uuid4()
    unowned_tag_id = uuid4()
    owned_tag_id = uuid4()

    created = []
    service = TagService(
        db=SimpleNamespace(session=SimpleNamespace(query=lambda *_args: _QueryStub(one_or_none_result=None)))
    )

    def _fake_owned_resource(model, res_id, acc_id):
        if model is Tag and res_id == owned_tag_id and acc_id == account_id:
            return SimpleNamespace(id=res_id)
        if model is App and res_id == app_id and acc_id == account_id:
            return SimpleNamespace(id=res_id)
        if model is Workflow and res_id == workflow_id and acc_id == account_id:
            return SimpleNamespace(id=res_id)
        return None

    monkeypatch.setattr(service, "_get_owned_resource", _fake_owned_resource)
    monkeypatch.setattr(service, "create", lambda model, **kwargs: created.append((model, kwargs)) or kwargs)

    assert service.add_app_tag(account_id, app_id, unowned_tag_id) is None
    assert service.add_workflow_tag(account_id, workflow_id, unowned_tag_id) is None
    assert service.add_app_tag(account_id, uuid4(), owned_tag_id) is None
    assert service.add_workflow_tag(account_id, uuid4(), owned_tag_id) is None
    assert created == []

    app_tag = service.add_app_tag(account_id, app_id, owned_tag_id)
    assert app_tag is not None
    assert created[0] == (AppTag, {"account_id": account_id, "app_id": app_id, "tag_id": owned_tag_id})

    wf_tag = service.add_workflow_tag(account_id, workflow_id, owned_tag_id)
    assert wf_tag is not None
    assert created[1] == (WorkflowTag, {"account_id": account_id, "workflow_id": workflow_id, "tag_id": owned_tag_id})


def test_remove_app_and_workflow_tag_isolation_and_scoping(monkeypatch):
    account_a = uuid4()
    account_b = uuid4()
    app_a = uuid4()
    app_b = uuid4()
    workflow_a = uuid4()
    workflow_b = uuid4()
    tag_id = uuid4()

    deleted = []
    service = TagService(db=SimpleNamespace(session=SimpleNamespace()))
    service.delete = lambda item: deleted.append(item)

    def _fake_owned_resource(model, res_id, acc_id):
        if model is App and ((res_id == app_a and acc_id == account_a) or (res_id == app_b and acc_id == account_b)):
            return SimpleNamespace(id=res_id)
        if model is Workflow and ((res_id == workflow_a and acc_id == account_a) or (res_id == workflow_b and acc_id == account_b)):
            return SimpleNamespace(id=res_id)
        return None

    monkeypatch.setattr(service, "_get_owned_resource", _fake_owned_resource)

    app_tag_a = SimpleNamespace(account_id=account_a, app_id=app_a, tag_id=tag_id)
    wf_tag_a = SimpleNamespace(account_id=account_a, workflow_id=workflow_a, tag_id=tag_id)

    def _query(model):
        query = _QueryStub()
        def _one():
            if not query.filters:
                return None
            f = query.filters[0]
            values = {c.left.name: c.right.value for c in getattr(f, "clauses", [f]) if hasattr(c, "left") and hasattr(c, "right")}
            if model is AppTag and values.get("account_id") == account_a and values.get("app_id") == app_a and values.get("tag_id") == tag_id:
                return app_tag_a
            if model is WorkflowTag and values.get("account_id") == account_a and values.get("workflow_id") == workflow_a and values.get("tag_id") == tag_id:
                return wf_tag_a
            return None
        query.one_or_none = _one
        return query

    service.db.session.query = _query

    # 1. 账号 A 删除自己 App 的 Tag -> True
    assert service.remove_app_tag(app_a, tag_id, account_a) is True
    assert deleted == [app_tag_a]
    deleted.clear()

    # 2. 账号 A 删除自己 Workflow 的 Tag -> True
    assert service.remove_workflow_tag(workflow_a, tag_id, account_a) is True
    assert deleted == [wf_tag_a]
    deleted.clear()

    # 3. 账号 A 尝试删除账号 B 的 App Tag -> False
    assert service.remove_app_tag(app_b, tag_id, account_a) is False
    assert deleted == []

    # 4. 账号 A 尝试删除账号 B 的 Workflow Tag -> False
    assert service.remove_workflow_tag(workflow_b, tag_id, account_a) is False
    assert deleted == []

    # 5. account_id 缺失 -> False
    assert service.remove_app_tag(app_a, tag_id, None) is False
    assert service.remove_workflow_tag(workflow_a, tag_id, None) is False
    assert deleted == []

    # 6. 关联记录不存在 -> False
    assert service.remove_app_tag(app_a, uuid4(), account_a) is False
    assert service.remove_workflow_tag(workflow_a, uuid4(), account_a) is False
    assert deleted == []


def test_create_tag_should_validate_and_normalize_name_and_description():
    created = []
    service = TagService(db=SimpleNamespace(session=SimpleNamespace()))
    service.create = lambda model, **kwargs: created.append((model, kwargs)) or kwargs

    account_id = uuid4()
    with pytest.raises(ValidateErrorException, match="标签名称不能为空"):
        service.create_tag(account_id, "   ")

    with pytest.raises(ValidateErrorException, match="长度必须在 1-50 个字符之间"):
        service.create_tag(account_id, "a" * 51)

    with pytest.raises(ValidateErrorException, match="长度不能超过 200 个字符"):
        service.create_tag(account_id, "valid-name", "d" * 201)

    with pytest.raises(ValidateErrorException, match="标签类型不支持"):
        service.create_tag(account_id, "valid-name", "desc", tag_type="unsupported")

    res = service.create_tag(account_id, "  trimmed-name  ", "  trimmed-desc  ")
    assert res["name"] == "trimmed-name"
    assert res["description"] == "trimmed-desc"
    assert res["tag_type"] == "custom"


def test_get_app_and_workflow_tags_account_isolation(monkeypatch):
    service = TagService(db=SimpleNamespace(session=SimpleNamespace()))
    account_a = uuid4()
    account_b = uuid4()
    app_id = uuid4()
    wf_id = uuid4()
    tag = SimpleNamespace(id=uuid4(), name="demo")

    def _fake_owned(model, res_id, acc_id):
        if model is App and res_id == app_id and acc_id == account_a:
            return SimpleNamespace(id=res_id)
        if model is Workflow and res_id == wf_id and acc_id == account_a:
            return SimpleNamespace(id=res_id)
        return None

    monkeypatch.setattr(service, "_get_owned_resource", _fake_owned)

    def _query(model):
        q = _QueryStub()
        if model in (AppTag, WorkflowTag):
            q.all = lambda: [SimpleNamespace(tag_id=tag.id)]
        elif model is Tag:
            q.all = lambda: [tag]
        else:
            q.one_or_none = lambda: None
        return q

    service.db.session.query = _query

    # 1. 拥有者查询应用和工作流标签
    assert service.get_app_tags(app_id, account_id=account_a) == [tag]
    assert service.get_workflow_tags(wf_id, account_id=account_a) == [tag]

    # 2. 非拥有者查询私有应用和工作流标签 -> 空
    assert service.get_app_tags(app_id, account_id=account_b) == []
    assert service.get_workflow_tags(wf_id, account_id=account_b) == []

    # 3. 未传 account_id 保持兼容
    assert service.get_app_tags(app_id) == [tag]
    assert service.get_workflow_tags(wf_id) == [tag]
