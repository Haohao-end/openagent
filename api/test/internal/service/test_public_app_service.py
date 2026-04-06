from contextlib import contextmanager
from datetime import UTC, datetime
import random
from types import SimpleNamespace
from uuid import uuid4
import sys

import pytest

from internal.entity.app_category_entity import AppCategory
from internal.entity.app_entity import AppStatus
from internal.exception import FailException, ForbiddenException, NotFoundException, ValidateErrorException
from internal.service.public_app_service import PublicAppService


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
        self.c = SimpleNamespace(app_id="app_id", favorite_count="favorite_count")
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

    id = _Col()
    is_public = _Col()
    status = _Col()

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
    public_agent_registry_service=None,
):
    session = session or _QueueSession()
    return PublicAppService(
        db=_DB(session),
        builtin_provider_manager=builtin_provider_manager or SimpleNamespace(get_provider=lambda _provider_id: None),
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

    def test_get_public_apps_with_page_should_merge_sort_paginate_and_attach_user_status(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        user_app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            name="用户应用",
            icon="https://user/icon.png",
            description="user app",
            category=AppCategory.GENERAL.value,
            tags=[AppCategory.GENERAL.value],
            view_count=12,
            like_count=7,
            fork_count=3,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            created_at=datetime(2025, 12, 31, tzinfo=UTC),
        )
        creator = SimpleNamespace(id=user_app.account_id, name="Alice", avatar="https://creator/icon.png")
        session = _QueueSession(
            [
                _Query(),  # favorite_count_subquery
                _Query(all_result=[(user_app, creator.name, creator.avatar, 5)], count_result=1),
                _Query(all_result=[(user_app.id,)]),
                _Query(all_result=[]),
                _Query(all_result=[(user_app.id,)]),
            ]
        )
        service = _build_service(session=session)

        class _Paginator:
            def __init__(self, db, req):
                self.db = db
                self.req = req
                self.total = 0

        monkeypatch.setattr("internal.service.public_app_service.Paginator", _Paginator)
        apps, paginator = service.get_public_apps_with_page(
            _req(sort_by="popular", current_page=1, page_size=1),
            account,
        )

        assert isinstance(paginator, _Paginator)
        assert paginator.total == 1
        assert len(apps) == 1
        assert apps[0]["id"] == str(user_app.id)
        assert apps[0]["creator_name"] == "Alice"
        assert apps[0]["creator_avatar"] == creator.avatar
        assert apps[0]["favorite_count"] == 5
        assert apps[0]["is_liked"] is True
        assert apps[0]["is_favorited"] is False
        assert apps[0]["is_forked"] is True
        assert apps[0]["tags"] == [AppCategory.GENERAL.value]

    def test_get_public_apps_with_page_should_keep_default_like_flags_when_account_absent(self, monkeypatch):
        user_app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            name="用户应用",
            icon="https://user/icon.png",
            description="user app",
            category=AppCategory.GENERAL.value,
            tags=[AppCategory.GENERAL.value],
            view_count=12,
            like_count=7,
            fork_count=3,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            created_at=datetime(2025, 12, 31, tzinfo=UTC),
        )
        creator = SimpleNamespace(id=user_app.account_id, name="Alice")
        session = _QueueSession(
            [
                _Query(),
                _Query(all_result=[(user_app, creator.name, "", 3)], count_result=1),
            ]
        )
        service = _build_service(session=session)

        class _Paginator:
            def __init__(self, db, req):
                self.total = 0

        monkeypatch.setattr("internal.service.public_app_service.Paginator", _Paginator)
        apps, _paginator = service.get_public_apps_with_page(
            _req(sort_by="latest", current_page=1, page_size=20),
            None,
        )

        assert len(apps) == 1
        assert apps[0]["is_liked"] is False
        assert apps[0]["is_favorited"] is False

    def test_get_public_apps_with_page_should_update_total_record_and_total_page_without_total_attr(self, monkeypatch):
        user_app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            name="用户应用",
            icon="https://user/icon.png",
            description="user app",
            category=AppCategory.GENERAL.value,
            tags=[AppCategory.GENERAL.value],
            view_count=1,
            like_count=1,
            fork_count=1,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            created_at=datetime(2025, 12, 31, tzinfo=UTC),
        )
        creator = SimpleNamespace(id=user_app.account_id, name="Alice")
        session = _QueueSession(
            [
                _Query(),
                _Query(all_result=[(user_app, creator.name, "", 0)], count_result=1),
            ]
        )
        service = _build_service(session=session)

        class _Paginator:
            def __init__(self, db, req):
                self.total_record = 0
                self.total_page = -1

        monkeypatch.setattr("internal.service.public_app_service.Paginator", _Paginator)
        apps, paginator = service.get_public_apps_with_page(
            _req(sort_by="latest", current_page=1, page_size=2),
            None,
        )

        assert len(apps) == 1
        assert paginator.total_record == 1
        assert paginator.total_page == 1

    def test_get_public_apps_with_page_should_keep_user_app_for_anonymous_with_search(self, monkeypatch):
        user_app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            name="翻译专家",
            icon="https://user/icon.png",
            description="translate helper",
            category=AppCategory.GENERAL.value,
            tags=["translation"],
            view_count=3,
            like_count=2,
            fork_count=1,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            created_at=datetime(2025, 12, 31, tzinfo=UTC),
        )
        session = _QueueSession(
            [
                _Query(),
                _Query(all_result=[(user_app, None, None, 0)], count_result=1),
            ]
        )
        service = _build_service(session=session)

        class _Paginator:
            def __init__(self, db, req):
                self.total = 0

        monkeypatch.setattr("internal.service.public_app_service.Paginator", _Paginator)
        apps, paginator = service.get_public_apps_with_page(
            _req(search_word="translate"),
            None,
        )

        assert paginator.total == 1
        assert len(apps) == 1
        assert apps[0]["id"] == str(user_app.id)
        assert apps[0]["is_liked"] is False
        assert apps[0]["is_favorited"] is False

    def test_get_public_apps_with_page_should_filter_by_tags(self, monkeypatch):
        """测试按标签筛选应用"""
        user_app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            name="编程助手",
            icon="https://user/icon.png",
            description="coding helper",
            category=AppCategory.PROGRAMMING.value,
            tags=["coding"],
            view_count=5,
            like_count=3,
            fork_count=2,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            created_at=datetime(2025, 12, 31, tzinfo=UTC),
        )
        creator = SimpleNamespace(id=user_app.account_id, name="Bob")
        session = _QueueSession(
            [
                _Query(),  # favorite_count_subquery
                _Query(all_result=[(user_app, creator.name, "", 2)], count_result=1),
            ]
        )
        service = _build_service(session=session)

        class _Paginator:
            def __init__(self, db, req):
                self.total = 0

        monkeypatch.setattr("internal.service.public_app_service.Paginator", _Paginator)
        apps, paginator = service.get_public_apps_with_page(
            _req(tags="coding", sort_by="latest"),
            None,
        )

        assert paginator.total == 1
        assert len(apps) == 1
        assert apps[0]["id"] == str(user_app.id)
        assert apps[0]["tags"] == ["coding"]

    def test_fork_public_app_should_support_public_path(self, monkeypatch):
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
        assert public_app.view_count == 2
        assert public_app.fork_count == 3
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
        assert public_app.fork_count == 3

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
            workflows=[],
            retrieval_config={},
            long_term_memory={"enable": False},
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

        dataset_joins = [obj for obj in session.added if hasattr(obj, "dataset_id")]
        assert copied.name.endswith("(副本)")
        assert len(dataset_joins) == 2
        assert {join.dataset_id for join in dataset_joins} == {dataset_id_1, dataset_id_2}

    @pytest.mark.parametrize(
        "existing_like,expected_liked,expected_count",
        [
            (SimpleNamespace(id=uuid4()), False, 2),
            (None, True, 4),
        ],
    )
    def test_like_app_should_toggle(self, monkeypatch, existing_like, expected_liked, expected_count):
        app = SimpleNamespace(id=uuid4(), is_public=True, like_count=3)
        session = _QueueSession(
            [
                _Query(one_or_none_result=app),
                _Query(one_or_none_result=existing_like),
            ]
        )
        service = _build_service(session=session)
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: target.__dict__.update(kwargs) or target,
        )

        result = service.like_app(app.id, SimpleNamespace(id=uuid4()))

        assert result == {"is_liked": expected_liked, "like_count": expected_count}
        assert app.like_count == expected_count
        assert session.commit_calls == 1

    def test_like_app_should_raise_when_target_not_public(self):
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=None)]))

        with pytest.raises(NotFoundException):
            service.like_app(uuid4(), SimpleNamespace(id=uuid4()))

    def test_like_app_should_raise_when_app_not_public_or_not_found(self):
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=None)]))

        with pytest.raises(NotFoundException):
            service.like_app(uuid4(), SimpleNamespace(id=uuid4()))

    @pytest.mark.parametrize(
        "existing_favorite,expected",
        [
            (SimpleNamespace(id=uuid4()), {"is_favorited": False}),
            (None, {"is_favorited": True}),
        ],
    )
    def test_favorite_app_should_toggle(self, existing_favorite, expected):
        app = SimpleNamespace(id=uuid4(), is_public=True)
        session = _QueueSession(
            [
                _Query(one_or_none_result=app),
                _Query(one_or_none_result=existing_favorite),
            ]
        )
        service = _build_service(session=session)

        result = service.favorite_app(app.id, SimpleNamespace(id=uuid4()))

        assert result == expected
        assert session.commit_calls == 1

    def test_favorite_app_should_raise_when_target_not_public(self):
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=None)]))

        with pytest.raises(NotFoundException):
            service.favorite_app(uuid4(), SimpleNamespace(id=uuid4()))

    def test_favorite_app_should_raise_when_app_not_public_or_not_found(self):
        service = _build_service(session=_QueueSession([_Query(one_or_none_result=None)]))

        with pytest.raises(NotFoundException):
            service.favorite_app(uuid4(), SimpleNamespace(id=uuid4()))

    def test_get_my_favorites_should_return_serialized_public_apps(self):
        account = SimpleNamespace(id=uuid4())
        favorite_1 = SimpleNamespace(app_id=uuid4(), created_at=datetime(2026, 1, 2, tzinfo=UTC))
        favorite_2 = SimpleNamespace(app_id=uuid4(), created_at=datetime(2026, 1, 1, tzinfo=UTC))
        app_1 = SimpleNamespace(
            id=favorite_1.app_id,
            name="收藏应用一",
            icon="https://a.com/1.png",
            description="desc 1",
            tags=["assistant"],
            view_count=3,
            like_count=5,
            fork_count=2,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            created_at=datetime(2025, 12, 1, tzinfo=UTC),
        )
        app_2 = SimpleNamespace(
            id=favorite_2.app_id,
            name="收藏应用二",
            icon="https://a.com/2.png",
            description="desc 2",
            tags=["workflow"],
            view_count=4,
            like_count=6,
            fork_count=3,
            published_at=datetime(2026, 1, 2, tzinfo=UTC),
            created_at=datetime(2025, 12, 2, tzinfo=UTC),
        )
        session = _QueueSession(
            [
                _Query(all_result=[favorite_1, favorite_2]),
                _Query(),  # favorite_count_subquery
                _Query(all_result=[(app_1, "Alice", "https://avatar/1.png", 7), (app_2, "Bob", "", 8)]),
                _Query(all_result=[]),  # liked ids
                _Query(all_result=[(favorite_1.app_id,), (favorite_2.app_id,)]),  # favorited ids
                _Query(all_result=[(favorite_1.app_id,)]),  # forked ids
            ]
        )
        service = _build_service(session=session)

        apps = service.get_my_favorites(account)

        assert [app["id"] for app in apps] == [str(favorite_1.app_id), str(favorite_2.app_id)]
        assert apps[0]["creator_name"] == "Alice"
        assert apps[0]["is_favorited"] is True
        assert apps[0]["is_forked"] is True
        assert apps[1]["creator_name"] == "Bob"
        assert apps[1]["favorite_count"] == 8

    def test_get_my_likes_should_return_serialized_public_apps(self):
        account = SimpleNamespace(id=uuid4())
        like_1 = SimpleNamespace(app_id=uuid4(), created_at=datetime(2026, 1, 2, tzinfo=UTC))
        like_2 = SimpleNamespace(app_id=uuid4(), created_at=datetime(2026, 1, 1, tzinfo=UTC))
        app_1 = SimpleNamespace(
            id=like_1.app_id,
            name="点赞应用一",
            icon="https://a.com/1.png",
            description="desc 1",
            tags=["assistant"],
            view_count=8,
            like_count=11,
            fork_count=4,
            published_at=datetime(2026, 1, 3, tzinfo=UTC),
            created_at=datetime(2025, 12, 3, tzinfo=UTC),
        )
        app_2 = SimpleNamespace(
            id=like_2.app_id,
            name="点赞应用二",
            icon="https://a.com/2.png",
            description="desc 2",
            tags=["workflow"],
            view_count=6,
            like_count=9,
            fork_count=2,
            published_at=datetime(2026, 1, 4, tzinfo=UTC),
            created_at=datetime(2025, 12, 4, tzinfo=UTC),
        )
        session = _QueueSession(
            [
                _Query(all_result=[like_1, like_2]),
                _Query(),  # favorite_count_subquery
                _Query(all_result=[(app_1, "Alice", "https://avatar/1.png", 3), (app_2, None, "", 4)]),
                _Query(all_result=[(like_1.app_id,), (like_2.app_id,)]),  # liked ids
                _Query(all_result=[(like_2.app_id,)]),  # favorited ids
                _Query(all_result=[]),  # forked ids
            ]
        )
        service = _build_service(session=session)

        apps = service.get_my_likes(account)

        assert [app["id"] for app in apps] == [str(like_1.app_id), str(like_2.app_id)]
        assert apps[0]["is_liked"] is True
        assert apps[0]["is_favorited"] is False
        assert apps[1]["creator_name"] == "未知用户"
        assert apps[1]["is_favorited"] is True

    def test_get_public_app_detail_should_support_public_app(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
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
            view_count=3,
            like_count=2,
            fork_count=1,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            created_at=datetime(2025, 12, 31, tzinfo=UTC),
            app_config=SimpleNamespace(
                model_config={"provider": "openai"},
                dialog_round=4,
                preset_prompt="prompt",
                tools=[{"type": "builtin_tool"}],
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
        creator = SimpleNamespace(id=app.account_id, name="Owner")
        session = _QueueSession(
            [
                _Query(one_or_none_result=app),
                _Query(one_or_none_result=creator),
                _Query(scalar_result=6),
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
        monkeypatch.setattr(service, "_enrich_tools", lambda _tools: [{"type": "enriched"}])

        detail = service.get_public_app_detail(str(app.id), account)

        assert detail["creator_name"] == "Owner"
        assert detail["tags"] == [AppCategory.GENERAL.value]
        assert detail["is_liked"] is True
        assert detail["is_favorited"] is False
        assert detail["draft_app_config"]["tools"] == [{"type": "enriched"}]
        assert app.view_count == 4

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
            name="PublicApp",
            icon="https://icon",
            description="desc",
            category=AppCategory.GENERAL.value,
            tags=[AppCategory.GENERAL.value],
            view_count=3,
            like_count=2,
            fork_count=1,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            created_at=datetime(2025, 12, 31, tzinfo=UTC),
            app_config=None,
        )
        creator = SimpleNamespace(id=app.account_id, name="Owner")
        session = _QueueSession(
            [
                _Query(one_or_none_result=app),
                _Query(one_or_none_result=creator),
                _Query(scalar_result=1),
            ]
        )
        service = _build_service(session=session)
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: target.__dict__.update(kwargs) or target,
        )

        detail = service.get_public_app_detail(str(app.id), None)

        assert detail["tags"] == [AppCategory.GENERAL.value]
        assert detail["is_liked"] is False
        assert detail["is_favorited"] is False
        assert "draft_app_config" not in detail

    def test_get_public_app_detail_should_support_anonymous_user_and_missing_config(self, monkeypatch):
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
            view_count=0,
            like_count=0,
            fork_count=0,
            published_at=None,
            created_at=datetime(2025, 12, 31, tzinfo=UTC),
            app_config=None,
        )
        session = _QueueSession(
            [
                _Query(one_or_none_result=app),
                _Query(one_or_none_result=None),
                _Query(scalar_result=0),
            ]
        )
        service = _build_service(session=session)
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: target.__dict__.update(kwargs) or target,
        )

        detail = service.get_public_app_detail(str(app.id), None)

        assert detail["creator_name"] == "未知用户"
        assert detail["tags"] == [AppCategory.GENERAL.value]
        assert detail["is_liked"] is False
        assert detail["is_favorited"] is False
        assert "draft_app_config" not in detail

    def test_enrich_tools_should_include_builtin_and_api_and_skip_invalid_items(self):
        builtin_provider = SimpleNamespace(
            provider_entity=SimpleNamespace(
                name="search",
                label="Search",
                description="search provider",
            ),
            get_tool_entity=lambda tool_id: (
                SimpleNamespace(name="web_search", label="Web Search", description="desc")
                if tool_id == "web_search"
                else None
            ),
        )
        api_tool = SimpleNamespace(id=uuid4(), name="api_tool", description="api desc")
        api_provider = SimpleNamespace(id=uuid4(), name="api-provider", icon="icon", description="provider desc")
        session = _QueueSession(
            [
                _Query(one_or_none_result=api_tool),
                _Query(one_or_none_result=api_provider),
                _Query(one_or_none_result=None),
                _Query(one_or_none_result=api_tool),
                _Query(one_or_none_result=None),
            ]
        )
        service = _build_service(
            session=session,
            builtin_provider_manager=SimpleNamespace(
                get_provider=lambda provider_id: builtin_provider if provider_id == "search" else None,
            ),
        )

        tools = service._enrich_tools(
            [
                {"type": "unknown_tool", "provider_id": "x", "tool_id": "y", "params": {}},
                {"type": "builtin_tool", "provider_id": "search", "tool_id": "web_search", "params": {"q": "x"}},
                {"type": "builtin_tool", "provider_id": "missing", "tool_id": "web_search", "params": {}},
                {"type": "builtin_tool", "provider_id": "search", "tool_id": "not-found", "params": {}},
                {"type": "api_tool", "provider_id": str(api_provider.id), "tool_id": str(api_tool.id), "params": {"x": 1}},
                {"type": "api_tool", "provider_id": str(api_provider.id), "tool_id": "missing-tool", "params": {}},
                {"type": "api_tool", "provider_id": "missing-provider", "tool_id": str(api_tool.id), "params": {}},
            ]
        )

        assert len(tools) == 2
        assert tools[0]["type"] == "builtin_tool"
        assert tools[0]["provider"]["id"] == "search"
        assert tools[1]["type"] == "api_tool"
        assert tools[1]["provider"]["name"] == "api-provider"

    def test_enrich_tools_should_ignore_unknown_tool_type(self):
        service = _build_service(session=_QueueSession())

        tools = service._enrich_tools(
            [
                {"type": "unknown_tool", "provider_id": "x", "tool_id": "y", "params": {}},
            ]
        )

        assert tools == []

    def test_enrich_workflows_should_fill_workflow_fields_from_database(self):
        workflow_id = uuid4()
        workflow_record = SimpleNamespace(
            id=workflow_id,
            name="工作流A",
            icon="https://workflow/icon.png",
            description="workflow desc",
        )
        service = _build_service(session=_QueueSession([_Query(all_result=[workflow_record])]))

        workflows = service._enrich_workflows([{"id": str(workflow_id), "name": "old-name"}])

        assert workflows == [
            {
                "id": str(workflow_id),
                "name": "工作流A",
                "icon": "https://workflow/icon.png",
                "description": "workflow desc",
            }
        ]

    def test_enrich_workflows_should_keep_original_entries_when_record_missing(self):
        service = _build_service(session=_QueueSession([_Query(all_result=[])]))

        workflows = service._enrich_workflows(
            [
                {"id": "wf-missing", "name": "原始名称", "icon": "icon", "description": "desc"},
                {"id": ""},
                None,
            ]
        )

        assert workflows == [
            {
                "id": "wf-missing",
                "name": "原始名称",
                "icon": "icon",
                "description": "desc",
            }
        ]
        assert service._enrich_workflows(None) == []

    def test_enrich_workflows_should_support_string_workflow_id(self):
        workflow_id = uuid4()
        workflow_record = SimpleNamespace(
            id=workflow_id,
            name="发布工作流",
            icon="https://workflow/icon.png",
            description="workflow desc",
        )
        service = _build_service(session=_QueueSession([_Query(all_result=[workflow_record])]))

        workflows = service._enrich_workflows([str(workflow_id)])

        assert workflows == [
            {
                "id": str(workflow_id),
                "name": "发布工作流",
                "icon": "https://workflow/icon.png",
                "description": "workflow desc",
            }
        ]

    def test_enrich_workflows_should_return_empty_when_all_entries_invalid(self):
        service = _build_service(session=_QueueSession())

        assert service._enrich_workflows([None, {"id": "   "}, "   "]) == []

    @pytest.mark.parametrize("seed", [5, 17, 29])
    def test_enrich_workflows_property_should_preserve_order_and_merge_records(self, seed):
        rng = random.Random(seed)
        workflow_ids = [str(uuid4()) for _ in range(8)]
        db_hit_ids = set(rng.sample(workflow_ids, 4))
        workflow_records = [
            SimpleNamespace(
                id=workflow_id,
                name=f"DB-{index}",
                icon=f"https://db/{index}.png",
                description=f"db-desc-{index}",
            )
            for index, workflow_id in enumerate(db_hit_ids)
        ]
        workflow_record_map = {str(record.id): record for record in workflow_records}
        service = _build_service(session=_QueueSession([_Query(all_result=workflow_records)]))

        input_workflows = []
        expected_workflows = []
        for _ in range(50):
            entry_type = rng.choice(["none", "blank", "string", "dict"])

            if entry_type == "none":
                input_workflows.append(None)
                continue

            if entry_type == "blank":
                input_workflows.append({"id": "   ", "name": "x"})
                continue

            workflow_id = rng.choice(workflow_ids)
            if entry_type == "string":
                input_workflows.append(workflow_id)
                original_entry = {
                    "id": workflow_id,
                    "name": "",
                    "icon": "",
                    "description": "",
                }
            else:
                original_entry = {
                    "id": workflow_id,
                    "name": f"orig-{workflow_id[:4]}",
                    "icon": "orig-icon",
                    "description": "orig-desc",
                }
                input_workflows.append(dict(original_entry))

            workflow_record = workflow_record_map.get(workflow_id)
            if workflow_record:
                expected_workflows.append(
                    {
                        "id": workflow_id,
                        "name": workflow_record.name,
                        "icon": workflow_record.icon,
                        "description": workflow_record.description,
                    }
                )
            else:
                expected_workflows.append(original_entry)

        assert service._enrich_workflows(input_workflows) == expected_workflows

    def test_get_public_app_analysis_should_return_metrics_and_raise_when_not_found(self, monkeypatch):
        app = SimpleNamespace(id=uuid4(), is_public=True, status=AppStatus.PUBLISHED.value)
        session = _QueueSession([_Query(one_or_none_result=app)])
        service = _build_service(session=session)
        time_ranges = []

        analysis_service = SimpleNamespace(
            get_messages_by_time_range=lambda *_args, **_kwargs: time_ranges.append((_args[1], _args[2])) or ["m1", "m2"],
            calculate_overview_indicators_by_messages=lambda messages: {
                "total_messages": len(messages),
                "active_accounts": 1,
                "avg_of_conversation_messages": 2.0,
                "token_output_rate": 0.5,
                "cost_consumption": 0.1,
            },
            calculate_pop_by_overview_indicators=lambda *_args, **_kwargs: {
                "total_messages": 10,
                "active_accounts": 5,
                "avg_of_conversation_messages": 0.1,
                "token_output_rate": 0.2,
                "cost_consumption": 0.3,
            },
            calculate_trend_by_messages=lambda *_args, **_kwargs: {"total_messages_trend": [1, 2, 3]},
        )
        fake_module = SimpleNamespace(injector=SimpleNamespace(get=lambda _cls: analysis_service))
        monkeypatch.setitem(sys.modules, "app.http.module", fake_module)
        monkeypatch.setattr(
            "internal.service.public_app_service.utc_now_naive",
            lambda: datetime(2024, 1, 8, 18, 30, 0),
        )

        result = service.get_public_app_analysis(str(app.id), None)

        assert result["total_messages"]["data"] == 2
        assert result["total_messages"]["pop"] == 10
        assert result["total_messages_trend"] == [1, 2, 3]
        assert time_ranges[0] == (datetime(2024, 1, 1, 0, 0, 0), datetime(2024, 1, 8, 18, 30, 0))
        assert time_ranges[1] == (datetime(2023, 12, 25, 0, 0, 0), datetime(2024, 1, 1, 0, 0, 0))

        service = _build_service(
            session=_QueueSession([_Query(one_or_none_result=None)]),
        )
        with pytest.raises(NotFoundException):
            service.get_public_app_analysis(str(uuid4()), None)

    def test_get_public_app_analysis_should_raise_not_found_when_app_id_is_invalid(self):
        service = _build_service(
            session=_QueueSession(),
        )

        with pytest.raises(NotFoundException):
            service.get_public_app_analysis("not-a-uuid", None)
