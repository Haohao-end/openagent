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


class TestRetrievalService:
    def _build_service(self, db):
        return RetrievalService(
            db=db,
            jieba_service=SimpleNamespace(),
            vector_database_service=SimpleNamespace(vector_store="vector-store"),
        )

    def test_search_in_datasets_should_raise_when_no_available_dataset(self):
        service = self._build_service(SimpleNamespace(session=SimpleNamespace(query=lambda _model: _QueryStub(all_result=[]))))

        with pytest.raises(NotFoundException):
            service.search_in_datasets(
                dataset_ids=[uuid4()],
                query="hello",
                account_id=uuid4(),
            )

    def test_search_in_datasets_should_create_query_records_and_execute_hit_update(self, monkeypatch):
        account_id = uuid4()
        dataset_id = uuid4()
        segment_id = uuid4()
        datasets = [SimpleNamespace(id=dataset_id, account_id=account_id)]
        lc_docs = [
            SimpleNamespace(metadata={"dataset_id": dataset_id, "segment_id": segment_id, "score": 0.66}),
            SimpleNamespace(metadata={"dataset_id": dataset_id, "segment_id": segment_id, "score": 0.55}),
        ]

        class _Session:
            def __init__(self):
                self.executed = False

            def query(self, model):
                if model is Dataset:
                    return _QueryStub(all_result=datasets)
                return _QueryStub()

            def execute(self, _stmt):
                self.executed = True

        session = _Session()
        db = _DBStub(session)
        service = self._build_service(db)

        class _SemanticRetriever:
            def __init__(self, **_kwargs):
                pass

            def invoke(self, _query):
                return lc_docs

        class _FullTextRetriever:
            def __init__(self, **_kwargs):
                pass

            def invoke(self, _query):
                return []

        monkeypatch.setitem(
            sys.modules,
            "internal.core.retrievers",
            SimpleNamespace(
                SemanticRetriever=_SemanticRetriever,
                FullTextRetriever=_FullTextRetriever,
            ),
        )
        monkeypatch.setattr(
            "internal.service.retrieval_service.EnsembleRetriever",
            lambda retrievers, weights: SimpleNamespace(invoke=lambda _query: []),
        )

        create_calls = []
        monkeypatch.setattr(
            service,
            "create",
            lambda model, **kwargs: create_calls.append((model, kwargs)) or SimpleNamespace(**kwargs),
        )

        result = service.search_in_datasets(
            dataset_ids=[dataset_id],
            query="搜索语句",
            account_id=account_id,
            retrieval_strategy="semantic",
            k=2,
        )

        assert result == lc_docs[:2]
        assert len(create_calls) == 1
        assert create_calls[0][1]["dataset_id"] == str(dataset_id)
        assert session.executed is True

    def test_create_langchain_tool_from_search_should_return_fallback_message(self, monkeypatch):
        service = self._build_service(SimpleNamespace(session=SimpleNamespace()))
        monkeypatch.setattr(service, "search_in_datasets", lambda **_kwargs: [])
        app = SimpleNamespace(
            app_context=lambda: _null_context(),
        )

        tool = service.create_langchain_tool_from_search(app, [uuid4()], uuid4())
        result = tool.invoke({"query": "not-found"})

        assert result == "知识库内没有检索到对应内容"

    def test_search_in_datasets_should_use_full_text_strategy(self, monkeypatch):
        account_id = uuid4()
        dataset_id = uuid4()
        segment_id = uuid4()
        datasets = [SimpleNamespace(id=dataset_id, account_id=account_id)]
        full_text_docs = [
            SimpleNamespace(metadata={"dataset_id": dataset_id, "segment_id": segment_id, "score": 0.66}),
        ]

        class _Session:
            def __init__(self):
                self.executed = False

            def query(self, model):
                if model is Dataset:
                    return _QueryStub(all_result=datasets)
                return _QueryStub()

            def execute(self, _stmt):
                self.executed = True

        session = _Session()
        service = self._build_service(_DBStub(session))

        class _SemanticRetriever:
            def __init__(self, **_kwargs):
                pass

            def invoke(self, _query):
                return []

        class _FullTextRetriever:
            def __init__(self, **_kwargs):
                pass

            def invoke(self, _query):
                return full_text_docs

        monkeypatch.setitem(
            sys.modules,
            "internal.core.retrievers",
            SimpleNamespace(
                SemanticRetriever=_SemanticRetriever,
                FullTextRetriever=_FullTextRetriever,
            ),
        )
        monkeypatch.setattr(
            "internal.service.retrieval_service.EnsembleRetriever",
            lambda retrievers, weights: SimpleNamespace(invoke=lambda _query: []),
        )
        monkeypatch.setattr(service, "create", lambda *_args, **_kwargs: SimpleNamespace())

        result = service.search_in_datasets(
            dataset_ids=[dataset_id],
            query="全文检索",
            account_id=account_id,
            retrieval_strategy="full_text",
            k=1,
        )

        assert result == full_text_docs
        assert session.executed is True

    def test_search_in_datasets_should_use_hybrid_strategy(self, monkeypatch):
        account_id = uuid4()
        dataset_id = uuid4()
        segment_id = uuid4()
        datasets = [SimpleNamespace(id=dataset_id, account_id=account_id)]
        hybrid_docs = [
            SimpleNamespace(metadata={"dataset_id": dataset_id, "segment_id": segment_id, "score": 0.77}),
        ]

        class _Session:
            def query(self, model):
                if model is Dataset:
                    return _QueryStub(all_result=datasets)
                return _QueryStub()

            def execute(self, _stmt):
                return None

        service = self._build_service(_DBStub(_Session()))

        class _SemanticRetriever:
            def __init__(self, **_kwargs):
                pass

            def invoke(self, _query):
                return []

        class _FullTextRetriever:
            def __init__(self, **_kwargs):
                pass

            def invoke(self, _query):
                return []

        monkeypatch.setitem(
            sys.modules,
            "internal.core.retrievers",
            SimpleNamespace(
                SemanticRetriever=_SemanticRetriever,
                FullTextRetriever=_FullTextRetriever,
            ),
        )
        monkeypatch.setattr(
            "internal.service.retrieval_service.EnsembleRetriever",
            lambda retrievers, weights: SimpleNamespace(invoke=lambda _query: hybrid_docs),
        )
        monkeypatch.setattr(service, "create", lambda *_args, **_kwargs: SimpleNamespace())

        result = service.search_in_datasets(
            dataset_ids=[dataset_id],
            query="混合检索",
            account_id=account_id,
            retrieval_strategy="hybrid",
            k=1,
        )

        assert result == hybrid_docs

    def test_create_langchain_tool_from_search_should_combine_documents_when_hit(self, monkeypatch):
        service = self._build_service(SimpleNamespace(session=SimpleNamespace()))
        documents = [LCDocument(page_content="答案内容")]
        monkeypatch.setattr(service, "search_in_datasets", lambda **_kwargs: documents)
        monkeypatch.setattr(
            "internal.service.retrieval_service.combine_documents",
            lambda docs: f"combined:{len(docs)}",
        )
        app = SimpleNamespace(app_context=lambda: _null_context())

        tool = service.create_langchain_tool_from_search(app, [uuid4()], uuid4())
        result = tool.invoke({"query": "找到结果"})

        assert result == "combined:1"
