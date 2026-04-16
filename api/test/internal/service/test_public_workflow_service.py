from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from internal.entity.app_category_entity import AppCategory
from internal.entity.workflow_entity import WorkflowStatus
from internal.exception import ForbiddenException, NotFoundException, ValidateErrorException
from internal.service.public_workflow_service import PublicWorkflowService


def _field(value):
    return SimpleNamespace(data=value)


def _req(*, tags="", sort_by="latest", search_word="", current_page=1, page_size=20):
    return SimpleNamespace(
        tags=_field(tags),
        sort_by=_field(sort_by),
        search_word=_field(search_word),
        current_page=_field(current_page),
        page_size=_field(page_size),
    )


class _Query:
    def __init__(self, *, one_or_none_result=None, all_result=None, scalar_result=None, count_result=0):
        self._one_or_none_result = one_or_none_result
        self._all_result = all_result if all_result is not None else []
        self._scalar_result = scalar_result
        self._count_result = count_result
        self.filter_args = ()
        self.order_by_args = ()

    def filter(self, *args, **_kwargs):
        self.filter_args = args
        return self

    def order_by(self, *args, **_kwargs):
        self.order_by_args = args
        return self

    def join(self, *_args, **_kwargs):
        return self

    def outerjoin(self, *_args, **_kwargs):
        return self

    def group_by(self, *_args, **_kwargs):
        return self

    def subquery(self):
        return SimpleNamespace(c=SimpleNamespace(workflow_id="workflow_id", favorite_count="favorite_count"))

    def one_or_none(self):
        return self._one_or_none_result

    def all(self):
        return self._all_result

    def count(self):
        return self._count_result

    def scalar(self):
        return self._scalar_result


class _QueueSession:
    def __init__(self, queries=None):
        self._queries = list(queries or [])
        self.queried_models = []
        self.added = []
        self.deleted = []
        self.commit_calls = 0

    def query(self, *model):
        self.queried_models.append(model)
        if self._queries:
            return self._queries.pop(0)
        return _Query()

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        if self.added and getattr(self.added[-1], "id", None) is None:
            self.added[-1].id = uuid4()

    def delete(self, obj):
        self.deleted.append(obj)

    def commit(self):
        self.commit_calls += 1


class _DB:
    def __init__(self, session):
        self.session = session
        self.auto_commit_calls = 0

    @contextmanager
    def auto_commit(self):
        self.auto_commit_calls += 1
        yield


class _FakeWorkflow:
    class _Col:
        def __eq__(self, _other):
            return self

    id = _Col()
    is_public = _Col()
    status = _Col()

    def __init__(self, **kwargs):
        self.id = kwargs.pop("id", None)
        self.__dict__.update(kwargs)


def _build_service(*, session=None):
    return PublicWorkflowService(db=_DB(session or _QueueSession()))


