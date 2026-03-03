from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4
import sys

import pytest
from langchain_core.documents import Document as LCDocument

from internal.entity.dataset_entity import DocumentStatus, SegmentStatus, ProcessType
from internal.exception import (
    FailException,
    ForbiddenException,
    NotFoundException,
    ValidateErrorException,
)
from internal.model import AppDatasetJoin, Dataset, Document, Segment, KeywordTable, DatasetQuery, ProcessRule
from internal.service.dataset_service import DatasetService as _DatasetService
from internal.service.document_service import DocumentService
from internal.service.indexing_service import IndexingService
from internal.service.jieba_service import JiebaService
from internal.service.keyword_table_service import KeywordTableService
from internal.service.process_rule_service import ProcessRuleService
from internal.service.retrieval_service import RetrievalService
from internal.service.segment_service import SegmentService


class _QueryStub:
    def __init__(self, *, one_or_none_result=None, all_result=None, scalar_result=None, first_result=None):
        self._one_or_none_result = one_or_none_result
        self._all_result = all_result if all_result is not None else []
        self._scalar_result = scalar_result
        self._first_result = first_result
        self.deleted = False

    def filter(self, *_args, **_kwargs):
        return self

    def filter_by(self, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def with_entities(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def one_or_none(self):
        return self._one_or_none_result

    def all(self):
        return self._all_result

    def scalar(self):
        return self._scalar_result

    def first(self):
        return self._first_result

    def update(self, *_args, **_kwargs):
        return 1

    def delete(self):
        self.deleted = True


class _DBStub:
    def __init__(self, session):
        self.session = session

    @contextmanager
    def auto_commit(self):
        yield


def _new_dataset_service(**kwargs):
    kwargs.setdefault("icon_generator_service", SimpleNamespace())
    return _DatasetService(**kwargs)


@contextmanager
def _null_context():
    """通用空上下文，便于替代真实事务上下文。"""
    yield


class _DummyLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _RedisStub:
    def __init__(self, get_value=None):
        self._get_value = get_value
        self.setex_calls = []
        self.delete_calls = []
        self.lock_calls = []

    def get(self, _key):
        return self._get_value

    def setex(self, key, ttl, value):
        self.setex_calls.append((key, ttl, value))

    def delete(self, key):
        self.delete_calls.append(key)

    def lock(self, key, timeout=None):
        self.lock_calls.append((key, timeout))
        return _DummyLock()


class TestDocumentService:
    def test_create_documents_should_raise_forbidden_when_dataset_not_accessible(self, monkeypatch):
        dataset_id = uuid4()
        account = SimpleNamespace(id=uuid4())
        service = DocumentService(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda _model: _QueryStub(all_result=[]))),
            redis_client=_RedisStub(),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)

        with pytest.raises(ForbiddenException):
            service.create_documents(dataset_id, [uuid4()], account=account)

    def test_create_documents_should_raise_when_no_legal_upload_files(self, monkeypatch):
        dataset_id = uuid4()
        account = SimpleNamespace(id=uuid4())
        upload_file = SimpleNamespace(id=uuid4(), extension="exe", name="evil.exe")
        session = SimpleNamespace(query=lambda _model: _QueryStub(all_result=[upload_file]))
        service = DocumentService(db=SimpleNamespace(session=session), redis_client=_RedisStub())
        monkeypatch.setattr(
            service,
            "get",
            lambda model, _id: SimpleNamespace(id=dataset_id, account_id=account.id) if model is Dataset else None,
        )

        with pytest.raises(FailException):
            service.create_documents(dataset_id, [upload_file.id], account=account)

    def test_create_documents_should_create_process_rule_and_documents_then_dispatch_task(self, monkeypatch):
        dataset_id = uuid4()
        account = SimpleNamespace(id=uuid4())
        upload_file_1 = SimpleNamespace(id=uuid4(), extension="txt", name="doc-1.txt")
        upload_file_2 = SimpleNamespace(id=uuid4(), extension="md", name="doc-2.md")
        session = SimpleNamespace(query=lambda _model: _QueryStub(all_result=[upload_file_1, upload_file_2]))
        service = DocumentService(db=SimpleNamespace(session=session), redis_client=_RedisStub())
        monkeypatch.setattr(
            service,
            "get",
            lambda model, _id: SimpleNamespace(id=dataset_id, account_id=account.id) if model is Dataset else None,
        )
        monkeypatch.setattr(service, "get_latest_document_position", lambda _dataset_id: 5)

        process_rule = SimpleNamespace(id=uuid4())
        create_calls = []
        document_ids = [uuid4(), uuid4()]

        def _fake_create(model, **kwargs):
            create_calls.append((model, kwargs))
            if model is ProcessRule:
                return process_rule
            doc_idx = len([item for item in create_calls if item[0] is Document]) - 1
            return SimpleNamespace(id=document_ids[doc_idx], **kwargs)

        monkeypatch.setattr(service, "create", _fake_create)
        task_calls = []
        monkeypatch.setattr(
            "internal.service.document_service.build_documents.delay",
            lambda ids: task_calls.append(ids),
        )

        documents, batch = service.create_documents(
            dataset_id=dataset_id,
            upload_file_ids=[upload_file_1.id, upload_file_2.id],
            process_type=ProcessType.CUSTOM.value,
            rule={"segment": {"chunk_size": 200}},
            account=account,
        )

        assert len(documents) == 2
        assert batch
        assert create_calls[0][0] is ProcessRule
        assert create_calls[0][1]["mode"] == ProcessType.CUSTOM.value
        assert create_calls[1][0] is Document
        assert create_calls[1][1]["position"] == 6
        assert create_calls[2][1]["position"] == 7
        assert task_calls == [[document_ids[0], document_ids[1]]]

    def test_get_documents_status_should_raise_forbidden_when_dataset_not_accessible(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        service = DocumentService(db=SimpleNamespace(session=SimpleNamespace()), redis_client=_RedisStub())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)

        with pytest.raises(ForbiddenException):
            service.get_documents_status(uuid4(), "batch-1", account)

    def test_get_documents_status_should_raise_when_batch_has_no_documents(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        service = DocumentService(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda _model: _QueryStub(all_result=[]))),
            redis_client=_RedisStub(),
        )
        monkeypatch.setattr(
            service,
            "get",
            lambda model, _id: SimpleNamespace(id=dataset_id, account_id=account.id) if model is Dataset else None,
        )

        with pytest.raises(NotFoundException):
            service.get_documents_status(dataset_id, "batch-empty", account)

    def test_update_document_enabled_should_raise_when_status_unchanged(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document = SimpleNamespace(
            id=uuid4(),
            dataset_id=dataset_id,
            account_id=account.id,
            status=DocumentStatus.COMPLETED.value,
            enabled=True,
        )
        service = DocumentService(db=SimpleNamespace(session=SimpleNamespace()), redis_client=_RedisStub())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: document)

        with pytest.raises(FailException):
            service.update_document_enabled(dataset_id, document.id, True, account)

    def test_update_document_enabled_should_raise_when_document_not_found(self, monkeypatch):
        service = DocumentService(db=SimpleNamespace(session=SimpleNamespace()), redis_client=_RedisStub())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)

        with pytest.raises(NotFoundException):
            service.update_document_enabled(uuid4(), uuid4(), True, SimpleNamespace(id=uuid4()))

    def test_update_document_enabled_should_raise_when_document_forbidden(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        service = DocumentService(db=SimpleNamespace(session=SimpleNamespace()), redis_client=_RedisStub())
        document = SimpleNamespace(
            id=uuid4(),
            dataset_id=uuid4(),
            account_id=uuid4(),
            status=DocumentStatus.COMPLETED.value,
            enabled=False,
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: document)

        with pytest.raises(ForbiddenException):
            service.update_document_enabled(uuid4(), document.id, True, account)

    def test_update_document_enabled_should_raise_when_status_not_completed(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        service = DocumentService(db=SimpleNamespace(session=SimpleNamespace()), redis_client=_RedisStub())
        document = SimpleNamespace(
            id=uuid4(),
            dataset_id=dataset_id,
            account_id=account.id,
            status=DocumentStatus.PARSING.value,
            enabled=False,
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: document)

        with pytest.raises(ForbiddenException):
            service.update_document_enabled(dataset_id, document.id, True, account)

    def test_update_document_enabled_should_raise_when_locked(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document = SimpleNamespace(
            id=uuid4(),
            dataset_id=dataset_id,
            account_id=account.id,
            status=DocumentStatus.COMPLETED.value,
            enabled=False,
        )
        service = DocumentService(db=SimpleNamespace(session=SimpleNamespace()), redis_client=_RedisStub(get_value="1"))
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: document)

        with pytest.raises(FailException):
            service.update_document_enabled(dataset_id, document.id, True, account)

    def test_update_document_enabled_should_update_state_lock_and_dispatch_task(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document = SimpleNamespace(
            id=uuid4(),
            dataset_id=dataset_id,
            account_id=account.id,
            status=DocumentStatus.COMPLETED.value,
            enabled=False,
        )
        redis_client = _RedisStub()
        service = DocumentService(db=SimpleNamespace(session=SimpleNamespace()), redis_client=redis_client)
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: document)
        update_calls = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: update_calls.append((target, kwargs)) or target,
        )
        task_calls = []
        monkeypatch.setattr(
            "internal.service.document_service.update_document_enabled.delay",
            lambda document_id: task_calls.append(document_id),
        )

        result = service.update_document_enabled(dataset_id, document.id, True, account)

        assert result is document
        assert update_calls[0][0] is document
        assert update_calls[0][1]["enabled"] is True
        assert update_calls[0][1]["disabled_at"] is None
        assert len(redis_client.setex_calls) == 1
        assert task_calls == [document.id]

    def test_delete_document_should_raise_when_document_not_deletable(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document = SimpleNamespace(
            id=uuid4(),
            dataset_id=dataset_id,
            account_id=account.id,
            status=DocumentStatus.PARSING.value,
        )
        service = DocumentService(db=SimpleNamespace(session=SimpleNamespace()), redis_client=_RedisStub())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: document)

        with pytest.raises(FailException):
            service.delete_document(dataset_id, document.id, account)

    def test_delete_document_should_raise_when_document_not_found(self, monkeypatch):
        service = DocumentService(db=SimpleNamespace(session=SimpleNamespace()), redis_client=_RedisStub())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)

        with pytest.raises(NotFoundException):
            service.delete_document(uuid4(), uuid4(), SimpleNamespace(id=uuid4()))

    def test_delete_document_should_raise_when_document_forbidden(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        service = DocumentService(db=SimpleNamespace(session=SimpleNamespace()), redis_client=_RedisStub())
        document = SimpleNamespace(
            id=uuid4(),
            dataset_id=uuid4(),
            account_id=uuid4(),
            status=DocumentStatus.COMPLETED.value,
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: document)

        with pytest.raises(ForbiddenException):
            service.delete_document(uuid4(), document.id, account)

    def test_delete_document_should_delete_and_dispatch_async_cleanup(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document = SimpleNamespace(
            id=uuid4(),
            dataset_id=dataset_id,
            account_id=account.id,
            status=DocumentStatus.COMPLETED.value,
        )
        service = DocumentService(db=SimpleNamespace(session=SimpleNamespace()), redis_client=_RedisStub())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: document)
        delete_calls = []
        monkeypatch.setattr(service, "delete", lambda target: delete_calls.append(target))
        task_calls = []
        monkeypatch.setattr(
            "internal.service.document_service.delete_document.delay",
            lambda dataset_id, document_id: task_calls.append((dataset_id, document_id)),
        )

        result = service.delete_document(dataset_id, document.id, account)

        assert result is document
        assert delete_calls == [document]
        assert task_calls == [(dataset_id, document.id)]

    def test_get_documents_status_should_return_document_status_payload(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document = SimpleNamespace(
            id=uuid4(),
            name="doc-a",
            position=1,
            error="",
            status=DocumentStatus.COMPLETED.value,
            processing_started_at=None,
            parsing_completed_at=None,
            splitting_completed_at=None,
            indexing_completed_at=None,
            completed_at=None,
            stopped_at=None,
            created_at=datetime.now(UTC),
            upload_file=SimpleNamespace(size=10, extension="txt", mime_type="text/plain"),
        )

        class _Session:
            def __init__(self):
                self.calls = 0

            def query(self, _model):
                self.calls += 1
                if self.calls == 1:
                    return _QueryStub(all_result=[document])
                if self.calls == 2:
                    return _QueryStub(scalar_result=3)
                return _QueryStub(scalar_result=2)

        service = DocumentService(db=SimpleNamespace(session=_Session()), redis_client=_RedisStub())
        monkeypatch.setattr(
            service,
            "get",
            lambda model, _id: SimpleNamespace(id=dataset_id, account_id=account.id) if model is Dataset else None,
        )

        result = service.get_documents_status(dataset_id, "batch-1", account)

        assert result[0]["id"] == document.id
        assert result[0]["segment_count"] == 3
        assert result[0]["completed_segment_count"] == 2
        assert result[0]["extension"] == "txt"

    def test_get_document_should_return_document_when_belongs_to_dataset_and_account(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document = SimpleNamespace(id=uuid4(), dataset_id=dataset_id, account_id=account.id)
        service = DocumentService(db=SimpleNamespace(session=SimpleNamespace()), redis_client=_RedisStub())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: document)

        result = service.get_document(dataset_id, document.id, account)

        assert result is document

    def test_get_document_should_raise_when_not_found(self, monkeypatch):
        service = DocumentService(db=SimpleNamespace(session=SimpleNamespace()), redis_client=_RedisStub())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)

        with pytest.raises(NotFoundException):
            service.get_document(uuid4(), uuid4(), SimpleNamespace(id=uuid4()))

    def test_get_document_should_raise_when_forbidden(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document = SimpleNamespace(id=uuid4(), dataset_id=dataset_id, account_id=uuid4())
        service = DocumentService(db=SimpleNamespace(session=SimpleNamespace()), redis_client=_RedisStub())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: document)

        with pytest.raises(ForbiddenException):
            service.get_document(dataset_id, document.id, account)

    def test_update_document_should_delegate_update_with_kwargs(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document = SimpleNamespace(id=uuid4(), dataset_id=dataset_id, account_id=account.id, name="old")
        service = DocumentService(db=SimpleNamespace(session=SimpleNamespace()), redis_client=_RedisStub())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: document)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.update_document(dataset_id, document.id, account, name="new")

        assert result is document
        assert updates == [(document, {"name": "new"})]

    def test_update_document_should_raise_when_not_found(self, monkeypatch):
        service = DocumentService(db=SimpleNamespace(session=SimpleNamespace()), redis_client=_RedisStub())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)

        with pytest.raises(NotFoundException):
            service.update_document(uuid4(), uuid4(), SimpleNamespace(id=uuid4()), name="new")

    def test_update_document_should_raise_when_forbidden(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        document = SimpleNamespace(id=uuid4(), dataset_id=uuid4(), account_id=uuid4())
        service = DocumentService(db=SimpleNamespace(session=SimpleNamespace()), redis_client=_RedisStub())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: document)

        with pytest.raises(ForbiddenException):
            service.update_document(uuid4(), document.id, account, name="new")

    def test_get_documents_with_page_should_use_paginator(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        service = DocumentService(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda _model: _QueryStub(all_result=[]))),
            redis_client=_RedisStub(),
        )
        monkeypatch.setattr(
            service,
            "get",
            lambda model, _id: SimpleNamespace(id=dataset_id, account_id=account.id) if model is Dataset else None,
        )
        captures = {}

        class _Paginator:
            def __init__(self, db, req):
                captures["db"] = db
                captures["req"] = req

            def paginate(self, query):
                captures["query"] = query
                return ["document-1"]

        monkeypatch.setattr("internal.service.document_service.Paginator", _Paginator)
        req = SimpleNamespace(
            current_page=SimpleNamespace(data=1),
            page_size=SimpleNamespace(data=20),
            search_word=SimpleNamespace(data="doc"),
        )

        records, paginator = service.get_documents_with_page(dataset_id, req, account)

        assert records == ["document-1"]
        assert captures["req"] is req
        assert captures["db"] is service.db
        assert captures["query"] is not None
        assert isinstance(paginator, _Paginator)

    def test_get_documents_with_page_should_build_default_filter_when_search_word_empty(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()

        class _Query:
            def __init__(self):
                self.filter_calls = []

            def filter(self, *args, **_kwargs):
                self.filter_calls.append(args)
                return self

            def order_by(self, *_args, **_kwargs):
                return self

        query = _Query()
        service = DocumentService(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda _model: query)),
            redis_client=_RedisStub(),
        )
        monkeypatch.setattr(
            service,
            "get",
            lambda model, _id: SimpleNamespace(id=dataset_id, account_id=account.id) if model is Dataset else None,
        )

        class _Paginator:
            def __init__(self, db, req):
                pass

            def paginate(self, query_obj):
                assert query_obj is query
                return ["doc-1"]

        monkeypatch.setattr("internal.service.document_service.Paginator", _Paginator)
        req = SimpleNamespace(
            current_page=SimpleNamespace(data=1),
            page_size=SimpleNamespace(data=20),
            search_word=SimpleNamespace(data=""),
        )

        records, _paginator = service.get_documents_with_page(dataset_id, req, account)

        assert records == ["doc-1"]
        assert len(query.filter_calls[0]) == 2

    def test_get_documents_with_page_should_raise_when_dataset_not_found(self, monkeypatch):
        service = DocumentService(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda _model: _QueryStub(all_result=[]))),
            redis_client=_RedisStub(),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)
        req = SimpleNamespace(
            current_page=SimpleNamespace(data=1),
            page_size=SimpleNamespace(data=20),
            search_word=SimpleNamespace(data=None),
        )

        with pytest.raises(NotFoundException):
            service.get_documents_with_page(uuid4(), req, SimpleNamespace(id=uuid4()))

    def test_get_latest_document_position_should_return_zero_when_empty(self):
        service = DocumentService(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda _model: _QueryStub(first_result=None))),
            redis_client=_RedisStub(),
        )

        assert service.get_latest_document_position(uuid4()) == 0
