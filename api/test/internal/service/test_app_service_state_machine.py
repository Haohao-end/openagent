from contextlib import contextmanager
from datetime import UTC, datetime
import random
import threading
from types import SimpleNamespace
from uuid import uuid4

import pytest

from internal.entity.app_entity import AppStatus
from internal.exception import FailException
from internal.model import AppDatasetJoin
from internal.service.app_service import AppService


class _DeleteQuery:
    def __init__(self, session):
        self.session = session

    def filter(self, *_args, **_kwargs):
        return self

    def delete(self):
        with self.session.lock:
            self.session.delete_calls += 1


class _ScalarQuery:
    def __init__(self, session):
        self.session = session

    def filter(self, *_args, **_kwargs):
        return self

    def scalar(self):
        with self.session.lock:
            return self.session.max_published_version


class _Session:
    def __init__(self):
        self.lock = threading.Lock()
        self.delete_calls = 0
        self.max_published_version = 0

    def query(self, model):
        model_name = getattr(model, "__name__", "")
        if model_name == AppDatasetJoin.__name__:
            return _DeleteQuery(self)
        return _ScalarQuery(self)


class _DB:
    def __init__(self):
        self.session = _Session()
        self.auto_commit_count = 0
        self._lock = threading.Lock()

    @contextmanager
    def auto_commit(self):
        with self._lock:
            self.auto_commit_count += 1
        yield


def _build_service_with_state(app, draft_config):
    db = _DB()
    service = AppService(
        db=db,
        redis_client=SimpleNamespace(),
        cos_service=SimpleNamespace(),
        retrieval_service=SimpleNamespace(),
        app_config_service=SimpleNamespace(),
        api_provider_manager=SimpleNamespace(),
        conversation_service=SimpleNamespace(),
        language_model_manager=SimpleNamespace(),
        language_model_service=SimpleNamespace(),
        builtin_provider_manager=SimpleNamespace(),
        icon_generator_service=SimpleNamespace(),
    )

    create_calls = []
    update_calls = []
    create_lock = threading.Lock()
    update_lock = threading.Lock()

    def _create(model, **kwargs):
        with create_lock:
            create_calls.append((model.__name__, kwargs))

        if model.__name__ == "AppConfig":
            return SimpleNamespace(id=uuid4(), **kwargs)

        if model.__name__ == "AppDatasetJoin":
            return SimpleNamespace(id=uuid4(), **kwargs)

        if model.__name__ == "AppConfigVersion":
            with db.session.lock:
                db.session.max_published_version = kwargs["version"]
            return SimpleNamespace(id=uuid4(), **kwargs)

        return SimpleNamespace(id=uuid4(), **kwargs)

    def _update(target, **kwargs):
        with update_lock:
            update_calls.append((target, kwargs))
            for key, value in kwargs.items():
                setattr(target, key, value)
        return target

    service.get_app = lambda *_args, **_kwargs: app
    service.get_draft_app_config = lambda *_args, **_kwargs: draft_config
    service.create = _create
    service.update = _update

    return service, db, create_calls, update_calls


def _build_draft_config():
    return {
        "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
        "dialog_round": 4,
        "preset_prompt": "prompt",
        "tools": [
            {
                "type": "builtin_tool",
                "provider": {"id": "google"},
                "tool": {"name": "google_serper", "params": {}},
            }
        ],
        "workflows": [{"id": str(uuid4())}],
        "datasets": [{"id": str(uuid4())}, {"id": str(uuid4())}],
        "retrieval_config": {"k": 3, "score": 0.5},
        "long_term_memory": {"enable": True},
        "opening_statement": "hello",
        "opening_questions": ["q1", "q2"],
        "speech_to_text": {"enable": True},
        "text_to_speech": {"enable": True, "voice": "alex"},
        "suggested_after_answer": {"enable": True},
        "review_config": {"enable": False},
    }


def _build_stateful_app(status: str = AppStatus.DRAFT.value):
    is_published = status == AppStatus.PUBLISHED.value
    return SimpleNamespace(
        id=uuid4(),
        account_id=uuid4(),
        status=status,
        app_config_id=uuid4() if is_published else None,
        is_public=is_published,
        published_at=datetime.now(UTC).replace(tzinfo=None) if is_published else None,
        draft_app_config=SimpleNamespace(
            id=uuid4(),
            app_id=uuid4(),
            version=0,
            config_type="draft",
            updated_at=None,
            created_at=None,
            model_config={"provider": "openai", "model": "gpt-4o-mini"},
            dialog_round=4,
            preset_prompt="prompt",
            tools=[],
            workflows=[],
            datasets=[],
            retrieval_config={},
            long_term_memory={"enable": True},
            opening_statement="hello",
            opening_questions=["q1", "q2"],
            speech_to_text={"enable": True},
            text_to_speech={"enable": True, "voice": "alex"},
            suggested_after_answer={"enable": True},
            review_config={"enable": False},
        ),
    )