class TestPublicWorkflowService:
    def test_share_workflow_to_square_should_validate_exists_owner_status_and_accept_tags(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        workflow_id = uuid4()

        service = _build_service(session=_QueueSession([_Query(one_or_none_result=None)]))
        with pytest.raises(NotFoundException):
            service.share_workflow_to_square(workflow_id, AppCategory.GENERAL.value, account)

        foreign_workflow = SimpleNamespace(id=workflow_id, account_id=uuid4(), status=WorkflowStatus.PUBLISHED.value)
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=foreign_workflow)]))
        with pytest.raises(ForbiddenException):
            service.share_workflow_to_square(workflow_id, AppCategory.GENERAL.value, account)

        draft_workflow = SimpleNamespace(id=workflow_id, account_id=account.id, status=WorkflowStatus.DRAFT.value)
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=draft_workflow)]))
        with pytest.raises(ValidateErrorException):
            service.share_workflow_to_square(workflow_id, AppCategory.GENERAL.value, account)

        published = SimpleNamespace(
            id=workflow_id,
            account_id=account.id,
            status=WorkflowStatus.PUBLISHED.value,
            is_public=False,
            tags=[],
            published_at=None,
        )
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=published)]))
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: target.__dict__.update(kwargs) or target,
        )

        shared = service.share_workflow_to_square(workflow_id, AppCategory.GENERAL.value, account)

        assert shared.tags == [AppCategory.GENERAL.value]
        assert shared.is_public is True
        assert shared.published_at is not None

    def test_share_and_unshare_workflow_should_update_public_fields(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(id=uuid4(), account_id=account.id, status=WorkflowStatus.PUBLISHED.value)
        service = _build_service(
            session=_QueueSession([
                _Query(one_or_none_result=workflow),
                _Query(one_or_none_result=workflow),
            ])
        )
        updates = []

        def _update(target, **kwargs):
            updates.append((target, kwargs))
            for key, value in kwargs.items():
                setattr(target, key, value)
            return target

        monkeypatch.setattr(service, "update", _update)

        shared = service.share_workflow_to_square(workflow.id, AppCategory.GENERAL.value, account)
        unshared = service.unshare_workflow_from_square(workflow.id, account)

        assert shared is workflow
        assert unshared is workflow
        assert updates[0][1]["is_public"] is True
        assert updates[0][1]["tags"] == [AppCategory.GENERAL.value]
        assert updates[0][1]["published_at"] is not None
        assert updates[1][1] == {"is_public": False, "published_at": None}

    def test_unshare_workflow_from_square_should_validate_exists_and_owner(self):
        account = SimpleNamespace(id=uuid4())
        workflow_id = uuid4()

        service = _build_service(session=_QueueSession([_Query(one_or_none_result=None)]))
        with pytest.raises(NotFoundException):
            service.unshare_workflow_from_square(workflow_id, account)

        foreign_workflow = SimpleNamespace(id=workflow_id, account_id=uuid4(), status=WorkflowStatus.PUBLISHED.value)
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=foreign_workflow)]))
        with pytest.raises(ForbiddenException):
            service.unshare_workflow_from_square(workflow_id, account)

    def test_get_public_workflows_with_page_should_support_sorting_and_user_flags(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            name="wf",
            icon="https://icon",
            description="desc",
            tags=[AppCategory.GENERAL.value],
            view_count=9,
            like_count=4,
            fork_count=2,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            created_at=datetime(2025, 12, 31, tzinfo=UTC),
        )
        session = _QueueSession(
            [
                _Query(),  # favorite_count_subquery
                _Query(),  # query(Workflow, Account.name, favorite_count)
                _Query(all_result=[(workflow.id,)]),  # liked workflow ids
                _Query(all_result=[]),  # favorited workflow ids
                _Query(all_result=[(workflow.id,)]),  # forked workflow ids
            ]
        )
        service = _build_service(session=session)
        captures = {}

        class _Paginator:
            def __init__(self, db, req):
                captures["db"] = db
                captures["req"] = req

            def paginate(self, query):
                captures["query"] = query
                return [(workflow, "Owner", "https://avatar", 5)]

        monkeypatch.setattr("internal.service.public_workflow_service.Paginator", _Paginator)
        results, paginator = service.get_public_workflows_with_page(
            _req(sort_by="popular"),
            account,
        )

        assert isinstance(paginator, _Paginator)
        assert captures["query"] is not None
        assert len(results) == 1
        assert results[0]["id"] == str(workflow.id)
        assert results[0]["favorite_count"] == 5
        assert results[0]["is_liked"] is True
        assert results[0]["is_favorited"] is False
        assert results[0]["is_forked"] is True
        assert results[0]["account_name"] == "Owner"

    def test_get_my_likes_should_return_serialized_public_workflows(self):
        account = SimpleNamespace(id=uuid4())
        like_1 = SimpleNamespace(workflow_id=uuid4(), created_at=datetime(2026, 1, 2, tzinfo=UTC))
        like_2 = SimpleNamespace(workflow_id=uuid4(), created_at=datetime(2026, 1, 1, tzinfo=UTC))
        workflow_1 = SimpleNamespace(
            id=like_1.workflow_id,
            name="点赞工作流一",
            icon="https://wf/1.png",
            description="desc 1",
            tags=["assistant"],
            view_count=5,
            like_count=10,
            fork_count=1,
            published_at=datetime(2026, 1, 3, tzinfo=UTC),
            created_at=datetime(2025, 12, 3, tzinfo=UTC),
        )
        workflow_2 = SimpleNamespace(
            id=like_2.workflow_id,
            name="点赞工作流二",
            icon="https://wf/2.png",
            description="desc 2",
            tags=["workflow"],
            view_count=6,
            like_count=12,
            fork_count=2,
            published_at=datetime(2026, 1, 4, tzinfo=UTC),
            created_at=datetime(2025, 12, 4, tzinfo=UTC),
        )
        session = _QueueSession(
            [
                _Query(all_result=[like_1, like_2]),
                _Query(),  # favorite_count_subquery
                _Query(all_result=[(workflow_1, "Owner A", "https://avatar/1.png", 3), (workflow_2, None, "", 4)]),
                _Query(all_result=[(like_1.workflow_id,), (like_2.workflow_id,)]),  # liked ids
                _Query(all_result=[(like_2.workflow_id,)]),  # favorited ids
                _Query(all_result=[]),  # forked ids
            ]
        )
        service = _build_service(session=session)

        workflows = service.get_my_likes(account)

        assert [workflow["id"] for workflow in workflows] == [
            str(like_1.workflow_id),
            str(like_2.workflow_id),
        ]
        assert workflows[0]["is_liked"] is True
        assert workflows[0]["account_name"] == "Owner A"
        assert workflows[1]["is_favorited"] is True
        assert workflows[1]["account_name"] == "Unknown"

    def test_get_my_favorites_should_return_serialized_public_workflows(self):
        account = SimpleNamespace(id=uuid4())
        favorite_1 = SimpleNamespace(workflow_id=uuid4(), created_at=datetime(2026, 1, 2, tzinfo=UTC))
        favorite_2 = SimpleNamespace(workflow_id=uuid4(), created_at=datetime(2026, 1, 1, tzinfo=UTC))
        workflow_1 = SimpleNamespace(
            id=favorite_1.workflow_id,
            name="收藏工作流一",
            icon="https://wf/1.png",
            description="desc 1",
            tags=["assistant"],
            view_count=7,
            like_count=9,
            fork_count=3,
            published_at=datetime(2026, 1, 5, tzinfo=UTC),
            created_at=datetime(2025, 12, 5, tzinfo=UTC),
        )
        workflow_2 = SimpleNamespace(
            id=favorite_2.workflow_id,
            name="收藏工作流二",
            icon="https://wf/2.png",
            description="desc 2",
            tags=["workflow"],
            view_count=8,
            like_count=13,
            fork_count=4,
            published_at=datetime(2026, 1, 6, tzinfo=UTC),
            created_at=datetime(2025, 12, 6, tzinfo=UTC),
        )
        session = _QueueSession(
            [
                _Query(all_result=[favorite_1, favorite_2]),
                _Query(),  # favorite_count_subquery
                _Query(all_result=[(workflow_1, "Owner B", "https://avatar/2.png", 5), (workflow_2, "Owner C", "", 6)]),
                _Query(all_result=[]),  # liked ids
                _Query(all_result=[(favorite_1.workflow_id,), (favorite_2.workflow_id,)]),  # favorited ids
                _Query(all_result=[(favorite_1.workflow_id,)]),  # forked ids
            ]
        )
        service = _build_service(session=session)

        workflows = service.get_my_favorites(account)

        assert [workflow["id"] for workflow in workflows] == [
            str(favorite_1.workflow_id),
            str(favorite_2.workflow_id),
        ]
        assert workflows[0]["is_favorited"] is True
        assert workflows[0]["is_forked"] is True
        assert workflows[1]["favorite_count"] == 6
        assert workflows[0]["account_avatar"] == "https://avatar/2.png"
        assert workflows[0]["tags"] == ["assistant"]

    def test_get_public_workflows_with_page_should_cover_most_favorited_sort(self, monkeypatch):
        service = _build_service(session=_QueueSession([_Query(), _Query()]))

        class _Paginator:
            def __init__(self, db, req):
                pass

            def paginate(self, query):
                assert query is not None
                return []

        monkeypatch.setattr("internal.service.public_workflow_service.Paginator", _Paginator)
        records, paginator = service.get_public_workflows_with_page(_req(sort_by="most_favorited"), None)

        assert records == []
        assert isinstance(paginator, _Paginator)

    def test_get_public_workflows_with_page_should_support_tag_search_and_anonymous_user(self, monkeypatch):
        workflow = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            name="工作流 A",
            icon="https://icon",
            description="支持搜索",
            tags=[AppCategory.GENERAL.value],
            view_count=3,
            like_count=1,
            fork_count=0,
            published_at=datetime(2026, 2, 1, tzinfo=UTC),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        session = _QueueSession(
            [
                _Query(),  # favorite_count_subquery
                _Query(),  # query(Workflow, Account.name, favorite_count)
            ]
        )
        service = _build_service(session=session)

        class _Paginator:
            def __init__(self, db, req):
                self.db = db
                self.req = req

            def paginate(self, query):
                assert query is not None
                return [(workflow, None, None, 2)]

        monkeypatch.setattr("internal.service.public_workflow_service.Paginator", _Paginator)

        records, paginator = service.get_public_workflows_with_page(
            _req(tags=AppCategory.GENERAL.value, sort_by="latest", search_word="工作流"),
            None,
        )

        assert isinstance(paginator, _Paginator)
        assert records[0]["account_name"] == "Unknown"
        assert records[0]["is_liked"] is False
        assert records[0]["is_favorited"] is False
        assert records[0]["favorite_count"] == 2
        assert records[0]["tags"] == [AppCategory.GENERAL.value]

    def test_get_public_workflows_with_page_should_apply_tag_filter_in_sql_and_not_slice_twice(self, monkeypatch):
        workflow = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            name="工作流 B",
            icon="https://icon",
            description="分页回归测试",
            tags=[AppCategory.GENERAL.value],
            view_count=8,
            like_count=5,
            fork_count=1,
            published_at=datetime(2026, 2, 2, tzinfo=UTC),
            created_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
        session = _QueueSession(
            [
                _Query(),  # favorite_count_subquery
                _Query(),  # query(Workflow, Account.name, favorite_count)
            ]
        )
        service = _build_service(session=session)
        captures = {}

        class _Paginator:
            def __init__(self, db, req):
                captures["req"] = req

            def paginate(self, query):
                captures["query"] = query
                return [(workflow, "Owner", "https://avatar", 3)]

        monkeypatch.setattr("internal.service.public_workflow_service.Paginator", _Paginator)

        records, paginator = service.get_public_workflows_with_page(
            _req(tags=AppCategory.GENERAL.value, current_page=2, page_size=1),
            None,
        )

        assert isinstance(paginator, _Paginator)
        assert len(captures["query"].filter_args) == 3
        assert records == [
            {
                "id": str(workflow.id),
                "name": "工作流 B",
                "icon": "https://icon",
                "description": "分页回归测试",
                "tags": [AppCategory.GENERAL.value],
                "view_count": 8,
                "like_count": 5,
                "fork_count": 1,
                "favorite_count": 3,
                "published_at": int(workflow.published_at.timestamp()),
                "created_at": int(workflow.created_at.timestamp()),
                "is_liked": False,
                "is_favorited": False,
                "is_forked": False,
                "account_name": "Owner",
                "account_avatar": "https://avatar",
            }
        ]

    def test_get_public_workflows_with_page_should_not_trigger_deepseek_when_tags_missing(self, monkeypatch):
        workflow = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            name="未知工作流",
            icon="https://icon",
            description="没有明显关键词",
            tags=[],
            view_count=1,
            like_count=0,
            fork_count=0,
            published_at=datetime(2026, 2, 3, tzinfo=UTC),
            created_at=datetime(2026, 1, 3, tzinfo=UTC),
        )
        session = _QueueSession(
            [
                _Query(),  # favorite_count_subquery
                _Query(),  # query(Workflow, Account.name, favorite_count)
            ]
        )
        service = _build_service(session=session)

        monkeypatch.setattr(
            "internal.service.public_workflow_service.TagAssignmentService.match_tags_by_keywords",
            lambda *_args, **_kwargs: [],
        )
        monkeypatch.setattr(
            "internal.service.public_workflow_service.TagAssignmentService.assign_tags_by_deepseek",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("deepseek should not be called")),
        )

        class _Paginator:
            def __init__(self, db, req):
                pass

            def paginate(self, query):
                return [(workflow, None, None, 0)]

        monkeypatch.setattr("internal.service.public_workflow_service.Paginator", _Paginator)

        records, _ = service.get_public_workflows_with_page(_req(), None)

        assert records[0]["tags"] == ["other"]

    def test_fork_public_workflow_should_create_copy_and_update_counters(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        source = SimpleNamespace(
            id=uuid4(),
            is_public=True,
            status=WorkflowStatus.PUBLISHED.value,
            view_count=2,
            fork_count=3,
            name="公开工作流",
            tool_call_name="public_tool",
            icon="https://icon",
            description="desc",
            graph={"nodes": [], "edges": []},
            tags=[AppCategory.GENERAL.value],
        )
        session = _QueueSession([_Query(one_or_none_result=source)])
        service = _build_service(session=session)
        monkeypatch.setattr("internal.service.public_workflow_service.Workflow", _FakeWorkflow)
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: target.__dict__.update(kwargs) or target,
        )

        copied = service.fork_public_workflow(source.id, account)

        assert copied.name.endswith("(副本)")
        assert copied.original_workflow_id == source.id
        assert copied.status == WorkflowStatus.DRAFT.value
        assert copied.tags == source.tags
        assert source.view_count == 3
        assert source.fork_count == 4
        assert len(session.added) == 1
        assert service.db.auto_commit_calls == 1

    def test_fork_public_workflow_should_raise_when_source_missing(self):
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=None)]))
        with pytest.raises(NotFoundException):
            service.fork_public_workflow(uuid4(), SimpleNamespace(id=uuid4()))

    @pytest.mark.parametrize(
        "existing_like,expected",
        [
            (SimpleNamespace(id=uuid4()), {"is_liked": False, "like_count": 2}),
            (None, {"is_liked": True, "like_count": 4}),
        ],
    )
    def test_like_workflow_should_toggle(self, monkeypatch, existing_like, expected):
        workflow = SimpleNamespace(id=uuid4(), is_public=True, like_count=3)
        session = _QueueSession(
            [
                _Query(one_or_none_result=workflow),
                _Query(one_or_none_result=existing_like),
            ]
        )
        service = _build_service(session=session)
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: target.__dict__.update(kwargs) or target,
        )

        result = service.like_workflow(workflow.id, SimpleNamespace(id=uuid4()))

        assert result == expected
        assert workflow.like_count == expected["like_count"]
        assert session.commit_calls == 1

    def test_like_workflow_should_raise_when_workflow_not_public(self):
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=None)]))

        with pytest.raises(NotFoundException):
            service.like_workflow(uuid4(), SimpleNamespace(id=uuid4()))

    @pytest.mark.parametrize(
        "existing_favorite,is_favorited,count_result",
        [
            (SimpleNamespace(id=uuid4()), False, 2),
            (None, True, 5),
        ],
    )
    def test_favorite_workflow_should_toggle(self, existing_favorite, is_favorited, count_result):
        workflow = SimpleNamespace(id=uuid4(), is_public=True)
        session = _QueueSession(
            [
                _Query(one_or_none_result=workflow),
                _Query(one_or_none_result=existing_favorite),
                _Query(count_result=count_result),
            ]
        )
        service = _build_service(session=session)

        result = service.favorite_workflow(workflow.id, SimpleNamespace(id=uuid4()))

        assert result == {"is_favorited": is_favorited, "favorite_count": count_result}
        assert session.commit_calls == 1

    def test_favorite_workflow_should_raise_when_workflow_not_public(self):
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=None)]))

        with pytest.raises(NotFoundException):
            service.favorite_workflow(uuid4(), SimpleNamespace(id=uuid4()))

    def test_get_public_workflow_detail_should_raise_when_not_found(self):
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=None)]))
        with pytest.raises(NotFoundException):
            service.get_public_workflow_detail(uuid4(), None)

    def test_get_public_workflow_detail_should_return_detail_and_user_status(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            is_public=True,
            status=WorkflowStatus.PUBLISHED.value,
            is_debug_passed=True,
            name="wf",
            icon="https://icon",
            description="desc",
            tags=[AppCategory.GENERAL.value],
            view_count=10,
            like_count=3,
            fork_count=4,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
            updated_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
        creator = SimpleNamespace(id=workflow.account_id, name="Owner")
        session = _QueueSession(
            [
                _Query(one_or_none_result=workflow),
                _Query(one_or_none_result=creator),
                _Query(scalar_result=7),
                _Query(one_or_none_result=SimpleNamespace(id=uuid4())),
                _Query(one_or_none_result=None),
            ]
        )
        service = _build_service(session=session)
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: target.__dict__.update(kwargs) or target,
        )

        detail = service.get_public_workflow_detail(workflow.id, account)

        assert detail["id"] == str(workflow.id)
        assert detail["status"] == WorkflowStatus.PUBLISHED.value
        assert detail["is_debug_passed"] is True
        assert detail["favorite_count"] == 7
        assert detail["tags"] == [AppCategory.GENERAL.value]
        assert detail["is_liked"] is True
        assert detail["is_favorited"] is False
        assert workflow.view_count == 11

    def test_get_public_workflow_detail_should_default_flags_when_account_absent(self, monkeypatch):
        workflow = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            is_public=True,
            status=WorkflowStatus.PUBLISHED.value,
            is_debug_passed=False,
            name="wf",
            icon="https://icon",
            description="desc",
            tags=[AppCategory.GENERAL.value],
            view_count=1,
            like_count=0,
            fork_count=0,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
            updated_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
        session = _QueueSession(
            [
                _Query(one_or_none_result=workflow),
                _Query(one_or_none_result=None),  # account not found
                _Query(scalar_result=None),  # favorite count fallback to 0
            ]
        )
        service = _build_service(session=session)
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: target.__dict__.update(kwargs) or target,
        )

        detail = service.get_public_workflow_detail(workflow.id, None)

        assert detail["account_name"] == "Unknown"
        assert detail["favorite_count"] == 0
        assert detail["tags"] == [AppCategory.GENERAL.value]
        assert detail["is_liked"] is False
        assert detail["is_favorited"] is False

    def test_get_public_workflow_draft_graph_should_convert_node_and_edge_fields(self):
        workflow = SimpleNamespace(
            id=uuid4(),
            is_public=True,
            status=WorkflowStatus.PUBLISHED.value,
            graph={
                "nodes": [
                    {
                        "id": "node-1",
                        "node_type": "start",
                        "position": {"x": 0, "y": 0},
                        "title": "start",
                        "foo": "bar",
                    }
                ],
                "edges": [
                    {
                        "id": "edge-1",
                        "source": "node-1",
                        "target": "node-2",
                        "source_handle": "s1",
                        "target_handle": "t1",
                    }
                ],
            },
        )
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=workflow)]))

        graph = service.get_public_workflow_draft_graph(workflow.id)

        assert graph["nodes"][0]["type"] == "start"
        assert graph["nodes"][0]["data"]["foo"] == "bar"
        assert "foo" not in graph["nodes"][0]
        assert graph["edges"][0]["sourceHandle"] == "s1"
        assert graph["edges"][0]["targetHandle"] == "t1"

    def test_get_public_workflow_draft_graph_should_support_empty_graph_and_not_found(self):
        workflow = SimpleNamespace(id=uuid4(), is_public=True, status=WorkflowStatus.PUBLISHED.value, graph=None)
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=workflow)]))
        graph = service.get_public_workflow_draft_graph(workflow.id)
        assert graph == {"nodes": [], "edges": []}

        service = _build_service(session=_QueueSession([_Query(one_or_none_result=None)]))
        with pytest.raises(NotFoundException):
            service.get_public_workflow_draft_graph(uuid4())

    def test_get_public_workflow_draft_graph_should_keep_existing_node_data_and_edge_handles_when_missing(self):
        workflow = SimpleNamespace(
            id=uuid4(),
            is_public=True,
            status=WorkflowStatus.PUBLISHED.value,
            graph={
                "nodes": [
                    {
                        "id": "node-1",
                        "type": "start",
                        "position": {"x": 0, "y": 0},
                        "data": {"title": "start"},
                    }
                ],
                "edges": [
                    {
                        "id": "edge-1",
                        "source": "node-1",
                        "target": "node-2",
                    }
                ],
            },
        )
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=workflow)]))

        graph = service.get_public_workflow_draft_graph(workflow.id)

        assert graph["nodes"][0]["type"] == "start"
        assert graph["nodes"][0]["data"] == {"title": "start"}
        assert "sourceHandle" not in graph["edges"][0]
        assert "targetHandle" not in graph["edges"][0]

    def test_get_public_workflow_draft_graph_should_return_graph_when_nodes_and_edges_keys_missing(self):
        workflow = SimpleNamespace(
            id=uuid4(),
            is_public=True,
            status=WorkflowStatus.PUBLISHED.value,
            graph={"meta": {"version": 1}},
        )
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=workflow)]))

        graph = service.get_public_workflow_draft_graph(workflow.id)

        assert graph == {"meta": {"version": 1}}

    def test_get_public_workflow_draft_graph_should_cover_nonstandard_node_contains_branch(self):
        class _WeirdNode(dict):
            def __contains__(self, key):
                if key == "foo":
                    return False
                return super().__contains__(key)

        workflow = SimpleNamespace(
            id=uuid4(),
            is_public=True,
            status=WorkflowStatus.PUBLISHED.value,
            graph={
                "nodes": [
                    _WeirdNode(
                        {
                            "id": "node-1",
                            "node_type": "start",
                            "position": {"x": 0, "y": 0},
                            "foo": "bar",
                        }
                    )
                ],
                "edges": [],
            },
        )
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=workflow)]))

        graph = service.get_public_workflow_draft_graph(workflow.id)

        assert graph["nodes"][0]["type"] == "start"
        assert graph["nodes"][0]["data"]["foo"] == "bar"

    def test_get_public_workflow_draft_graph_should_cover_additional_conversion_branches(self):
        workflow = SimpleNamespace(
            id=uuid4(),
            is_public=True,
            status=WorkflowStatus.PUBLISHED.value,
            graph={
                "nodes": [
                    {
                        "id": "node-1",
                        "type": "start",
                        "position": {"x": 0, "y": 0},
                        "data": {"existing": True},
                        "foo": "keep",
                    },
                    {
                        "id": "node-2",
                        "position": {"x": 1, "y": 1},
                        "foo": "bar",
                        "bar": "baz",
                    },
                ],
                "edges": [
                    {"id": "edge-1", "source": "node-1", "target": "node-2"},
                    {
                        "id": "edge-2",
                        "source": "node-1",
                        "target": "node-2",
                        "source_handle": "s2",
                    },
                ],
            },
        )
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=workflow)]))

        graph = service.get_public_workflow_draft_graph(workflow.id)

        assert graph["nodes"][0]["data"] == {"existing": True}
        assert graph["nodes"][0]["foo"] == "keep"
        assert graph["nodes"][1]["data"] == {"foo": "bar", "bar": "baz"}
        assert "foo" not in graph["nodes"][1]
        assert "bar" not in graph["nodes"][1]
        assert "sourceHandle" not in graph["edges"][0]
        assert "targetHandle" not in graph["edges"][0]
        assert graph["edges"][1]["sourceHandle"] == "s2"
        assert "targetHandle" not in graph["edges"][1]

        workflow_only_nodes = SimpleNamespace(
            id=uuid4(),
            is_public=True,
            status=WorkflowStatus.PUBLISHED.value,
            graph={"nodes": [{"id": "n1", "node_type": "start", "position": {"x": 0, "y": 0}}]},
        )
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=workflow_only_nodes)]))
        graph_only_nodes = service.get_public_workflow_draft_graph(workflow_only_nodes.id)
        assert graph_only_nodes["nodes"][0]["type"] == "start"

        workflow_only_edges = SimpleNamespace(
            id=uuid4(),
            is_public=True,
            status=WorkflowStatus.PUBLISHED.value,
            graph={"edges": [{"id": "e1", "source": "a", "target": "b"}]},
        )
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=workflow_only_edges)]))
        graph_only_edges = service.get_public_workflow_draft_graph(workflow_only_edges.id)
        assert graph_only_edges["edges"][0]["id"] == "e1"
