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


class TestKeywordTableService:
    def _build_service(self, session):
        return KeywordTableService(
            db=SimpleNamespace(session=session),
            redis_client=_RedisStub(),
        )

    def test_get_keyword_table_from_dataset_id_should_create_when_missing(self, monkeypatch):
        dataset_id = uuid4()
        session = SimpleNamespace(query=lambda _model: _QueryStub(one_or_none_result=None))
        service = self._build_service(session)
        monkeypatch.setattr(
            service,
            "create",
            lambda _model, **kwargs: SimpleNamespace(dataset_id=kwargs["dataset_id"], keyword_table={}),
        )

        result = service.get_keyword_table_from_dataset_id(dataset_id)

        assert result.dataset_id == dataset_id
        assert result.keyword_table == {}

    def test_get_keyword_table_from_dataset_id_should_return_existing_record(self, monkeypatch):
        dataset_id = uuid4()
        existed = SimpleNamespace(dataset_id=dataset_id, keyword_table={"python": ["1"]})
        session = SimpleNamespace(query=lambda _model: _QueryStub(one_or_none_result=existed))
        service = self._build_service(session)
        monkeypatch.setattr(
            service,
            "create",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("create should not be called")),
        )

        result = service.get_keyword_table_from_dataset_id(dataset_id)

        assert result is existed

    def test_delete_keyword_table_from_ids_should_prune_empty_keywords(self, monkeypatch):
        dataset_id = uuid4()
        record = SimpleNamespace(keyword_table={"python": ["1", "2"], "redis": ["2"]})
        service = self._build_service(SimpleNamespace(query=lambda _model: _QueryStub()))
        monkeypatch.setattr(service, "get_keyword_table_from_dataset_id", lambda _id: record)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)),
        )

        service.delete_keyword_table_from_ids(dataset_id, ["2"])

        assert updates[0][1]["keyword_table"] == {"python": ["1"]}

    def test_delete_keyword_table_from_ids_should_keep_keywords_without_intersection(self, monkeypatch):
        dataset_id = uuid4()
        record = SimpleNamespace(keyword_table={"python": ["1"], "redis": ["2"]})
        service = self._build_service(SimpleNamespace(query=lambda _model: _QueryStub()))
        monkeypatch.setattr(service, "get_keyword_table_from_dataset_id", lambda _id: record)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)),
        )

        service.delete_keyword_table_from_ids(dataset_id, ["3"])

        assert updates[0][1]["keyword_table"] == {"python": ["1"], "redis": ["2"]}

    def test_add_keyword_table_from_ids_should_merge_new_segment_keywords(self, monkeypatch):
        dataset_id = uuid4()
        seg_id = uuid4()
        record = SimpleNamespace(keyword_table={"python": ["1"]})
        session = SimpleNamespace(query=lambda _model: _QueryStub(all_result=[(seg_id, ["python", "llm"])]))
        service = self._build_service(session)
        monkeypatch.setattr(service, "get_keyword_table_from_dataset_id", lambda _id: record)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)),
        )

        service.add_keyword_table_from_ids(dataset_id, [seg_id])

        table = updates[0][1]["keyword_table"]
        assert str(seg_id) in table["python"]
        assert table["llm"] == [str(seg_id)]
