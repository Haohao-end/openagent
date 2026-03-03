from types import SimpleNamespace
from uuid import uuid4

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
    service = SimpleNamespace(build_documents=lambda document_ids: calls.append(("build", document_ids)))
    injector = _RecordingInjector(service)
    monkeypatch.setattr("app.http.app.injector", injector)

    document_ids = [uuid4(), uuid4()]
    document_task.build_documents.run(document_ids)

    assert calls == [("build", document_ids)]
    assert injector.requested_classes[-1].__name__ == "IndexingService"


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
    service = SimpleNamespace(auto_create_app=lambda name, desc, account_id: calls.append((name, desc, account_id)))
    injector = _RecordingInjector(service)
    monkeypatch.setattr("app.http.module.injector", injector)

    account_id = uuid4()
    app_task.auto_create_app.run("Agent", "desc", account_id)

    assert calls == [("Agent", "desc", account_id)]
    assert injector.requested_classes[-1].__name__ == "AppService"
