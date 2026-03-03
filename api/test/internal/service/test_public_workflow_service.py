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


def _req(*, category="all", sort_by="latest", search_word="", current_page=1, page_size=20):
    return SimpleNamespace(
        category=_field(category),
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
    def test_share_workflow_to_square_should_validate_exists_owner_status_and_category(self):
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

        published = SimpleNamespace(id=workflow_id, account_id=account.id, status=WorkflowStatus.PUBLISHED.value)
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=published)]))
        with pytest.raises(ValidateErrorException):
            service.share_workflow_to_square(workflow_id, "invalid-category", account)

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
        assert updates[0][1]["category"] == AppCategory.GENERAL.value
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
            category=AppCategory.GENERAL.value,
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
                return [(workflow, "Owner", 5)]

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
        assert results[0]["account_name"] == "Owner"

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

    def test_get_public_workflows_with_page_should_support_category_search_and_anonymous_user(self, monkeypatch):
        workflow = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            name="工作流 A",
            icon="https://icon",
            description="支持搜索",
            category=AppCategory.GENERAL.value,
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
                return [(workflow, None, 2)]

        monkeypatch.setattr("internal.service.public_workflow_service.Paginator", _Paginator)

        records, paginator = service.get_public_workflows_with_page(
            _req(category=AppCategory.GENERAL.value, sort_by="latest", search_word="工作流"),
            None,
        )

        assert isinstance(paginator, _Paginator)
        assert records[0]["account_name"] == "Unknown"
        assert records[0]["is_liked"] is False
        assert records[0]["is_favorited"] is False
        assert records[0]["favorite_count"] == 2

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
            category=AppCategory.GENERAL.value,
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
            category=AppCategory.GENERAL.value,
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
            category=AppCategory.GENERAL.value,
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
