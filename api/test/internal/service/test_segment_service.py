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


class TestSegmentService:
    def _build_service(self):
        return SegmentService(
            db=SimpleNamespace(session=SimpleNamespace()),
            redis_client=_RedisStub(),
            jieba_service=SimpleNamespace(extract_keywords=lambda _content, _k: ["kw"]),
            embeddings_service=SimpleNamespace(calculate_token_count=lambda _content: 2, embeddings=SimpleNamespace(embed_query=lambda _q: [0.1])),
            keyword_table_service=SimpleNamespace(
                add_keyword_table_from_ids=lambda *_args, **_kwargs: None,
                delete_keyword_table_from_ids=lambda *_args, **_kwargs: None,
            ),
            vector_database_service=SimpleNamespace(
                vector_store=SimpleNamespace(add_documents=lambda **_kwargs: None),
                collection=SimpleNamespace(
                    data=SimpleNamespace(
                        update=lambda **_kwargs: None,
                        delete_by_id=lambda *_args, **_kwargs: None,
                    )
                ),
            ),
        )

    def test_create_segment_should_raise_when_token_too_large(self):
        service = self._build_service()
        service.embeddings_service = SimpleNamespace(calculate_token_count=lambda _content: 1001)

        req = SimpleNamespace(content=SimpleNamespace(data="x" * 100), keywords=SimpleNamespace(data=[]))
        with pytest.raises(ValidateErrorException):
            service.create_segment(uuid4(), uuid4(), req, SimpleNamespace(id=uuid4()))

    def test_update_segment_enabled_should_raise_when_status_not_changed(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document_id = uuid4()
        segment = SimpleNamespace(
            id=uuid4(),
            account_id=account.id,
            dataset_id=dataset_id,
            document_id=document_id,
            status=SegmentStatus.COMPLETED.value,
            enabled=True,
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: segment)

        with pytest.raises(FailException):
            service.update_segment_enabled(dataset_id, document_id, segment.id, True, account)

    def test_delete_segment_should_delete_segment_and_recount_document(self, monkeypatch):
        document = SimpleNamespace(id=uuid4())
        segment = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            dataset_id=uuid4(),
            document_id=uuid4(),
            node_id=uuid4(),
            status=SegmentStatus.COMPLETED.value,
            document=document,
        )

        query_stub = _QueryStub(first_result=(18, 7))
        session = SimpleNamespace(query=lambda *_args, **_kwargs: query_stub)
        service = SegmentService(
            db=SimpleNamespace(session=session),
            redis_client=_RedisStub(),
            jieba_service=SimpleNamespace(),
            embeddings_service=SimpleNamespace(embeddings=SimpleNamespace(embed_query=lambda _q: [0.1]), calculate_token_count=lambda _q: 1),
            keyword_table_service=SimpleNamespace(delete_keyword_table_from_ids=lambda *_args, **_kwargs: None),
            vector_database_service=SimpleNamespace(collection=SimpleNamespace(data=SimpleNamespace(delete_by_id=lambda *_args, **_kwargs: None))),
        )
        account = SimpleNamespace(id=segment.account_id)
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: segment)
        monkeypatch.setattr(service, "delete", lambda *_args, **_kwargs: None)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.delete_segment(segment.dataset_id, segment.document_id, segment.id, account)

        assert result is segment
        assert updates[-1][0] is document
        assert updates[-1][1]["character_count"] == 18
        assert updates[-1][1]["token_count"] == 7

    def test_get_segment_should_return_when_owned(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document_id = uuid4()
        segment = SimpleNamespace(
            id=uuid4(),
            account_id=account.id,
            dataset_id=dataset_id,
            document_id=document_id,
            status=SegmentStatus.COMPLETED.value,
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: segment)

        result = service.get_segment(dataset_id, document_id, segment.id, account)

        assert result is segment

    def test_get_segments_with_page_should_use_paginator(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document_id = uuid4()
        document = SimpleNamespace(id=document_id, dataset_id=dataset_id, account_id=account.id)
        service = self._build_service()
        service.db = SimpleNamespace(session=SimpleNamespace(query=lambda _model: _QueryStub(all_result=[])))
        monkeypatch.setattr(
            service,
            "get",
            lambda model, _id: document if model is Document else None,
        )
        captures = {}

        class _Paginator:
            def __init__(self, db, req):
                captures["db"] = db
                captures["req"] = req

            def paginate(self, query):
                captures["query"] = query
                return ["segment-1"]

        monkeypatch.setattr("internal.service.segment_service.Paginator", _Paginator)
        req = SimpleNamespace(
            current_page=SimpleNamespace(data=1),
            page_size=SimpleNamespace(data=20),
            search_word=SimpleNamespace(data="内容"),
        )

        segments, paginator = service.get_segments_with_page(dataset_id, document_id, req, account)

        assert segments == ["segment-1"]
        assert captures["req"] is req
        assert captures["db"] is service.db
        assert captures["query"] is not None
        assert isinstance(paginator, _Paginator)

    def test_update_segment_should_sync_keyword_document_and_vector_when_content_changed(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document = SimpleNamespace(id=uuid4(), enabled=True)
        segment = SimpleNamespace(
            id=uuid4(),
            account_id=account.id,
            dataset_id=dataset_id,
            document_id=document.id,
            status=SegmentStatus.COMPLETED.value,
            hash="old-hash",
            node_id=uuid4(),
            document=document,
        )
        keyword_calls = []
        vector_calls = []
        service = SegmentService(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda *_args, **_kwargs: _QueryStub(first_result=(12, 8)))),
            redis_client=_RedisStub(),
            jieba_service=SimpleNamespace(extract_keywords=lambda _content, _k: ["k1"]),
            embeddings_service=SimpleNamespace(
                calculate_token_count=lambda _content: 6,
                embeddings=SimpleNamespace(embed_query=lambda _q: [0.1, 0.2]),
            ),
            keyword_table_service=SimpleNamespace(
                delete_keyword_table_from_ids=lambda *_args, **_kwargs: keyword_calls.append("delete"),
                add_keyword_table_from_ids=lambda *_args, **_kwargs: keyword_calls.append("add"),
            ),
            vector_database_service=SimpleNamespace(
                collection=SimpleNamespace(
                    data=SimpleNamespace(
                        update=lambda **kwargs: vector_calls.append(kwargs),
                    )
                )
            ),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: segment)
        monkeypatch.setattr("internal.service.segment_service.generate_text_hash", lambda _text: "new-hash")
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )
        req = SimpleNamespace(
            content=SimpleNamespace(data="新内容"),
            keywords=SimpleNamespace(data=[]),
        )

        result = service.update_segment(dataset_id, document.id, segment.id, req, account)

        assert result is segment
        assert updates[0][0] is segment
        assert updates[0][1]["hash"] == "new-hash"
        assert updates[1][0] is document
        assert updates[1][1]["character_count"] == 12
        assert updates[1][1]["token_count"] == 8
        assert keyword_calls == ["delete", "add"]
        assert vector_calls[0]["uuid"] == str(segment.node_id)

    def test_create_segment_should_raise_when_document_not_found(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        req = SimpleNamespace(content=SimpleNamespace(data="片段"), keywords=SimpleNamespace(data=[]))
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)

        with pytest.raises(NotFoundException):
            service.create_segment(uuid4(), uuid4(), req, account)

    def test_create_segment_should_raise_when_document_status_not_completed(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document_id = uuid4()
        document = SimpleNamespace(
            id=document_id,
            account_id=account.id,
            dataset_id=dataset_id,
            status=DocumentStatus.PARSING.value,
        )
        service = self._build_service()
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: document)
        req = SimpleNamespace(content=SimpleNamespace(data="片段"), keywords=SimpleNamespace(data=[]))

        with pytest.raises(FailException):
            service.create_segment(dataset_id, document_id, req, account)

    def test_create_segment_should_create_vector_keyword_and_update_document(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document = SimpleNamespace(
            id=uuid4(),
            account_id=account.id,
            dataset_id=dataset_id,
            status=DocumentStatus.COMPLETED.value,
            enabled=True,
        )

        class _Session:
            def __init__(self):
                self.calls = 0

            def query(self, *_args, **_kwargs):
                self.calls += 1
                if self.calls == 1:
                    return _QueryStub(scalar_result=3)
                if self.calls == 2:
                    return _QueryStub(first_result=(18, 9))
                raise AssertionError("unexpected query count")

        vector_calls = []
        keyword_calls = []
        service = SegmentService(
            db=SimpleNamespace(session=_Session()),
            redis_client=_RedisStub(),
            jieba_service=SimpleNamespace(extract_keywords=lambda _content, _k: ["kw1", "kw2"]),
            embeddings_service=SimpleNamespace(
                calculate_token_count=lambda _content: 4,
                embeddings=SimpleNamespace(embed_query=lambda _q: [0.1]),
            ),
            keyword_table_service=SimpleNamespace(
                add_keyword_table_from_ids=lambda dataset_id, segment_ids: keyword_calls.append((dataset_id, segment_ids))
            ),
            vector_database_service=SimpleNamespace(
                vector_store=SimpleNamespace(
                    add_documents=lambda documents, ids: vector_calls.append((documents, ids))
                )
            ),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: document)
        create_calls = []

        def _fake_create(_model, **kwargs):
            create_calls.append(kwargs)
            return SimpleNamespace(id=uuid4(), node_id=kwargs["node_id"])

        monkeypatch.setattr(service, "create", _fake_create)
        update_calls = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: update_calls.append((target, kwargs)) or target,
        )
        req = SimpleNamespace(content=SimpleNamespace(data="new segment"), keywords=SimpleNamespace(data=[]))

        service.create_segment(dataset_id, document.id, req, account)

        assert create_calls[0]["position"] == 4
        assert create_calls[0]["keywords"] == ["kw1", "kw2"]
        assert vector_calls[0][1][0] == str(create_calls[0]["node_id"])
        assert update_calls[0][0] is document
        assert update_calls[0][1]["character_count"] == 18
        assert update_calls[0][1]["token_count"] == 9
        assert keyword_calls and keyword_calls[0][0] == dataset_id

    def test_create_segment_should_skip_jieba_and_keyword_table_when_keywords_given_and_document_disabled(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document = SimpleNamespace(
            id=uuid4(),
            account_id=account.id,
            dataset_id=dataset_id,
            status=DocumentStatus.COMPLETED.value,
            enabled=False,
        )

        class _Session:
            def __init__(self):
                self.calls = 0

            def query(self, *_args, **_kwargs):
                self.calls += 1
                if self.calls == 1:
                    return _QueryStub(scalar_result=0)
                if self.calls == 2:
                    return _QueryStub(first_result=(5, 2))
                raise AssertionError("unexpected query count")

        keyword_calls = []
        service = SegmentService(
            db=SimpleNamespace(session=_Session()),
            redis_client=_RedisStub(),
            jieba_service=SimpleNamespace(
                extract_keywords=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("jieba should not be called"))
            ),
            embeddings_service=SimpleNamespace(
                calculate_token_count=lambda _content: 2,
                embeddings=SimpleNamespace(embed_query=lambda _q: [0.1]),
            ),
            keyword_table_service=SimpleNamespace(
                add_keyword_table_from_ids=lambda *_args, **_kwargs: keyword_calls.append("add")
            ),
            vector_database_service=SimpleNamespace(
                vector_store=SimpleNamespace(add_documents=lambda *_args, **_kwargs: None)
            ),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: document)
        monkeypatch.setattr(
            service,
            "create",
            lambda _model, **kwargs: SimpleNamespace(id=uuid4(), node_id=kwargs["node_id"]),
        )
        monkeypatch.setattr(service, "update", lambda *_args, **_kwargs: None)
        req = SimpleNamespace(content=SimpleNamespace(data="segment"), keywords=SimpleNamespace(data=["given-kw"]))

        service.create_segment(dataset_id, document.id, req, account)

        assert keyword_calls == []

    def test_create_segment_should_raise_fail_when_segment_not_created_and_exception_occurs(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document = SimpleNamespace(
            id=uuid4(),
            account_id=account.id,
            dataset_id=dataset_id,
            status=DocumentStatus.COMPLETED.value,
            enabled=True,
        )
        service = SegmentService(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda *_args, **_kwargs: _QueryStub(scalar_result=0))),
            redis_client=_RedisStub(),
            jieba_service=SimpleNamespace(extract_keywords=lambda _content, _k: ["kw"]),
            embeddings_service=SimpleNamespace(
                calculate_token_count=lambda _content: 2,
                embeddings=SimpleNamespace(embed_query=lambda _q: [0.1]),
            ),
            keyword_table_service=SimpleNamespace(add_keyword_table_from_ids=lambda *_args, **_kwargs: None),
            vector_database_service=SimpleNamespace(
                vector_store=SimpleNamespace(add_documents=lambda *_args, **_kwargs: None)
            ),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: document)
        monkeypatch.setattr(
            service,
            "create",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("create failed")),
        )
        update_calls = []
        monkeypatch.setattr(service, "update", lambda target, **kwargs: update_calls.append((target, kwargs)) or target)
        req = SimpleNamespace(content=SimpleNamespace(data="segment"), keywords=SimpleNamespace(data=[]))

        with pytest.raises(FailException):
            service.create_segment(dataset_id, document.id, req, account)

        # segment 尚未创建，不应进入 segment 错误状态更新分支。
        assert update_calls == []

    def test_create_segment_should_mark_segment_error_when_vector_write_failed(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document = SimpleNamespace(
            id=uuid4(),
            account_id=account.id,
            dataset_id=dataset_id,
            status=DocumentStatus.COMPLETED.value,
            enabled=True,
        )
        segment = SimpleNamespace(id=uuid4(), node_id=uuid4())
        service = SegmentService(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda *_args, **_kwargs: _QueryStub(scalar_result=0))),
            redis_client=_RedisStub(),
            jieba_service=SimpleNamespace(extract_keywords=lambda _content, _k: ["kw"]),
            embeddings_service=SimpleNamespace(
                calculate_token_count=lambda _content: 3,
                embeddings=SimpleNamespace(embed_query=lambda _q: [0.1]),
            ),
            keyword_table_service=SimpleNamespace(add_keyword_table_from_ids=lambda *_args, **_kwargs: None),
            vector_database_service=SimpleNamespace(
                vector_store=SimpleNamespace(
                    add_documents=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("vector boom"))
                )
            ),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: document)
        monkeypatch.setattr(service, "create", lambda *_args, **_kwargs: segment)
        update_calls = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: update_calls.append((target, kwargs)) or target,
        )
        req = SimpleNamespace(content=SimpleNamespace(data="segment"), keywords=SimpleNamespace(data=[]))

        with pytest.raises(FailException):
            service.create_segment(dataset_id, document.id, req, account)

        assert update_calls[-1][0] is segment
        assert update_calls[-1][1]["status"] == SegmentStatus.ERROR.value
        assert update_calls[-1][1]["enabled"] is False
        assert "vector boom" in update_calls[-1][1]["error"]

    def test_update_segment_should_skip_document_and_vector_update_when_content_not_changed(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document_id = uuid4()
        segment = SimpleNamespace(
            id=uuid4(),
            account_id=account.id,
            dataset_id=dataset_id,
            document_id=document_id,
            status=SegmentStatus.COMPLETED.value,
            hash="same-hash",
            node_id=uuid4(),
            document=SimpleNamespace(id=document_id),
        )
        keyword_calls = []
        vector_calls = []
        service = SegmentService(
            db=SimpleNamespace(session=SimpleNamespace()),
            redis_client=_RedisStub(),
            jieba_service=SimpleNamespace(extract_keywords=lambda _content, _k: ["kw"]),
            embeddings_service=SimpleNamespace(
                calculate_token_count=lambda _content: 5,
                embeddings=SimpleNamespace(embed_query=lambda _q: [0.1]),
            ),
            keyword_table_service=SimpleNamespace(
                delete_keyword_table_from_ids=lambda *_args, **_kwargs: keyword_calls.append("delete"),
                add_keyword_table_from_ids=lambda *_args, **_kwargs: keyword_calls.append("add"),
            ),
            vector_database_service=SimpleNamespace(
                collection=SimpleNamespace(data=SimpleNamespace(update=lambda **kwargs: vector_calls.append(kwargs)))
            ),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: segment)
        monkeypatch.setattr("internal.service.segment_service.generate_text_hash", lambda _text: "same-hash")
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )
        req = SimpleNamespace(content=SimpleNamespace(data="unchanged"), keywords=SimpleNamespace(data=[]))

        service.update_segment(dataset_id, document_id, segment.id, req, account)

        assert len(updates) == 1
        assert updates[0][0] is segment
        assert keyword_calls == ["delete", "add"]
        assert vector_calls == []

    def test_update_segment_should_not_call_jieba_when_keywords_given(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document_id = uuid4()
        segment = SimpleNamespace(
            id=uuid4(),
            account_id=account.id,
            dataset_id=dataset_id,
            document_id=document_id,
            status=SegmentStatus.COMPLETED.value,
            hash="same-hash",
            node_id=uuid4(),
            document=SimpleNamespace(id=document_id),
        )
        service = SegmentService(
            db=SimpleNamespace(session=SimpleNamespace()),
            redis_client=_RedisStub(),
            jieba_service=SimpleNamespace(
                extract_keywords=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("jieba should not be called"))
            ),
            embeddings_service=SimpleNamespace(
                calculate_token_count=lambda _content: 5,
                embeddings=SimpleNamespace(embed_query=lambda _q: [0.1]),
            ),
            keyword_table_service=SimpleNamespace(
                delete_keyword_table_from_ids=lambda *_args, **_kwargs: None,
                add_keyword_table_from_ids=lambda *_args, **_kwargs: None,
            ),
            vector_database_service=SimpleNamespace(
                collection=SimpleNamespace(data=SimpleNamespace(update=lambda **_kwargs: None))
            ),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: segment)
        monkeypatch.setattr("internal.service.segment_service.generate_text_hash", lambda _text: "same-hash")
        monkeypatch.setattr(service, "update", lambda *_args, **_kwargs: None)
        req = SimpleNamespace(content=SimpleNamespace(data="unchanged"), keywords=SimpleNamespace(data=["provided"]))

        service.update_segment(dataset_id, document_id, segment.id, req, account)

    def test_update_segment_should_raise_fail_exception_when_update_failed(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document_id = uuid4()
        segment = SimpleNamespace(
            id=uuid4(),
            account_id=account.id,
            dataset_id=dataset_id,
            document_id=document_id,
            status=SegmentStatus.COMPLETED.value,
            hash="old-hash",
            node_id=uuid4(),
            document=SimpleNamespace(id=document_id),
        )
        service = self._build_service()
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: segment)
        monkeypatch.setattr(
            service,
            "update",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("db-update-error")),
        )
        req = SimpleNamespace(content=SimpleNamespace(data="new"), keywords=SimpleNamespace(data=[]))

        with pytest.raises(FailException):
            service.update_segment(dataset_id, document_id, segment.id, req, account)

    def test_update_segment_should_raise_when_segment_not_found(self, monkeypatch):
        service = self._build_service()
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)
        req = SimpleNamespace(content=SimpleNamespace(data="new"), keywords=SimpleNamespace(data=[]))

        with pytest.raises(NotFoundException):
            service.update_segment(uuid4(), uuid4(), uuid4(), req, SimpleNamespace(id=uuid4()))

    def test_update_segment_should_raise_when_segment_status_invalid(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document_id = uuid4()
        segment = SimpleNamespace(
            id=uuid4(),
            account_id=account.id,
            dataset_id=dataset_id,
            document_id=document_id,
            status=SegmentStatus.ERROR.value,
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: segment)
        req = SimpleNamespace(content=SimpleNamespace(data="new"), keywords=SimpleNamespace(data=[]))

        with pytest.raises(FailException):
            service.update_segment(dataset_id, document_id, segment.id, req, account)

    def test_get_segment_should_raise_when_segment_not_found(self, monkeypatch):
        service = self._build_service()
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)

        with pytest.raises(NotFoundException):
            service.get_segment(uuid4(), uuid4(), uuid4(), SimpleNamespace(id=uuid4()))

    def test_get_segments_with_page_should_raise_when_document_not_found(self, monkeypatch):
        service = self._build_service()
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)
        req = SimpleNamespace(search_word=SimpleNamespace(data=None))

        with pytest.raises(NotFoundException):
            service.get_segments_with_page(uuid4(), uuid4(), req, SimpleNamespace(id=uuid4()))

    def test_get_segments_with_page_should_build_default_filter_when_search_word_empty(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document_id = uuid4()
        service = self._build_service()
        monkeypatch.setattr(
            service,
            "get",
            lambda model, _id: SimpleNamespace(id=document_id, dataset_id=dataset_id, account_id=account.id)
            if model is Document
            else None,
        )

        class _Query:
            def __init__(self):
                self.filter_calls = []

            def filter(self, *args, **_kwargs):
                self.filter_calls.append(args)
                return self

            def order_by(self, *_args, **_kwargs):
                return self

        query = _Query()
        service.db = SimpleNamespace(session=SimpleNamespace(query=lambda _model: query))

        class _Paginator:
            def __init__(self, db, req):
                pass

            def paginate(self, query_obj):
                assert query_obj is query
                return ["segment-1"]

        monkeypatch.setattr("internal.service.segment_service.Paginator", _Paginator)
        req = SimpleNamespace(search_word=SimpleNamespace(data=""))

        segments, _paginator = service.get_segments_with_page(dataset_id, document_id, req, account)

        assert segments == ["segment-1"]
        assert len(query.filter_calls[0]) == 1

    def test_update_segment_enabled_should_raise_when_segment_not_found(self, monkeypatch):
        service = self._build_service()
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)

        with pytest.raises(NotFoundException):
            service.update_segment_enabled(uuid4(), uuid4(), uuid4(), True, SimpleNamespace(id=uuid4()))

    def test_update_segment_enabled_should_raise_when_segment_status_invalid(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document_id = uuid4()
        segment = SimpleNamespace(
            id=uuid4(),
            account_id=account.id,
            dataset_id=dataset_id,
            document_id=document_id,
            status=SegmentStatus.ERROR.value,
            enabled=False,
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: segment)

        with pytest.raises(FailException):
            service.update_segment_enabled(dataset_id, document_id, segment.id, True, account)

    def test_update_segment_enabled_should_raise_when_locked(self, monkeypatch):
        service = self._build_service()
        service.redis_client = _RedisStub(get_value="locked")
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document_id = uuid4()
        segment = SimpleNamespace(
            id=uuid4(),
            account_id=account.id,
            dataset_id=dataset_id,
            document_id=document_id,
            status=SegmentStatus.COMPLETED.value,
            enabled=False,
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: segment)

        with pytest.raises(FailException):
            service.update_segment_enabled(dataset_id, document_id, segment.id, True, account)

    def test_update_segment_enabled_should_enable_segment_and_add_keyword(self, monkeypatch):
        add_calls = []
        vector_calls = []
        service = self._build_service()
        service.redis_client = _RedisStub()
        service.keyword_table_service = SimpleNamespace(
            add_keyword_table_from_ids=lambda dataset_id, segment_ids: add_calls.append((dataset_id, segment_ids)),
            delete_keyword_table_from_ids=lambda *_args, **_kwargs: None,
        )
        service.vector_database_service = SimpleNamespace(
            collection=SimpleNamespace(data=SimpleNamespace(update=lambda **kwargs: vector_calls.append(kwargs)))
        )

        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document_id = uuid4()
        segment = SimpleNamespace(
            id=uuid4(),
            account_id=account.id,
            dataset_id=dataset_id,
            document_id=document_id,
            status=SegmentStatus.COMPLETED.value,
            enabled=False,
            node_id=uuid4(),
            document=SimpleNamespace(enabled=True),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: segment)
        update_calls = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: update_calls.append((target, kwargs)) or target,
        )

        service.update_segment_enabled(dataset_id, document_id, segment.id, True, account)

        assert update_calls[0][0] is segment
        assert update_calls[0][1]["enabled"] is True
        assert update_calls[0][1]["disabled_at"] is None
        assert add_calls == [(dataset_id, [segment.id])]
        assert vector_calls[0]["uuid"] == segment.node_id
        assert vector_calls[0]["properties"]["segment_enabled"] is True

    def test_update_segment_enabled_should_disable_segment_and_remove_keyword(self, monkeypatch):
        delete_calls = []
        vector_calls = []
        service = self._build_service()
        service.redis_client = _RedisStub()
        service.keyword_table_service = SimpleNamespace(
            add_keyword_table_from_ids=lambda *_args, **_kwargs: None,
            delete_keyword_table_from_ids=lambda dataset_id, segment_ids: delete_calls.append((dataset_id, segment_ids)),
        )
        service.vector_database_service = SimpleNamespace(
            collection=SimpleNamespace(data=SimpleNamespace(update=lambda **kwargs: vector_calls.append(kwargs)))
        )
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document_id = uuid4()
        segment = SimpleNamespace(
            id=uuid4(),
            account_id=account.id,
            dataset_id=dataset_id,
            document_id=document_id,
            status=SegmentStatus.COMPLETED.value,
            enabled=True,
            node_id=uuid4(),
            document=SimpleNamespace(enabled=True),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: segment)
        update_calls = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: update_calls.append((target, kwargs)) or target,
        )

        service.update_segment_enabled(dataset_id, document_id, segment.id, False, account)

        assert update_calls[0][1]["enabled"] is False
        assert update_calls[0][1]["disabled_at"] is not None
        assert delete_calls == [(dataset_id, [segment.id])]
        assert vector_calls[0]["properties"]["segment_enabled"] is False

    def test_update_segment_enabled_should_mark_segment_error_when_failed(self, monkeypatch):
        service = self._build_service()
        service.redis_client = _RedisStub()
        service.keyword_table_service = SimpleNamespace(
            add_keyword_table_from_ids=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("kw boom")),
            delete_keyword_table_from_ids=lambda *_args, **_kwargs: None,
        )
        service.vector_database_service = SimpleNamespace(
            collection=SimpleNamespace(data=SimpleNamespace(update=lambda **_kwargs: None))
        )
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document_id = uuid4()
        segment = SimpleNamespace(
            id=uuid4(),
            account_id=account.id,
            dataset_id=dataset_id,
            document_id=document_id,
            status=SegmentStatus.COMPLETED.value,
            enabled=False,
            node_id=uuid4(),
            document=SimpleNamespace(enabled=True),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: segment)
        update_calls = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: update_calls.append((target, kwargs)) or target,
        )

        with pytest.raises(FailException):
            service.update_segment_enabled(dataset_id, document_id, segment.id, True, account)

        assert update_calls[-1][0] is segment
        assert update_calls[-1][1]["status"] == SegmentStatus.ERROR.value
        assert update_calls[-1][1]["enabled"] is False
        assert "kw boom" in update_calls[-1][1]["error"]

    def test_delete_segment_should_raise_when_segment_status_not_deletable(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        document_id = uuid4()
        segment = SimpleNamespace(
            id=uuid4(),
            account_id=account.id,
            dataset_id=dataset_id,
            document_id=document_id,
            status=SegmentStatus.WAITING.value,
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: segment)

        with pytest.raises(FailException):
            service.delete_segment(dataset_id, document_id, segment.id, account)

    def test_delete_segment_should_raise_when_segment_not_found(self, monkeypatch):
        service = self._build_service()
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)

        with pytest.raises(NotFoundException):
            service.delete_segment(uuid4(), uuid4(), uuid4(), SimpleNamespace(id=uuid4()))

    def test_delete_segment_should_continue_when_vector_delete_failed(self, monkeypatch):
        document = SimpleNamespace(id=uuid4())
        segment = SimpleNamespace(
            id=uuid4(),
            account_id=uuid4(),
            dataset_id=uuid4(),
            document_id=uuid4(),
            node_id=uuid4(),
            status=SegmentStatus.COMPLETED.value,
            document=document,
        )

        query_stub = _QueryStub(first_result=(10, 5))
        service = SegmentService(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda *_args, **_kwargs: query_stub)),
            redis_client=_RedisStub(),
            jieba_service=SimpleNamespace(),
            embeddings_service=SimpleNamespace(
                embeddings=SimpleNamespace(embed_query=lambda _q: [0.1]),
                calculate_token_count=lambda _q: 1,
            ),
            keyword_table_service=SimpleNamespace(delete_keyword_table_from_ids=lambda *_args, **_kwargs: None),
            vector_database_service=SimpleNamespace(
                collection=SimpleNamespace(
                    data=SimpleNamespace(
                        delete_by_id=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("vector-delete-error"))
                    )
                )
            ),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: segment)
        monkeypatch.setattr(service, "delete", lambda *_args, **_kwargs: None)
        update_calls = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: update_calls.append((target, kwargs)) or target,
        )
        account = SimpleNamespace(id=segment.account_id)

        result = service.delete_segment(segment.dataset_id, segment.document_id, segment.id, account)

        assert result is segment
        assert update_calls[-1][0] is document
        assert update_calls[-1][1]["character_count"] == 10
        assert update_calls[-1][1]["token_count"] == 5
