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


class TestDatasetService:
    def test_create_dataset_should_fill_default_description_when_empty(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        session = SimpleNamespace(query=lambda _model: _QueryStub(one_or_none_result=None))
        service = _new_dataset_service(
            db=SimpleNamespace(session=session),
            retrieval_service=SimpleNamespace(),
        )
        req = SimpleNamespace(
            name=SimpleNamespace(data="用户画像库"),
            icon=SimpleNamespace(data="https://a.com/icon.png"),
            description=SimpleNamespace(data=" "),
        )
        create_calls = []
        monkeypatch.setattr(
            service,
            "create",
            lambda model, **kwargs: create_calls.append((model, kwargs)) or SimpleNamespace(**kwargs),
        )

        dataset = service.create_dataset(req, account)

        assert dataset.name == "用户画像库"
        assert "用户画像库" in create_calls[0][1]["description"]

    def test_create_dataset_should_keep_description_when_provided(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        session = SimpleNamespace(query=lambda _model: _QueryStub(one_or_none_result=None))
        service = _new_dataset_service(
            db=SimpleNamespace(session=session),
            retrieval_service=SimpleNamespace(),
        )
        req = SimpleNamespace(
            name=SimpleNamespace(data="运营知识库"),
            icon=SimpleNamespace(data="https://a.com/icon.png"),
            description=SimpleNamespace(data="明确描述"),
        )
        create_calls = []
        monkeypatch.setattr(
            service,
            "create",
            lambda model, **kwargs: create_calls.append((model, kwargs)) or SimpleNamespace(**kwargs),
        )

        dataset = service.create_dataset(req, account)

        assert dataset.description == "明确描述"
        assert create_calls[0][1]["description"] == "明确描述"

    def test_create_dataset_should_raise_when_name_duplicated(self):
        account = SimpleNamespace(id=uuid4())
        duplicated = SimpleNamespace(id=uuid4(), account_id=account.id)
        session = SimpleNamespace(query=lambda _model: _QueryStub(one_or_none_result=duplicated))
        service = _new_dataset_service(
            db=SimpleNamespace(session=session),
            retrieval_service=SimpleNamespace(),
        )
        req = SimpleNamespace(
            name=SimpleNamespace(data="重复知识库"),
            icon=SimpleNamespace(data="https://a.com/icon.png"),
            description=SimpleNamespace(data="desc"),
        )

        with pytest.raises(ValidateErrorException):
            service.create_dataset(req, account)

    def test_get_dataset_should_raise_when_not_found(self, monkeypatch):
        service = _new_dataset_service(db=SimpleNamespace(session=SimpleNamespace()), retrieval_service=SimpleNamespace())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)

        with pytest.raises(NotFoundException):
            service.get_dataset(uuid4(), SimpleNamespace(id=uuid4()))

    def test_get_dataset_queries_should_return_latest_records(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        expected_queries = [SimpleNamespace(query="q1"), SimpleNamespace(query="q2")]
        session = SimpleNamespace(query=lambda _model: _QueryStub(all_result=expected_queries))
        service = _new_dataset_service(db=SimpleNamespace(session=session), retrieval_service=SimpleNamespace())
        monkeypatch.setattr(
            service,
            "get",
            lambda model, _id: SimpleNamespace(id=dataset_id, account_id=account.id) if model is Dataset else None,
        )

        result = service.get_dataset_queries(dataset_id, account)

        assert result == expected_queries

    def test_get_dataset_queries_should_raise_when_dataset_not_accessible(self, monkeypatch):
        service = _new_dataset_service(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda _model: _QueryStub(all_result=[]))),
            retrieval_service=SimpleNamespace(),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)

        with pytest.raises(NotFoundException):
            service.get_dataset_queries(uuid4(), SimpleNamespace(id=uuid4()))

    def test_get_dataset_should_return_when_owned(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset = SimpleNamespace(id=uuid4(), account_id=account.id)
        service = _new_dataset_service(db=SimpleNamespace(session=SimpleNamespace()), retrieval_service=SimpleNamespace())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: dataset)

        result = service.get_dataset(dataset.id, account)

        assert result is dataset

    def test_update_dataset_should_fill_default_description_and_delegate_update(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        dataset = SimpleNamespace(id=dataset_id, account_id=account.id)
        session = SimpleNamespace(query=lambda _model: _QueryStub(one_or_none_result=None))
        service = _new_dataset_service(db=SimpleNamespace(session=session), retrieval_service=SimpleNamespace())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: dataset)
        req = SimpleNamespace(
            name=SimpleNamespace(data="新知识库"),
            icon=SimpleNamespace(data="https://a.com/new.png"),
            description=SimpleNamespace(data=" "),
        )
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.update_dataset(dataset_id, req, account)

        assert result is dataset
        assert updates[0][0] is dataset
        assert updates[0][1]["name"] == "新知识库"
        assert "新知识库" in updates[0][1]["description"]

    def test_update_dataset_should_keep_description_when_provided(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        dataset = SimpleNamespace(id=dataset_id, account_id=account.id)
        session = SimpleNamespace(query=lambda _model: _QueryStub(one_or_none_result=None))
        service = _new_dataset_service(db=SimpleNamespace(session=session), retrieval_service=SimpleNamespace())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: dataset)
        req = SimpleNamespace(
            name=SimpleNamespace(data="新知识库"),
            icon=SimpleNamespace(data="https://a.com/new.png"),
            description=SimpleNamespace(data="保留描述"),
        )
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.update_dataset(dataset_id, req, account)

        assert result is dataset
        assert updates[0][1]["description"] == "保留描述"

    def test_update_dataset_should_raise_when_dataset_not_accessible(self, monkeypatch):
        service = _new_dataset_service(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda _model: _QueryStub(one_or_none_result=None))),
            retrieval_service=SimpleNamespace(),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)
        req = SimpleNamespace(
            name=SimpleNamespace(data="新名称"),
            icon=SimpleNamespace(data="https://a.com/new.png"),
            description=SimpleNamespace(data="desc"),
        )

        with pytest.raises(NotFoundException):
            service.update_dataset(uuid4(), req, SimpleNamespace(id=uuid4()))

    def test_update_dataset_should_raise_when_name_duplicated(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset = SimpleNamespace(id=uuid4(), account_id=account.id)
        duplicated = SimpleNamespace(id=uuid4(), account_id=account.id)
        session = SimpleNamespace(query=lambda _model: _QueryStub(one_or_none_result=duplicated))
        service = _new_dataset_service(db=SimpleNamespace(session=session), retrieval_service=SimpleNamespace())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: dataset)
        req = SimpleNamespace(
            name=SimpleNamespace(data="重复名"),
            icon=SimpleNamespace(data="https://a.com/new.png"),
            description=SimpleNamespace(data="desc"),
        )

        with pytest.raises(ValidateErrorException):
            service.update_dataset(dataset.id, req, account)

    def test_get_datasets_with_page_should_use_paginator(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        service = _new_dataset_service(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda _model: _QueryStub(all_result=[]))),
            retrieval_service=SimpleNamespace(),
        )
        captures = {}

        class _Paginator:
            def __init__(self, db, req):
                captures["db"] = db
                captures["req"] = req

            def paginate(self, query):
                captures["query"] = query
                return ["dataset-1"]

        monkeypatch.setattr("internal.service.dataset_service.Paginator", _Paginator)
        req = SimpleNamespace(
            current_page=SimpleNamespace(data=1),
            page_size=SimpleNamespace(data=20),
            search_word=SimpleNamespace(data="知识"),
        )

        datasets, paginator = service.get_datasets_with_page(req, account)

        assert datasets == ["dataset-1"]
        assert captures["req"] is req
        assert captures["db"] is service.db
        assert captures["query"] is not None
        assert isinstance(paginator, _Paginator)

    def test_get_datasets_with_page_should_build_default_filter_when_search_word_empty(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())

        class _Query:
            def __init__(self):
                self.filter_calls = []

            def filter(self, *args, **_kwargs):
                self.filter_calls.append(args)
                return self

            def order_by(self, *_args, **_kwargs):
                return self

        query = _Query()
        service = _new_dataset_service(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda _model: query)),
            retrieval_service=SimpleNamespace(),
        )

        class _Paginator:
            def __init__(self, db, req):
                pass

            def paginate(self, query_obj):
                assert query_obj is query
                return ["dataset-1"]

        monkeypatch.setattr("internal.service.dataset_service.Paginator", _Paginator)
        req = SimpleNamespace(
            current_page=SimpleNamespace(data=1),
            page_size=SimpleNamespace(data=20),
            search_word=SimpleNamespace(data=""),
        )

        datasets, _paginator = service.get_datasets_with_page(req, account)

        assert datasets == ["dataset-1"]
        assert len(query.filter_calls[0]) == 1

    def test_hit_should_keep_retrieval_order_and_attach_scores(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        segment_a_id = uuid4()
        segment_b_id = uuid4()
        segment_a = SimpleNamespace(
            id=segment_a_id,
            dataset_id=dataset_id,
            position=1,
            content="A",
            keywords=["a"],
            character_count=1,
            token_count=1,
            hit_count=0,
            enabled=True,
            disabled_at=None,
            status="completed",
            error="",
            updated_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
            document=SimpleNamespace(
                id=uuid4(),
                name="doc-a",
                upload_file=SimpleNamespace(extension="txt", mime_type="text/plain"),
            ),
        )
        segment_b = SimpleNamespace(
            id=segment_b_id,
            dataset_id=dataset_id,
            position=2,
            content="B",
            keywords=["b"],
            character_count=1,
            token_count=1,
            hit_count=0,
            enabled=True,
            disabled_at=None,
            status="completed",
            error="",
            updated_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
            document=SimpleNamespace(
                id=uuid4(),
                name="doc-b",
                upload_file=SimpleNamespace(extension="md", mime_type="text/markdown"),
            ),
        )
        lc_documents = [
            SimpleNamespace(metadata={"segment_id": segment_b_id, "score": 0.91}),
            SimpleNamespace(metadata={"segment_id": segment_a_id, "score": 0.77}),
        ]

        session = SimpleNamespace(query=lambda model: _QueryStub(all_result=[segment_a, segment_b]) if model is Segment else _QueryStub())
        service = _new_dataset_service(
            db=SimpleNamespace(session=session),
            retrieval_service=SimpleNamespace(search_in_datasets=lambda **_kwargs: lc_documents),
        )
        monkeypatch.setattr(
            service,
            "get",
            lambda *_args, **_kwargs: SimpleNamespace(id=dataset_id, account_id=account.id),
        )

        result = service.hit(
            dataset_id,
            SimpleNamespace(data={"query": "hello", "retrieval_strategy": "semantic", "k": 2, "score": 0}),
            account,
        )

        assert [item["id"] for item in result] == [segment_b_id, segment_a_id]
        assert result[0]["score"] == 0.91
        assert result[1]["score"] == 0.77

    def test_hit_should_raise_when_dataset_not_accessible(self, monkeypatch):
        service = _new_dataset_service(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda _model: _QueryStub(all_result=[]))),
            retrieval_service=SimpleNamespace(),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)

        with pytest.raises(NotFoundException):
            service.hit(
                uuid4(),
                SimpleNamespace(data={"query": "hello", "retrieval_strategy": "semantic", "k": 2, "score": 0}),
                SimpleNamespace(id=uuid4()),
            )

    def test_delete_dataset_should_raise_fail_exception_when_delete_failed(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset = SimpleNamespace(id=uuid4(), account_id=account.id)
        service = _new_dataset_service(
            db=SimpleNamespace(session=SimpleNamespace(), auto_commit=lambda: _null_context()),
            retrieval_service=SimpleNamespace(),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: dataset)
        monkeypatch.setattr(
            service,
            "delete",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("db-error")),
        )

        with pytest.raises(FailException):
            service.delete_dataset(dataset.id, account)

    def test_delete_dataset_should_raise_when_dataset_not_accessible(self, monkeypatch):
        service = _new_dataset_service(
            db=SimpleNamespace(session=SimpleNamespace(), auto_commit=lambda: _null_context()),
            retrieval_service=SimpleNamespace(),
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)

        with pytest.raises(NotFoundException):
            service.delete_dataset(uuid4(), SimpleNamespace(id=uuid4()))

    def test_delete_dataset_should_delete_join_records_and_dispatch_async_task(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset_id = uuid4()
        dataset = SimpleNamespace(id=dataset_id, account_id=account.id)
        join_query = _QueryStub()
        db = _DBStub(
            SimpleNamespace(
                query=lambda model: join_query if model is AppDatasetJoin else _QueryStub(),
            )
        )
        service = _new_dataset_service(db=db, retrieval_service=SimpleNamespace())
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: dataset)
        deleted = []
        monkeypatch.setattr(service, "delete", lambda target: deleted.append(target))
        delay_calls = []
        monkeypatch.setattr(
            "internal.service.dataset_service.delete_dataset.delay",
            lambda _dataset_id: delay_calls.append(_dataset_id),
        )

        service.delete_dataset(dataset_id, account)

        assert deleted == [dataset]
        assert join_query.deleted is True
        assert delay_calls == [dataset_id]

    def test_regenerate_icon_should_update_dataset_icon(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset = SimpleNamespace(id=uuid4(), name="客服知识库", description="desc", icon="old-icon")
        service = _new_dataset_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            retrieval_service=SimpleNamespace(),
            icon_generator_service=SimpleNamespace(
                generate_icon=lambda name, description: f"https://icon/{name}/{description}"
            ),
        )
        monkeypatch.setattr(service, "get_dataset", lambda *_args, **_kwargs: dataset)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        icon_url = service.regenerate_icon(dataset.id, account)

        assert icon_url == "https://icon/客服知识库/desc"
        assert updates == [(dataset, {"icon": icon_url})]

    def test_regenerate_icon_should_raise_fail_exception_when_generator_failed(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        dataset = SimpleNamespace(id=uuid4(), name="客服知识库", description="desc")
        service = _new_dataset_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            retrieval_service=SimpleNamespace(),
            icon_generator_service=SimpleNamespace(
                generate_icon=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("icon-failed"))
            ),
        )
        monkeypatch.setattr(service, "get_dataset", lambda *_args, **_kwargs: dataset)

        with pytest.raises(FailException):
            service.regenerate_icon(dataset.id, account)

    def test_generate_icon_preview_should_return_generated_icon(self):
        service = _new_dataset_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            retrieval_service=SimpleNamespace(),
            icon_generator_service=SimpleNamespace(
                generate_icon=lambda name, description: f"https://preview/{name}/{description}"
            ),
        )

        icon_url = service.generate_icon_preview("dataset-preview", "")

        assert icon_url == "https://preview/dataset-preview/"

    def test_generate_icon_preview_should_raise_fail_exception_when_generator_failed(self):
        service = _new_dataset_service(
            db=SimpleNamespace(session=SimpleNamespace()),
            retrieval_service=SimpleNamespace(),
            icon_generator_service=SimpleNamespace(
                generate_icon=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("preview-failed"))
            ),
        )

        with pytest.raises(FailException):
            service.generate_icon_preview("dataset-preview", "desc")