def _extract_versions(create_calls):
    return [
        kwargs["version"]
        for model_name, kwargs in create_calls
        if model_name == "AppConfigVersion"
    ]


class TestAppServiceStateMachine:
    def test_publish_cancel_state_machine_should_hold_invariants_under_random_actions(self):
        rng = random.Random(20260303)
        app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            status=AppStatus.DRAFT.value,
            app_config_id=None,
            is_public=False,
            published_at=None,
            draft_app_config=SimpleNamespace(
                id=uuid4(),
                app_id=uuid4(),
                version=0,
                config_type="draft",
                updated_at=None,
                created_at=None,
                model_config={"provider": "openai", "model": "gpt-4o-mini"},
                dialog_round=4,
                preset_prompt="prompt",
                tools=[],
                workflows=[],
                datasets=[],
                retrieval_config={},
                long_term_memory={"enable": True},
                opening_statement="hello",
                opening_questions=["q1", "q2"],
                speech_to_text={"enable": True},
                text_to_speech={"enable": True, "voice": "alex"},
                suggested_after_answer={"enable": True},
                review_config={"enable": False},
            ),
        )
        account = SimpleNamespace(id=app.account_id)
        service, db, create_calls, _update_calls = _build_service_with_state(app, _build_draft_config())

        publish_count = 0
        cancel_success_count = 0
        expected_history_version = 0

        for _ in range(80):
            action = rng.choice(["publish_public", "publish_private", "cancel"])

            if action == "cancel":
                if app.status == AppStatus.PUBLISHED.value:
                    service.cancel_publish_app_config(app.id, account)
                    cancel_success_count += 1
                    assert app.status == AppStatus.DRAFT.value
                    assert app.app_config_id is None
                    assert app.is_public is False
                    assert app.published_at is None
                else:
                    with pytest.raises(FailException):
                        service.cancel_publish_app_config(app.id, account)
                continue

            share_to_square = action == "publish_public"
            previous_published_at = app.published_at
            service.publish_draft_app_config(app.id, account, share_to_square=share_to_square)
            publish_count += 1

            assert app.status == AppStatus.PUBLISHED.value
            assert app.app_config_id is not None

            if previous_published_at is None:
                assert app.published_at is not None
            else:
                assert app.published_at == previous_published_at

            if share_to_square:
                assert app.is_public is True

            history_versions = [
                kwargs["version"]
                for model_name, kwargs in create_calls
                if model_name == "AppConfigVersion"
            ]
            assert history_versions
            expected_history_version += 1
            assert history_versions[-1] == expected_history_version

        assert db.auto_commit_count == publish_count
        assert db.session.delete_calls == publish_count
        assert sum(1 for model_name, _ in create_calls if model_name == "AppDatasetJoin") == publish_count * 2
        assert cancel_success_count >= 1

    def test_publish_cancel_concurrency_should_keep_app_state_consistent(self):
        app = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            status=AppStatus.PUBLISHED.value,
            app_config_id=uuid4(),
            is_public=True,
            published_at=datetime.now(UTC).replace(tzinfo=None),
            draft_app_config=SimpleNamespace(
                id=uuid4(),
                app_id=uuid4(),
                version=0,
                config_type="draft",
                updated_at=None,
                created_at=None,
                model_config={"provider": "openai", "model": "gpt-4o-mini"},
                dialog_round=4,
                preset_prompt="prompt",
                tools=[],
                workflows=[],
                datasets=[],
                retrieval_config={},
                long_term_memory={"enable": True},
                opening_statement="hello",
                opening_questions=["q1", "q2"],
                speech_to_text={"enable": True},
                text_to_speech={"enable": True, "voice": "alex"},
                suggested_after_answer={"enable": True},
                review_config={"enable": False},
            ),
        )
        account = SimpleNamespace(id=app.account_id)
        service, _db, _create_calls, _update_calls = _build_service_with_state(app, _build_draft_config())

        barrier = threading.Barrier(3)
        errors = []

        def _publish_loop():
            try:
                barrier.wait()
                for index in range(30):
                    service.publish_draft_app_config(
                        app.id,
                        account,
                        share_to_square=(index % 2 == 0),
                    )
            except Exception as exc:  # pragma: no cover - 调试辅助
                errors.append(exc)

        def _cancel_loop():
            try:
                barrier.wait()
                for _ in range(30):
                    try:
                        service.cancel_publish_app_config(app.id, account)
                    except FailException:
                        # 并发下可能遇到 Draft 状态，属于预期冲突。
                        pass
            except Exception as exc:  # pragma: no cover - 调试辅助
                errors.append(exc)

        t1 = threading.Thread(target=_publish_loop)
        t2 = threading.Thread(target=_cancel_loop)
        t1.start()
        t2.start()
        barrier.wait()
        t1.join()
        t2.join()

        assert errors == []

        if app.status == AppStatus.DRAFT.value:
            assert app.app_config_id is None
            assert app.is_public is False
            assert app.published_at is None
        else:
            assert app.status == AppStatus.PUBLISHED.value
            assert app.app_config_id is not None

    @pytest.mark.parametrize("seed", [11, 23, 37, 41, 59])
    def test_publish_cancel_state_machine_should_match_reference_model_across_random_traces(self, seed):
        rng = random.Random(seed)
        app = _build_stateful_app(status=AppStatus.DRAFT.value)
        account = SimpleNamespace(id=app.account_id)
        service, db, create_calls, _update_calls = _build_service_with_state(app, _build_draft_config())

        expected_status = AppStatus.DRAFT.value
        expected_is_public = False
        expected_has_published_at = False
        expected_publish_count = 0

        for _ in range(120):
            action = rng.choice(["publish_public", "publish_private", "cancel"])

            if action == "cancel":
                if expected_status == AppStatus.PUBLISHED.value:
                    service.cancel_publish_app_config(app.id, account)
                    expected_status = AppStatus.DRAFT.value
                    expected_is_public = False
                    expected_has_published_at = False
                else:
                    with pytest.raises(FailException):
                        service.cancel_publish_app_config(app.id, account)
            else:
                service.publish_draft_app_config(
                    app.id,
                    account,
                    share_to_square=(action == "publish_public"),
                )
                expected_publish_count += 1
                expected_status = AppStatus.PUBLISHED.value
                if action == "publish_public":
                    expected_is_public = True
                if not expected_has_published_at:
                    expected_has_published_at = True

            assert app.status == expected_status
            assert app.is_public == expected_is_public
            if expected_status == AppStatus.DRAFT.value:
                assert app.app_config_id is None
                assert app.published_at is None
            else:
                assert app.app_config_id is not None
                assert app.published_at is not None

        versions = _extract_versions(create_calls)
        assert versions == list(range(1, expected_publish_count + 1))
        assert db.auto_commit_count == expected_publish_count
        assert db.session.delete_calls == expected_publish_count

        dataset_join_count = sum(
            1
            for model_name, _kwargs in create_calls
            if model_name == "AppDatasetJoin"
        )
        assert dataset_join_count == expected_publish_count * 2

    def test_publish_cancel_multi_actor_concurrency_should_preserve_core_invariants(self):
        app = _build_stateful_app(status=AppStatus.PUBLISHED.value)
        account = SimpleNamespace(id=app.account_id)
        service, db, create_calls, _update_calls = _build_service_with_state(app, _build_draft_config())

        barrier = threading.Barrier(4)
        errors = []

        def _run_publish(is_public: bool):
            try:
                barrier.wait()
                for _ in range(35):
                    service.publish_draft_app_config(
                        app.id,
                        account,
                        share_to_square=is_public,
                    )
            except Exception as exc:  # pragma: no cover - 调试辅助
                errors.append(exc)

        def _run_cancel():
            try:
                barrier.wait()
                for _ in range(45):
                    try:
                        service.cancel_publish_app_config(app.id, account)
                    except FailException:
                        pass
            except Exception as exc:  # pragma: no cover - 调试辅助
                errors.append(exc)

        t1 = threading.Thread(target=_run_publish, args=(True,))
        t2 = threading.Thread(target=_run_publish, args=(False,))
        t3 = threading.Thread(target=_run_cancel)
        t1.start()
        t2.start()
        t3.start()
        barrier.wait()
        t1.join()
        t2.join()
        t3.join()

        assert errors == []

        publish_count = sum(
            1
            for model_name, _kwargs in create_calls
            if model_name == "AppConfig"
        )
        versions = _extract_versions(create_calls)
        dataset_join_count = sum(
            1
            for model_name, _kwargs in create_calls
            if model_name == "AppDatasetJoin"
        )

        assert publish_count == len(versions)
        assert db.auto_commit_count == publish_count
        assert db.session.delete_calls == publish_count
        assert dataset_join_count == publish_count * 2

        if app.status == AppStatus.DRAFT.value:
            assert app.app_config_id is None
            assert app.published_at is None
            assert app.is_public is False
        else:
            assert app.status == AppStatus.PUBLISHED.value
            assert app.app_config_id is not None
            assert app.published_at is not None
