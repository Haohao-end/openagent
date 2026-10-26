from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from internal.entity.app_category_entity import AppCategory
from internal.entity.app_entity import AppStatus
from internal.exception import FailException, ForbiddenException, NotFoundException, ValidateErrorException
from internal.service.public_app_service import PublicAppService


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
    def __init__(
        self,
        *,
        one_or_none_result=None,
        all_result=None,
        scalar_result=None,
        count_result=0,
    ):
        self._one_or_none_result = one_or_none_result
        self._all_result = all_result if all_result is not None else []
        self._scalar_result = scalar_result
        self._count_result = count_result
        self.c = SimpleNamespace(app_id="app_id")
        self.filter_args = ()
        self.order_by_args = ()

    def filter(self, *args, **_kwargs):
        self.filter_args = args
        return self

    def join(self, *_args, **_kwargs):
        return self

    def outerjoin(self, *_args, **_kwargs):
        return self

    def order_by(self, *args, **_kwargs):
        self.order_by_args = args
        return self

    def options(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def group_by(self, *_args, **_kwargs):
        return self

    def subquery(self):
        return self

    def one_or_none(self):
        return self._one_or_none_result

    def first(self):
        return self._one_or_none_result

    def all(self):
        return self._all_result

    def scalar(self):
        return self._scalar_result

    def count(self):
        return self._count_result


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


class _FakeApp:
    class _Col:
        def __eq__(self, _other):
            return self

        def contains(self, *_args, **_kwargs):
            return self

        def in_(self, *_args, **_kwargs):
            return self

        def isnot(self, *_args, **_kwargs):
            return self

    id = _Col()
    is_public = _Col()
    status = _Col()
    account_id = _Col()
    original_app_id = _Col()
    tags = _Col()

    def __init__(self, **kwargs):
        self.id = kwargs.pop("id", None)
        self.__dict__.update(kwargs)


class _FakeAppConfigVersion:
    def __init__(self, **kwargs):
        self.id = kwargs.pop("id", None)
        self.__dict__.update(kwargs)


def _build_service(
    *,
    session=None,
    builtin_provider_manager=None,
    language_model_service=None,
    public_agent_registry_service=None,
):
    session = session or _QueueSession()
    return PublicAppService(
        db=_DB(session),
        builtin_provider_manager=builtin_provider_manager or SimpleNamespace(get_provider=lambda _provider_id: None),
        language_model_service=language_model_service,
        public_agent_registry_service=public_agent_registry_service,
    )


class TestPublicAppService:
    def test_share_app_to_square_should_validate_exists_owner_status_and_accept_tags(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        app_id = uuid4()
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=None)]))
        with pytest.raises(NotFoundException):
            service.share_app_to_square(app_id, AppCategory.GENERAL.value, account)

        foreign_app = SimpleNamespace(id=app_id, account_id=uuid4(), status=AppStatus.PUBLISHED.value)
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=foreign_app)]))
        with pytest.raises(ForbiddenException):
            service.share_app_to_square(app_id, AppCategory.GENERAL.value, account)

        draft_app = SimpleNamespace(id=app_id, account_id=account.id, status=AppStatus.DRAFT.value)
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=draft_app)]))
        with pytest.raises(ValidateErrorException):
            service.share_app_to_square(app_id, AppCategory.GENERAL.value, account)

        published_app = SimpleNamespace(
            id=app_id,
            account_id=account.id,
            status=AppStatus.PUBLISHED.value,
            is_public=False,
            tags=[],
            published_at=None,
        )
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=published_app)]))
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: target.__dict__.update(kwargs) or target,
        )

        shared = service.share_app_to_square(app_id, AppCategory.GENERAL.value, account)

        assert shared.tags == [AppCategory.GENERAL.value]
        assert shared.is_public is True
        assert shared.published_at is not None

    def test_share_app_to_square_should_fallback_to_other_when_tags_missing(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        app_id = uuid4()
        published_app = SimpleNamespace(
            id=app_id,
            account_id=account.id,
            status=AppStatus.PUBLISHED.value,
            is_public=False,
            tags=[],
            name="1231231123",
            description="",
            published_at=None,
        )
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=published_app)]))
        monkeypatch.setattr(
            "internal.service.public_app_service.TagAssignmentService.match_tags_by_keywords",
            lambda *_args, **_kwargs: [],
        )
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: target.__dict__.update(kwargs) or target,
        )

        shared = service.share_app_to_square(app_id, "", account)

        assert shared.tags == ["other"]
        assert shared.is_public is True
        assert shared.published_at is not None

    def test_share_and_unshare_app_should_update_public_fields(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(id=uuid4(), account_id=account.id, status=AppStatus.PUBLISHED.value)
        queued_app_ids = []
        service = _build_service(
            session=_QueueSession([
                _Query(one_or_none_result=app),
                _Query(one_or_none_result=app),
            ]),
            public_agent_registry_service=SimpleNamespace(),
        )
        monkeypatch.setattr(
            "internal.service.public_app_service.sync_public_app_registry",
            SimpleNamespace(delay=lambda app_id: queued_app_ids.append(app_id)),
        )
        updates = []

        def _update(target, **kwargs):
            updates.append((target, kwargs))
            for key, value in kwargs.items():
                setattr(target, key, value)
            return target

        monkeypatch.setattr(service, "update", _update)

        shared = service.share_app_to_square(app.id, AppCategory.GENERAL.value, account)
        unshared = service.unshare_app_from_square(app.id, account)

        assert shared is app
        assert unshared is app
        assert updates[0][1]["is_public"] is True
        assert updates[0][1]["tags"] == [AppCategory.GENERAL.value]
        assert updates[0][1]["published_at"] is not None
        assert updates[1][1] == {"is_public": False, "published_at": None}
        assert queued_app_ids == [str(app.id), str(app.id)]

    def test_unshare_app_from_square_should_validate_exists_and_owner(self):
        account = SimpleNamespace(id=uuid4())
        app_id = uuid4()
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=None)]))
        with pytest.raises(NotFoundException):
            service.unshare_app_from_square(app_id, account)

        foreign_app = SimpleNamespace(id=app_id, account_id=uuid4(), status=AppStatus.PUBLISHED.value)
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=foreign_app)]))
        with pytest.raises(ForbiddenException):
            service.unshare_app_from_square(app_id, account)

    def test_get_public_apps_with_page_should_return_basic_fields_and_fork_status(self, monkeypatch, _asia_shanghai_timezone):
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            name="用户应用",
            icon="https://user/icon.png",
            description="user app",
            tags=["coding"],
            published_at=datetime(2026, 1, 1),
            created_at=datetime(2025, 12, 31),
        )
        creator = SimpleNamespace(name="Alice", avatar="https://creator/icon.png")
        session = _QueueSession([_Query(), _Query(all_result=[(app.id,)])])
        service = _build_service(session=session)
        captured = {}

        class _Paginator:
            def __init__(self, db, req):
                self.db = db
                self.req = req
                self.total_record = 1
                self.total_page = 1
                self.total = 1

            def paginate(self, query):
                captured["query"] = query
                return [(app, creator.name, creator.avatar)]

        monkeypatch.setattr("internal.service.public_app_service.Paginator", _Paginator)
        apps, paginator = service.get_public_apps_with_page(
            _req(tags="coding", current_page=1, page_size=20),
            account,
        )

        assert len(apps) == 1
        assert apps[0] == {
            "id": str(app.id),
            "name": "用户应用",
            "icon": "https://user/icon.png",
            "description": "user app",
            "tags": ["coding"],
            "creator_name": "Alice",
            "creator_avatar": "https://creator/icon.png",
            "published_at": int(datetime(2026, 1, 1, tzinfo=UTC).timestamp()),
            "created_at": int(datetime(2025, 12, 31, tzinfo=UTC).timestamp()),
            "is_forked": True,
        }
        assert paginator.total_record == 1
        assert paginator.total_page == 1
        assert paginator.total == 1
        assert len(captured["query"].filter_args) == 3
        assert "tags" in str(captured["query"].filter_args[2])

    def test_get_public_apps_with_page_should_filter_by_requested_tags(self, monkeypatch):
        app_1 = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            name="编程助手",
            icon="https://user/icon.png",
            description="coding helper",
            tags=["coding"],
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            created_at=datetime(2025, 12, 31, tzinfo=UTC),
        )
        app_2 = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            name="翻译专家",
            icon="https://user/icon-2.png",
            description="translate helper",
            tags=["translation"],
            published_at=datetime(2026, 1, 2, tzinfo=UTC),
            created_at=datetime(2025, 12, 30, tzinfo=UTC),
        )
        session = _QueueSession([_Query()])
        service = _build_service(session=session)
        captured = {}

        class _Paginator:
            def __init__(self, db, req):
                self.total_record = 1
                self.total_page = 1

            def paginate(self, query):
                captured["query"] = query
                return [(app_1, "Bob", "")]

        monkeypatch.setattr("internal.service.public_app_service.Paginator", _Paginator)
        apps, _paginator = service.get_public_apps_with_page(
            _req(tags="coding", current_page=1, page_size=20),
            None,
        )

        assert [item["id"] for item in apps] == [str(app_1.id)]
        assert apps[0]["creator_name"] == "Bob"
        assert apps[0]["is_forked"] is False
        assert len(captured["query"].filter_args) == 3
        assert "tags" in str(captured["query"].filter_args[2])

    def test_fork_public_app_should_support_public_path(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        app_config = SimpleNamespace(
            model_config={"provider": "openai"},
            dialog_round=3,
            preset_prompt="prompt",
            tools=[],
            mcp_bindings=[
                {
                    "name": "Weather MCP",
                    "description": "weather",
                    "transport": "streamable_http",
                    "url": "https://mcp.example.com",
                    "enabled": True,
                    "headers": [],
                    "tool_names": [],
                    "timeout_seconds": 30,
                    "args": [],
                    "env": {},
                }
            ],
            workflows=[],
            retrieval_config={},
            long_term_memory={"enable": True},
            opening_statement="hello",
            opening_questions=["q1"],
            speech_to_text={"enable": False},
            text_to_speech={"enable": False},
            suggested_after_answer={"enable": True},
            review_config={"enable": False},
            app_dataset_joins=[],
        )
        public_app = SimpleNamespace(
            id=uuid4(),
            is_public=True,
            status=AppStatus.PUBLISHED.value,
            view_count=1,
            fork_count=2,
            name="公共应用",
            icon="https://x",
            description="desc",
            category=AppCategory.GENERAL.value,
            tags=[AppCategory.GENERAL.value],
            app_config=app_config,
        )
        session = _QueueSession([_Query(one_or_none_result=public_app)])
        service = _build_service(session=session)
        monkeypatch.setattr("internal.service.public_app_service.App", _FakeApp)
        monkeypatch.setattr("internal.service.public_app_service.AppConfigVersion", _FakeAppConfigVersion)
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: target.__dict__.update(kwargs) or target,
        )

        copied = service.fork_public_app(str(public_app.id), account)

        assert copied.name.endswith("(副本)")
        assert copied.original_app_id == public_app.id
        assert copied.tags == public_app.tags
        assert session.added[1].mcp_bindings == public_app.app_config.mcp_bindings
        assert len(session.added) == 2

    def test_fork_public_app_should_cover_dataset_join_iteration_branch(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        app_config = SimpleNamespace(
            model_config={"provider": "openai"},
            dialog_round=3,
            preset_prompt="prompt",
            tools=[],
            workflows=[],
            retrieval_config={},
            long_term_memory={"enable": True},
            opening_statement="hello",
            opening_questions=["q1"],
            speech_to_text={"enable": False},
            text_to_speech={"enable": False},
            suggested_after_answer={"enable": True},
            review_config={"enable": False},
            app_dataset_joins=[SimpleNamespace(dataset_id=uuid4())],
        )
        public_app = SimpleNamespace(
            id=uuid4(),
            is_public=True,
            status=AppStatus.PUBLISHED.value,
            view_count=1,
            fork_count=2,
            name="公共应用",
            icon="https://x",
            description="desc",
            category=AppCategory.GENERAL.value,
            tags=[AppCategory.GENERAL.value],
            app_config=app_config,
        )
        session = _QueueSession([_Query(one_or_none_result=public_app)])
        service = _build_service(session=session)
        monkeypatch.setattr("internal.service.public_app_service.App", _FakeApp)
        monkeypatch.setattr("internal.service.public_app_service.AppConfigVersion", _FakeAppConfigVersion)
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: target.__dict__.update(kwargs) or target,
        )

        copied = service.fork_public_app(str(public_app.id), account)

        assert copied.name.endswith("(副本)")

    def test_fork_public_app_should_raise_for_invalid_or_unavailable_source(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        service = _build_service(session=_QueueSession())
        with pytest.raises(NotFoundException):
            service.fork_public_app("not-a-uuid", account)

        service = _build_service(
            session=_QueueSession([_Query(one_or_none_result=None)]),
        )
        with pytest.raises(NotFoundException):
            service.fork_public_app(str(uuid4()), account)

        public_app = SimpleNamespace(
            id=uuid4(),
            is_public=True,
            status=AppStatus.PUBLISHED.value,
            view_count=0,
            fork_count=0,
            name="p",
            icon="i",
            description="d",
            category=AppCategory.GENERAL.value,
            tags=[AppCategory.GENERAL.value],
            app_config=None,
        )
        service = _build_service(
            session=_QueueSession([_Query(one_or_none_result=public_app)]),
        )
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: target.__dict__.update(kwargs) or target,
        )
        with pytest.raises(FailException):
            service.fork_public_app(str(public_app.id), account)

    def test_fork_public_app_should_copy_dataset_joins(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        app_config = SimpleNamespace(
            model_config={"provider": "openai"},
            dialog_round=3,
            preset_prompt="prompt",
            tools=[],
            workflows=[],
            retrieval_config={},
            long_term_memory={"enable": False},
            opening_statement="hello",
            opening_questions=["q1"],
            speech_to_text={"enable": False},
            text_to_speech={"enable": False},
            suggested_after_answer={"enable": True},
            review_config={"enable": False},
            app_dataset_joins=[SimpleNamespace(dataset_id=uuid4())],
        )
        public_app = SimpleNamespace(
            id=uuid4(),
            is_public=True,
            status=AppStatus.PUBLISHED.value,
            view_count=0,
            fork_count=0,
            name="公共应用",
            icon="https://x",
            description="desc",
            category=AppCategory.GENERAL.value,
            tags=[AppCategory.GENERAL.value],
            app_config=app_config,
        )
        session = _QueueSession([_Query(one_or_none_result=public_app)])
        service = _build_service(session=session)
        monkeypatch.setattr("internal.service.public_app_service.App", _FakeApp)
        monkeypatch.setattr("internal.service.public_app_service.AppConfigVersion", _FakeAppConfigVersion)
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: target.__dict__.update(kwargs) or target,
        )

        copied = service.fork_public_app(str(public_app.id), account)

        assert copied.name.endswith("(副本)")
        assert len(session.added) == 3
        assert getattr(session.added[2], "dataset_id", None) == app_config.app_dataset_joins[0].dataset_id

    def test_fork_public_app_should_skip_duplicate_dataset_joins(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id_1 = uuid4()
        dataset_id_2 = uuid4()
        app_config = SimpleNamespace(
            model_config={"provider": "openai"},
            dialog_round=3,
            preset_prompt="prompt",
            tools=[],
            agent_bindings=[
                {"app_id": str(uuid4()), "invoke_mode": "a2a"},
                {"app_id": str(uuid4()), "invoke_mode": "tool"},
            ],
            mcp_bindings=[],
            workflows=[],
            retrieval_config={},
            long_term_memory={"enable": True},
            opening_statement="hello",
            opening_questions=["q1"],
            speech_to_text={"enable": False},
            text_to_speech={"enable": False},
            suggested_after_answer={"enable": True},
            review_config={"enable": False},
            app_dataset_joins=[
                SimpleNamespace(dataset_id=dataset_id_1),
                SimpleNamespace(dataset_id=dataset_id_1),
                SimpleNamespace(dataset_id=dataset_id_2),
            ],
        )
        public_app = SimpleNamespace(
            id=uuid4(),
            is_public=True,
            status=AppStatus.PUBLISHED.value,
            name="公共应用",
            icon="https://x",
            description="desc",
            tags=[AppCategory.GENERAL.value],
            app_config=app_config,
        )
        session = _QueueSession([_Query(one_or_none_result=public_app)])
        service = _build_service(session=session)
        monkeypatch.setattr("internal.service.public_app_service.App", _FakeApp)
        monkeypatch.setattr("internal.service.public_app_service.AppConfigVersion", _FakeAppConfigVersion)

        copied = service.fork_public_app(str(public_app.id), account)

        dataset_joins = [obj for obj in session.added if hasattr(obj, "dataset_id")]
        assert copied.name.endswith("(副本)")
        assert copied.original_app_id == public_app.id
        assert copied.status == AppStatus.DRAFT.value
        assert copied.tags == [AppCategory.GENERAL.value]
        assert len(session.added) == 4
        assert len(dataset_joins) == 2
        assert {join.dataset_id for join in dataset_joins} == {dataset_id_1, dataset_id_2}
        assert session.added[1].app_id == copied.id
        assert session.added[1].version == 0

    def test_fork_public_app_should_raise_for_invalid_or_unavailable_source(self):
        account = SimpleNamespace(id=uuid4())
        service = _build_service(session=_QueueSession())

        with pytest.raises(NotFoundException):
            service.fork_public_app("not-a-uuid", account)

        service = _build_service(session=_QueueSession([_Query(one_or_none_result=None)]))
        with pytest.raises(NotFoundException):
            service.fork_public_app(str(uuid4()), account)

        public_app = SimpleNamespace(
            id=uuid4(),
            is_public=True,
            status=AppStatus.PUBLISHED.value,
            name="p",
            icon="i",
            description="d",
            tags=[AppCategory.GENERAL.value],
            app_config=None,
        )
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=public_app)]))
        with pytest.raises(FailException):
            service.fork_public_app(str(public_app.id), account)

    def test_get_public_app_detail_should_return_detail_and_fork_status(self):
        account = SimpleNamespace(id=uuid4())
        app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            is_public=True,
            status=AppStatus.PUBLISHED.value,
            name="app",
            icon="https://icon",
            description="desc",
            tags=[AppCategory.GENERAL.value],
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            created_at=datetime(2025, 12, 31, tzinfo=UTC),
            app_config=SimpleNamespace(
                model_config={"provider": "openai"},
                dialog_round=4,
                preset_prompt="prompt",
                tools=[{"type": "builtin_tool"}],
                mcp_bindings=[
                    {
                        "name": "Weather MCP",
                        "description": "weather",
                        "transport": "streamable_http",
                        "url": "https://mcp.example.com",
                        "enabled": True,
                        "headers": [],
                        "tool_names": [],
                        "timeout_seconds": 30,
                        "args": [],
                        "env": {},
                    }
                ],
                workflows=[{"id": "wf"}],
                retrieval_config={},
                long_term_memory={"enable": False},
                opening_statement="hello",
                opening_questions=["q1"],
                speech_to_text={"enable": False},
                text_to_speech={"enable": False},
                suggested_after_answer={"enable": True},
                review_config={"enable": False},
            ),
        )
        creator = SimpleNamespace(id=app.account_id, name="Owner", avatar="https://avatar")
        session = _QueueSession(
            [
                _Query(one_or_none_result=app),
                _Query(one_or_none_result=creator),
                _Query(one_or_none_result=SimpleNamespace(id=uuid4())),
            ]
        )
        service = _build_service(session=session)

        detail = service.get_public_app_detail(str(app.id), account)

        assert detail["creator_name"] == "Owner"
        assert detail["tags"] == [AppCategory.GENERAL.value]
        assert detail["is_forked"] is True
        assert detail["draft_app_config"]["tools"] == []
        assert detail["draft_app_config"]["mcp_bindings"] == [
            {
                "name": "Weather MCP",
                "description": "weather",
                "transport": "streamable_http",
                "url": "https://mcp.example.com",
                "enabled": True,
                "headers": [],
                "tool_names": [],
                "timeout_seconds": 30,
                "args": [],
                "env": {},
            }
        ]
        assert detail["draft_app_config"]["capabilities"] == {}

    def test_get_public_app_detail_should_include_runtime_capabilities_when_service_available(
        self, monkeypatch
    ):
        app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            is_public=True,
            status=AppStatus.PUBLISHED.value,
            name="PublicApp",
            icon="https://icon",
            description="desc",
            category=AppCategory.GENERAL.value,
            tags=[AppCategory.GENERAL.value],
            view_count=1,
            like_count=0,
            fork_count=0,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            created_at=datetime(2025, 12, 31, tzinfo=UTC),
            app_config=SimpleNamespace(
                model_config={"provider": "openai", "model": "gpt-4o-mini"},
                dialog_round=4,
                preset_prompt="prompt",
                tools=[],
                workflows=[],
                retrieval_config={},
                long_term_memory={"enable": False},
                opening_statement="hello",
                opening_questions=["q1"],
                speech_to_text={"enable": False},
                text_to_speech={"enable": False},
                suggested_after_answer={"enable": True},
                review_config={"enable": False},
            ),
        )
        session = _QueueSession(
            [
                _Query(one_or_none_result=app),
                _Query(one_or_none_result=None),
                _Query(scalar_result=0),
            ]
        )
        capture = {}
        capabilities = {"image_input": {"enabled": False, "reason_code": "PUBLIC_A2A_ONLY_TEXT"}}
        service = _build_service(
            session=session,
            language_model_service=SimpleNamespace(
                describe_runtime_capabilities=lambda model_config, entrypoint, allow_image_input: capture.update(
                    {
                        "model_config": model_config,
                        "entrypoint": entrypoint,
                        "allow_image_input": allow_image_input,
                    }
                )
                or capabilities
            ),
        )
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: target.__dict__.update(kwargs) or target,
        )

        detail = service.get_public_app_detail(str(app.id), None)

        assert detail["draft_app_config"]["capabilities"] == capabilities
        assert capture == {
            "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
            "entrypoint": "public_a2a",
            "allow_image_input": False,
        }

    def test_get_public_app_detail_should_raise_when_id_invalid_or_not_public(self):
        service = _build_service(session=_QueueSession())
        with pytest.raises(NotFoundException):
            service.get_public_app_detail("bad-id")

        service = _build_service(
            session=_QueueSession([_Query(one_or_none_result=None)]),
        )
        with pytest.raises(NotFoundException):
            service.get_public_app_detail(str(uuid4()))

    def test_get_public_app_detail_should_keep_default_flags_when_account_absent_and_skip_missing_config(self, monkeypatch):
        app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            is_public=True,
            status=AppStatus.PUBLISHED.value,
            name="app",
            icon="https://icon",
            description="desc",
            tags=[AppCategory.GENERAL.value],
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
            app_config=None,
        )
        session = _QueueSession(
            [
                _Query(one_or_none_result=app),
                _Query(one_or_none_result=None),
            ]
        )
        service = _build_service(session=session)

        detail = service.get_public_app_detail(str(app.id), None)

        assert detail["is_forked"] is False
        assert detail["creator_name"] == "未知用户"
        assert detail["tags"] == [AppCategory.GENERAL.value]

    def test_get_public_app_detail_should_fallback_to_other_without_model_call(self, monkeypatch):
        app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            is_public=True,
            status=AppStatus.PUBLISHED.value,
            name="1231231123",
            icon="https://icon",
            description="",
            tags=[],
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
            app_config=None,
        )
        session = _QueueSession(
            [
                _Query(one_or_none_result=app),
                _Query(one_or_none_result=None),
            ]
        )
        service = _build_service(session=session)

        monkeypatch.setattr(
            "internal.service.public_app_service.TagAssignmentService.match_tags_by_keywords",
            lambda *_args, **_kwargs: [],
        )
        monkeypatch.setattr(
            "internal.service.public_app_service.TagAssignmentService.assign_tags_by_deepseek",
            lambda *_args, **_kwargs: pytest.fail("public app detail should not call DeepSeek"),
        )

        detail = service.get_public_app_detail(str(app.id), None)

        assert detail["tags"] == ["other"]

    def test_get_public_app_detail_should_raise_when_not_found(self):
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=None)]))
        with pytest.raises(NotFoundException):
            service.get_public_app_detail(str(uuid4()), None)
