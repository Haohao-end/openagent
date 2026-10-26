from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from internal.entity.app_category_entity import AppCategory
from internal.entity.workflow_entity import WorkflowStatus
from internal.exception import ForbiddenException, NotFoundException, ValidateErrorException
from internal.service.public_workflow_service import PublicWorkflowService


@pytest.fixture
def _asia_shanghai_timezone():
    import os
    import time

    previous_timezone = os.environ.get("TZ")
    os.environ["TZ"] = "Asia/Shanghai"
    time.tzset()
    try:
        yield
    finally:
        if previous_timezone is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous_timezone
        time.tzset()


def _field(value):
    return SimpleNamespace(data=value)


def _req(*, tags="", search_word="", current_page=1, page_size=20):
    return SimpleNamespace(
        tags=_field(tags),
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
        return self

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

        def in_(self, *_args, **_kwargs):
            return self

        def isnot(self, *_args, **_kwargs):
            return self

    id = _Col()
    is_public = _Col()
    status = _Col()
    account_id = _Col()
    original_workflow_id = _Col()
    tags = _Col()

    def __init__(self, **kwargs):
        self.id = kwargs.pop("id", None)
        self.__dict__.update(kwargs)


def _build_service(*, session=None):
    return PublicWorkflowService(db=_DB(session or _QueueSession()))


class TestPublicWorkflowService:
    def test_share_workflow_to_square_should_validate_exists_owner_status_and_accept_tags(self):
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
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: target.__dict__.update(kwargs) or target,
        )
        try:
            shared = service.share_workflow_to_square(workflow_id, AppCategory.GENERAL.value, account)
        finally:
            monkeypatch.undo()

        assert shared.tags == [AppCategory.GENERAL.value]
        assert shared.is_public is True
        assert shared.published_at is not None

    def test_share_workflow_to_square_should_fallback_to_other_when_tags_missing(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        workflow_id = uuid4()
        published = SimpleNamespace(
            id=workflow_id,
            account_id=account.id,
            status=WorkflowStatus.PUBLISHED.value,
            is_public=False,
            tags=[],
            name="1231231123",
            description="",
            published_at=None,
        )
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=published)]))
        monkeypatch.setattr(
            "internal.service.public_workflow_service.TagAssignmentService.match_tags_by_keywords",
            lambda *_args, **_kwargs: [],
        )
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: target.__dict__.update(kwargs) or target,
        )

        shared = service.share_workflow_to_square(workflow_id, "", account)

        assert shared.tags == ["other"]
        assert shared.is_public is True
        assert shared.published_at is not None

    def test_share_and_unshare_workflow_should_update_public_fields(self):
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

        service.update = _update

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

    def test_get_public_workflows_with_page_should_return_basic_fields_and_fork_status(self, monkeypatch, _asia_shanghai_timezone):
        account = SimpleNamespace(id=uuid4())
        workflow = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            name="wf",
            icon="https://icon",
            description="desc",
            tags=[AppCategory.GENERAL.value],
            published_at=datetime(2026, 1, 1),
            created_at=datetime(2025, 12, 31),
        )
        session = _QueueSession([
            _Query(),
            _Query(all_result=[(workflow.id,)]),
        ])
        service = _build_service(session=session)
        captured = {}

        class _Paginator:
            def __init__(self, db, req):
                self.db = db
                self.req = req

            def paginate(self, query):
                captured["query"] = query
                return [(workflow, "Owner", "https://avatar")]

        monkeypatch.setattr("internal.service.public_workflow_service.Paginator", _Paginator)
        records, paginator = service.get_public_workflows_with_page(
            _req(tags="general", current_page=1, page_size=20),
            account,
        )

        assert isinstance(paginator, _Paginator)
        assert captured["query"] is not None
        assert records == [
            {
                "id": str(workflow.id),
                "name": "wf",
                "icon": "https://icon",
                "description": "desc",
                "tags": [AppCategory.GENERAL.value],
                "published_at": int(datetime(2026, 1, 1, tzinfo=UTC).timestamp()),
                "created_at": int(datetime(2025, 12, 31, tzinfo=UTC).timestamp()),
                "is_forked": True,
                "account_name": "Owner",
                "account_avatar": "https://avatar",
            }
        ]

    def test_get_public_workflows_with_page_should_default_tags_to_other_when_matching_fails(self, monkeypatch):
        workflow = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            name="未知工作流",
            icon="https://icon",
            description="没有明显关键词",
            tags=[],
            published_at=datetime(2026, 2, 1, tzinfo=UTC),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        session = _QueueSession()
        service = _build_service(session=session)

        monkeypatch.setattr(
            "internal.service.public_workflow_service.TagAssignmentService.match_tags_by_keywords",
            lambda *_args, **_kwargs: [],
        )
        monkeypatch.setattr(
            "internal.service.public_workflow_service.Paginator",
            lambda db, req: SimpleNamespace(
                paginate=lambda query: [(workflow, None, None)]
            ),
        )

        records, _ = service.get_public_workflows_with_page(_req(), None)

        assert records[0]["tags"] == ["other"]
        assert records[0]["account_name"] == "Unknown"
        assert records[0]["is_forked"] is False

    def test_fork_public_workflow_should_create_copy_and_set_draft_state(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        source = SimpleNamespace(
            id=uuid4(),
            is_public=True,
            status=WorkflowStatus.PUBLISHED.value,
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

        copied = service.fork_public_workflow(source.id, account)

        assert copied.name.endswith("(副本)")
        assert copied.original_workflow_id == source.id
        assert copied.status == WorkflowStatus.DRAFT.value
        assert copied.tags == [AppCategory.GENERAL.value]
        assert copied.draft_graph == source.graph
        assert copied.graph == {}
        assert len(session.added) == 1
        assert service.db.auto_commit_calls == 1

    def test_fork_public_workflow_should_raise_when_source_missing(self):
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=None)]))
        with pytest.raises(NotFoundException):
            service.fork_public_workflow(uuid4(), SimpleNamespace(id=uuid4()))

    def test_get_public_workflow_detail_should_return_detail_and_fork_status(self):
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
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
            updated_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
        creator = SimpleNamespace(id=workflow.account_id, name="Owner", avatar="https://avatar")
        session = _QueueSession(
            [
                _Query(one_or_none_result=workflow),
                _Query(one_or_none_result=creator),
                _Query(one_or_none_result=SimpleNamespace(id=uuid4())),
            ]
        )
        service = _build_service(session=session)

        detail = service.get_public_workflow_detail(workflow.id, account)

        assert detail == {
            "id": str(workflow.id),
            "name": "wf",
            "icon": "https://icon",
            "description": "desc",
            "tags": [AppCategory.GENERAL.value],
            "status": WorkflowStatus.PUBLISHED.value,
            "is_public": True,
            "is_debug_passed": True,
            "account_name": "Owner",
            "account_avatar": "https://avatar",
            "published_at": int(workflow.published_at.timestamp()),
            "created_at": int(workflow.created_at.timestamp()),
            "updated_at": int(workflow.updated_at.timestamp()),
            "is_forked": True,
        }

    def test_get_public_workflow_detail_should_default_fork_flag_when_account_absent(self):
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
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
            updated_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
        session = _QueueSession(
            [
                _Query(one_or_none_result=workflow),
                _Query(one_or_none_result=None),
            ]
        )
        service = _build_service(session=session)

        detail = service.get_public_workflow_detail(workflow.id, None)

        assert detail["account_name"] == "Unknown"
        assert detail["is_forked"] is False
        assert detail["tags"] == [AppCategory.GENERAL.value]

    def test_get_public_workflow_detail_should_raise_when_not_found(self):
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=None)]))
        with pytest.raises(NotFoundException):
            service.get_public_workflow_detail(uuid4(), None)

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
