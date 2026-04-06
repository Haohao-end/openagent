from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from openai import APIConnectionError

from internal.task import app_task, dataset_task, document_task


class _RecordingInjector:
    def __init__(self, service):
        self.service = service
        self.requested_classes = []

    def get(self, cls):
        self.requested_classes.append(cls)
        return self.service


def test_document_task_build_documents_should_delegate_to_indexing_service(monkeypatch):
    calls = []
    indexing_service = SimpleNamespace(build_documents=lambda document_ids: calls.append(("build", document_ids)))
    notification_service = SimpleNamespace(create_notification=lambda **_kwargs: None)
    db = SimpleNamespace(
        session=SimpleNamespace(
            query=lambda *_args, **_kwargs: SimpleNamespace(
                filter=lambda *_args, **_kwargs: SimpleNamespace(first=lambda: None)
            )
        )
    )
    injector = SimpleNamespace(
        requested_classes=[],
        get=lambda cls: (
            injector.requested_classes.append(cls)
            or (
                indexing_service
                if cls.__name__ == "IndexingService"
                else notification_service
                if cls.__name__ == "NotificationService"
                else db
            )
        ),
    )
    monkeypatch.setattr("app.http.app.injector", injector)

    document_ids = [uuid4(), uuid4()]
    document_task.build_documents.run(document_ids)

    assert calls == [("build", document_ids)]
    assert injector.requested_classes[0].__name__ == "IndexingService"


def test_document_task_update_document_enabled_should_delegate(monkeypatch):
    calls = []
    service = SimpleNamespace(update_document_enabled=lambda document_id: calls.append(("update", document_id)))
    injector = _RecordingInjector(service)
    monkeypatch.setattr("app.http.app.injector", injector)

    document_id = uuid4()
    document_task.update_document_enabled.run(document_id)

    assert calls == [("update", document_id)]
    assert injector.requested_classes[-1].__name__ == "IndexingService"


def test_document_task_delete_document_should_delegate(monkeypatch):
    calls = []
    service = SimpleNamespace(delete_document=lambda dataset_id, document_id: calls.append((dataset_id, document_id)))
    injector = _RecordingInjector(service)
    monkeypatch.setattr("app.http.module.injector", injector)

    dataset_id = uuid4()
    document_id = uuid4()
    document_task.delete_document.run(dataset_id, document_id)

    assert calls == [(dataset_id, document_id)]
    assert injector.requested_classes[-1].__name__ == "IndexingService"


def test_dataset_task_delete_dataset_should_delegate(monkeypatch):
    calls = []
    service = SimpleNamespace(delete_dataset=lambda dataset_id: calls.append(dataset_id))
    injector = _RecordingInjector(service)
    monkeypatch.setattr("app.http.app.injector", injector)

    dataset_id = uuid4()
    dataset_task.delete_dataset.run(dataset_id)

    assert calls == [dataset_id]
    assert injector.requested_classes[-1].__name__ == "IndexingService"


def test_app_task_auto_create_app_should_delegate(monkeypatch):
    calls = []
    app_id = uuid4()
    app_service = SimpleNamespace(
        auto_create_app=lambda name, desc, account_id: calls.append((name, desc, account_id))
        or SimpleNamespace(id=app_id, name=name)
    )
    notification_service = SimpleNamespace(
        create_agent_notification=lambda **_kwargs: SimpleNamespace(
            id=str(uuid4()),
            user_id=_kwargs["user_id"],
            app_id=_kwargs["app_id"],
            app_name=_kwargs["app_name"],
            created_at=None,
            is_read=False,
        )
    )
    injector = SimpleNamespace(
        requested_classes=[],
        get=lambda cls: (
            injector.requested_classes.append(cls)
            or (app_service if cls.__name__ == "AppService" else notification_service)
        ),
    )
    monkeypatch.setattr("app.http.app.injector", injector)
    monkeypatch.setattr(
        "internal.lib.websocket_manager.ws_manager",
        SimpleNamespace(emit_notification_to_user=lambda *_args, **_kwargs: None),
    )

    account_id = uuid4()
    app_task.auto_create_app.run("Agent", "desc", account_id)

    assert calls == [("Agent", "desc", account_id)]
    assert injector.requested_classes[0].__name__ == "AppService"


def test_app_task_sync_public_app_registry_should_delegate(monkeypatch):
    calls = []
    registry_service = SimpleNamespace(
        sync_public_app=lambda app_id: calls.append(app_id),
    )
    injector = _RecordingInjector(registry_service)
    monkeypatch.setattr("app.http.app.injector", injector)

    app_id = uuid4()
    app_task.sync_public_app_registry.run(str(app_id))

    assert calls == [app_id]
    assert injector.requested_classes[-1].__name__ == "PublicAgentRegistryService"


def test_app_task_sync_public_app_registry_should_retry_on_connection_error(monkeypatch):
    class _RetryTriggered(Exception):
        pass

    def _raise_connection_error(_app_id):
        raise APIConnectionError(
            message="Connection error.",
            request=httpx.Request("POST", "https://api.bianxie.ai/v1/embeddings"),
        )

    retry_calls = []
    registry_service = SimpleNamespace(sync_public_app=_raise_connection_error)
    injector = _RecordingInjector(registry_service)

    def _retry(*, exc, countdown):
        retry_calls.append((exc, countdown))
        raise _RetryTriggered()

    monkeypatch.setattr("app.http.app.injector", injector)
    monkeypatch.setattr(app_task.sync_public_app_registry, "retry", _retry)

    app_id = uuid4()
    with pytest.raises(_RetryTriggered):
        app_task.sync_public_app_registry.run(str(app_id))

    assert injector.requested_classes[-1].__name__ == "PublicAgentRegistryService"
    assert len(retry_calls) == 1
    assert isinstance(retry_calls[0][0], APIConnectionError)
    assert retry_calls[0][1] == 30
