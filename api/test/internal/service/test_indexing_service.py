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


class TestIndexingService:
    def _build_service(self, db=None):
        return IndexingService(
            db=db or SimpleNamespace(session=SimpleNamespace()),
            file_extractor=SimpleNamespace(),
            process_rule_service=SimpleNamespace(),
            embeddings_service=SimpleNamespace(calculate_token_count=lambda _text: 1),
            jieba_service=SimpleNamespace(extract_keywords=lambda _text, _k: ["kw"]),
            keyword_table_service=SimpleNamespace(
                delete_keyword_table_from_ids=lambda *_args, **_kwargs: None,
                add_keyword_table_from_ids=lambda *_args, **_kwargs: None,
                get_keyword_table_from_dataset_id=lambda _id: SimpleNamespace(keyword_table={}),
            ),
            vector_database_service=SimpleNamespace(
                vector_store=SimpleNamespace(add_documents=lambda **_kwargs: None),
                collection=SimpleNamespace(
                    data=SimpleNamespace(
                        update=lambda **_kwargs: None,
                        delete_many=lambda **_kwargs: None,
                    )
                ),
            ),
            redis_client=_RedisStub(),
        )

    def test_clean_extra_text_should_remove_control_characters(self):
        service = self._build_service()

        result = service._clean_extra_text("hello\x00<|world|>\uFFFE")

        assert "\x00" not in result
        assert "\uFFFE" not in result
        assert "<world>" in result

    def test_update_document_enabled_should_raise_when_document_not_found(self, monkeypatch):
        service = self._build_service()
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)

        with pytest.raises(NotFoundException):
            service.update_document_enabled(uuid4())

    def test_build_documents_should_continue_when_single_document_fails(self, monkeypatch):
        document_ok = SimpleNamespace(id=uuid4())
        document_error = SimpleNamespace(id=uuid4())
        session = SimpleNamespace(
            query=lambda model: _QueryStub(all_result=[document_ok, document_error]) if model is Document else _QueryStub()
        )
        service = self._build_service(db=SimpleNamespace(session=session))

        updates = []
        pipeline_calls = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)),
        )

        def _fake_parsing(document):
            pipeline_calls.append(("parsing", document.id))
            if document is document_error:
                raise RuntimeError("parse boom")
            return ["lc-doc"]

        monkeypatch.setattr(service, "_parsing", _fake_parsing)
        monkeypatch.setattr(
            service,
            "_splitting",
            lambda document, lc_docs: pipeline_calls.append(("splitting", document.id, len(lc_docs))) or ["lc-segment"],
        )
        monkeypatch.setattr(
            service,
            "_indexing",
            lambda document, lc_segments: pipeline_calls.append(("indexing", document.id, len(lc_segments))),
        )
        monkeypatch.setattr(
            service,
            "_completed",
            lambda document, lc_segments: pipeline_calls.append(("completed", document.id, len(lc_segments))),
        )

        service.build_documents([document_ok.id, document_error.id])

        # 正常文档完整执行解析-分割-索引-完成链路
        assert ("completed", document_ok.id, 1) in pipeline_calls
        # 异常文档仅触发错误更新，不会继续进入分割/索引/完成阶段
        assert not any(step == "splitting" and doc_id == document_error.id for step, doc_id, *_ in pipeline_calls)
        assert any(
            target is document_error
            and payload.get("status") == DocumentStatus.ERROR.value
            and "parse boom" in payload.get("error", "")
            for target, payload in updates
        )

    @pytest.mark.parametrize(
        "enabled",
        [True, False],
    )
    def test_update_document_enabled_should_sync_vector_and_keyword_table(self, enabled, monkeypatch):
        document = SimpleNamespace(id=uuid4(), enabled=enabled, dataset_id=uuid4())
        segment_rows = [
            (uuid4(), "node-1", True),
            (uuid4(), "node-2", False),
        ]

        class _SegmentListQuery:
            def with_entities(self, *_args, **_kwargs):
                return self

            def filter(self, *_args, **_kwargs):
                return self

            def all(self):
                return segment_rows

        class _Session:
            def query(self, model):
                if model is Segment:
                    return _SegmentListQuery()
                raise AssertionError(f"unexpected query model: {model}")

        service = self._build_service(db=_DBStub(_Session()))
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: document)
        vector_update_calls = []
        service.vector_database_service = SimpleNamespace(
            collection=SimpleNamespace(
                data=SimpleNamespace(update=lambda **kwargs: vector_update_calls.append(kwargs))
            )
        )
        add_keyword_calls = []
        delete_keyword_calls = []
        service.keyword_table_service = SimpleNamespace(
            add_keyword_table_from_ids=lambda dataset_id, segment_ids: add_keyword_calls.append((dataset_id, segment_ids)),
            delete_keyword_table_from_ids=lambda dataset_id, segment_ids: delete_keyword_calls.append(
                (dataset_id, segment_ids)
            ),
        )
        service.redis_client = _RedisStub()

        service.update_document_enabled(document.id)

        assert len(vector_update_calls) == 2
        assert vector_update_calls[0]["properties"]["document_enabled"] == enabled
        if enabled:
            assert add_keyword_calls == [(document.dataset_id, [segment_rows[0][0]])]
            assert delete_keyword_calls == []
        else:
            assert add_keyword_calls == []
            assert delete_keyword_calls == [(document.dataset_id, [segment_rows[0][0], segment_rows[1][0]])]
        assert len(service.redis_client.delete_calls) == 1

    def test_update_document_enabled_should_mark_segment_error_when_single_vector_update_fails(self, monkeypatch):
        document = SimpleNamespace(id=uuid4(), enabled=True, dataset_id=uuid4())
        segment_rows = [(uuid4(), "node-error", True)]

        class _SegmentListQuery:
            def with_entities(self, *_args, **_kwargs):
                return self

            def filter(self, *_args, **_kwargs):
                return self

            def all(self):
                return segment_rows

        class _SegmentUpdateQuery:
            def __init__(self):
                self.payloads = []

            def filter(self, *_args, **_kwargs):
                return self

            def update(self, payload):
                self.payloads.append(payload)
                return 1

        class _Session:
            def __init__(self):
                self.segment_query_count = 0
                self.segment_update_query = _SegmentUpdateQuery()

            def query(self, model):
                if model is Segment:
                    self.segment_query_count += 1
                    if self.segment_query_count == 1:
                        return _SegmentListQuery()
                    return self.segment_update_query
                raise AssertionError(f"unexpected query model: {model}")

        session = _Session()
        service = self._build_service(db=_DBStub(session))
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: document)
        service.vector_database_service = SimpleNamespace(
            collection=SimpleNamespace(
                data=SimpleNamespace(
                    update=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("vector-update-error"))
                )
            )
        )
        service.keyword_table_service = SimpleNamespace(
            add_keyword_table_from_ids=lambda *_args, **_kwargs: None,
            delete_keyword_table_from_ids=lambda *_args, **_kwargs: None,
        )
        service.redis_client = _RedisStub()

        service.update_document_enabled(document.id)

        assert session.segment_update_query.payloads[0]["status"] == SegmentStatus.ERROR.value
        assert session.segment_update_query.payloads[0]["enabled"] is False
        assert "vector-update-error" in session.segment_update_query.payloads[0]["error"]
        assert len(service.redis_client.delete_calls) == 1

    def test_update_document_enabled_should_rollback_document_enabled_on_outer_failure(self, monkeypatch):
        document = SimpleNamespace(id=uuid4(), enabled=True, dataset_id=uuid4())
        segment_rows = [(uuid4(), "node-1", True)]

        class _SegmentListQuery:
            def with_entities(self, *_args, **_kwargs):
                return self

            def filter(self, *_args, **_kwargs):
                return self

            def all(self):
                return segment_rows

        class _Session:
            def query(self, model):
                if model is Segment:
                    return _SegmentListQuery()
                raise AssertionError(f"unexpected query model: {model}")

        service = self._build_service(db=_DBStub(_Session()))
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: document)
        service.vector_database_service = SimpleNamespace(
            collection=SimpleNamespace(data=SimpleNamespace(update=lambda **_kwargs: None))
        )
        service.keyword_table_service = SimpleNamespace(
            add_keyword_table_from_ids=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("kw-error")),
            delete_keyword_table_from_ids=lambda *_args, **_kwargs: None,
        )
        rollback_updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: rollback_updates.append((target, kwargs)),
        )
        service.redis_client = _RedisStub()

        service.update_document_enabled(document.id)

        assert rollback_updates[0][0] is document
        assert rollback_updates[0][1]["enabled"] is False
        assert rollback_updates[0][1]["disabled_at"] is not None
        assert len(service.redis_client.delete_calls) == 1

    def test_parsing_should_clean_text_and_update_document_status(self, monkeypatch):
        service = self._build_service()
        document = SimpleNamespace(id=uuid4(), upload_file=SimpleNamespace(name="demo.txt"))
        service.file_extractor = SimpleNamespace(
            load=lambda *_args, **_kwargs: [
                LCDocument(page_content="hello\x00"),
                LCDocument(page_content="foo<|bar|>"),
            ]
        )
        update_calls = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: update_calls.append((target, kwargs)),
        )

        lc_documents = service._parsing(document)

        assert lc_documents[0].page_content == "hello"
        assert lc_documents[1].page_content == "foo<bar>"
        assert update_calls[0][0] is document
        assert update_calls[0][1]["status"] == DocumentStatus.SPLITTING.value
        assert update_calls[0][1]["character_count"] == len("hello") + len("foo<bar>")

    def test_splitting_should_create_segments_attach_metadata_and_update_document(self, monkeypatch):
        class _ScalarQuery:
            def filter(self, *_args, **_kwargs):
                return self

            def scalar(self):
                return 3

        class _Session:
            def query(self, *_args, **_kwargs):
                return _ScalarQuery()

        service = self._build_service(db=_DBStub(_Session()))
        document = SimpleNamespace(id=uuid4(), account_id=uuid4(), dataset_id=uuid4(), process_rule=SimpleNamespace())

        class _Splitter:
            @staticmethod
            def split_documents(_docs):
                return [
                    LCDocument(page_content="seg-one"),
                    LCDocument(page_content="seg-two"),
                ]

        service.process_rule_service = SimpleNamespace(
            get_text_splitter_by_process_rule=lambda *_args, **_kwargs: _Splitter(),
            clean_text_by_process_rule=lambda text, _rule: text.strip(),
        )
        service.embeddings_service = SimpleNamespace(calculate_token_count=lambda text: len(text))
        create_calls = []

        def _fake_create(_model, **kwargs):
            create_calls.append(kwargs)
            return SimpleNamespace(
                id=uuid4(),
                node_id=uuid4(),
                token_count=kwargs["token_count"],
            )

        monkeypatch.setattr(service, "create", _fake_create)
        update_calls = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: update_calls.append((target, kwargs)),
        )
        lc_documents = [LCDocument(page_content=" one "), LCDocument(page_content=" two ")]

        lc_segments = service._splitting(document, lc_documents)

        assert len(lc_segments) == 2
        assert create_calls[0]["position"] == 4
        assert create_calls[1]["position"] == 5
        assert lc_segments[0].metadata["document_enabled"] is False
        assert lc_segments[1].metadata["segment_enabled"] is False
        assert update_calls[0][1]["status"] == DocumentStatus.INDEXING.value
        assert update_calls[0][1]["token_count"] == len("seg-one") + len("seg-two")

    def test_indexing_should_update_segment_keywords_and_keyword_table(self, monkeypatch):
        class _SegmentQuery:
            def __init__(self):
                self.updates = []

            def filter(self, *_args, **_kwargs):
                return self

            def update(self, payload):
                self.updates.append(payload)
                return 1

        class _Session:
            def __init__(self):
                self.segment_query = _SegmentQuery()

            def query(self, model):
                if model is Segment:
                    return self.segment_query
                raise AssertionError(f"unexpected query model: {model}")

        session = _Session()
        service = self._build_service(db=_DBStub(session))
        keyword_table_record = SimpleNamespace(keyword_table={"existing": ["old-seg-id"]})
        service.keyword_table_service = SimpleNamespace(
            get_keyword_table_from_dataset_id=lambda _dataset_id: keyword_table_record
        )
        service.jieba_service = SimpleNamespace(
            extract_keywords=lambda text, _k: ["kw1", "kw2"] if text == "seg-one" else ["kw2", "kw3"]
        )
        update_calls = []

        def _fake_update(target, **kwargs):
            update_calls.append((target, kwargs))
            if target is keyword_table_record and "keyword_table" in kwargs:
                # 模拟 ORM update 之后对象上的 keyword_table 同步更新，便于下一轮循环读取最新词表。
                target.keyword_table = kwargs["keyword_table"]

        monkeypatch.setattr(
            service,
            "update",
            _fake_update,
        )
        document = SimpleNamespace(id=uuid4(), dataset_id=uuid4())
        lc_segments = [
            LCDocument(page_content="seg-one", metadata={"segment_id": "seg-id-1"}),
            LCDocument(page_content="seg-two", metadata={"segment_id": "seg-id-2"}),
        ]

        service._indexing(document, lc_segments)

        assert len(session.segment_query.updates) == 2
        assert session.segment_query.updates[0]["status"] == SegmentStatus.INDEXING.value
        keyword_updates = [payload for target, payload in update_calls if target is keyword_table_record]
        assert len(keyword_updates) == 2
        assert set(keyword_updates[-1]["keyword_table"]["kw2"]) == {"seg-id-1", "seg-id-2"}
        assert any(target is document and "indexing_completed_at" in payload for target, payload in update_calls)

    def test_completed_should_batch_write_vectors_update_segments_and_mark_document_completed(self, monkeypatch):
        class _SegmentUpdateQuery:
            def __init__(self):
                self.payloads = []

            def filter(self, *_args, **_kwargs):
                return self

            def update(self, payload):
                self.payloads.append(payload)
                return 1

        class _Session:
            def __init__(self):
                self.segment_update_query = _SegmentUpdateQuery()

            def query(self, model):
                if model is Segment:
                    return self.segment_update_query
                raise AssertionError(f"unexpected query model: {model}")

        session = _Session()
        service = self._build_service(db=_DBStub(session))
        vector_calls = []
        service.vector_database_service = SimpleNamespace(
            vector_store=SimpleNamespace(
                add_documents=lambda **kwargs: vector_calls.append(kwargs),
            )
        )
        update_calls = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: update_calls.append((target, kwargs)),
        )
        document = SimpleNamespace(id=uuid4())
        lc_segments = [
            LCDocument(page_content=f"seg-{i}", metadata={"node_id": f"node-{i}"})
            for i in range(11)
        ]

        service._completed(document, lc_segments)

        assert len(vector_calls) == 2
        assert len(vector_calls[0]["ids"]) == 10
        assert len(vector_calls[1]["ids"]) == 1
        assert session.segment_update_query.payloads[0]["status"] == SegmentStatus.COMPLETED.value
        assert all(segment.metadata["document_enabled"] is True for segment in lc_segments)
        assert all(segment.metadata["segment_enabled"] is True for segment in lc_segments)
        assert any(
            target is document
            and payload["status"] == DocumentStatus.COMPLETED.value
            and payload["enabled"] is True
            for target, payload in update_calls
        )

    def test_completed_should_mark_segment_and_document_error_when_vector_write_fails(self, monkeypatch):
        class _SegmentUpdateQuery:
            def __init__(self):
                self.payloads = []

            def filter(self, *_args, **_kwargs):
                return self

            def update(self, payload):
                self.payloads.append(payload)
                return 1

        class _Session:
            def __init__(self):
                self.segment_update_query = _SegmentUpdateQuery()

            def query(self, model):
                if model is Segment:
                    return self.segment_update_query
                raise AssertionError(f"unexpected query model: {model}")

        session = _Session()
        service = self._build_service(db=_DBStub(session))
        service.vector_database_service = SimpleNamespace(
            vector_store=SimpleNamespace(
                add_documents=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("vector-write-error"))
            )
        )
        update_calls = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: update_calls.append((target, kwargs)),
        )
        document = SimpleNamespace(id=uuid4())
        lc_segments = [LCDocument(page_content="seg-1", metadata={"node_id": "node-1"})]

        with pytest.raises(RuntimeError):
            service._completed(document, lc_segments)

        assert session.segment_update_query.payloads[0]["status"] == SegmentStatus.ERROR.value
        assert session.segment_update_query.payloads[0]["enabled"] is False
        assert any(
            target is document
            and payload["status"] == DocumentStatus.ERROR.value
            and "vector-write-error" in payload["error"]
            for target, payload in update_calls
        )

    def test_delete_dataset_should_delete_related_records_and_vectors(self):
        dataset_id = uuid4()
        queries = {
            Document: _QueryStub(),
            Segment: _QueryStub(),
            KeywordTable: _QueryStub(),
            DatasetQuery: _QueryStub(),
        }

        class _Session:
            def query(self, model):
                return queries[model]

        vector_delete_calls = []
        service = self._build_service(db=_DBStub(_Session()))
        service.vector_database_service = SimpleNamespace(
            collection=SimpleNamespace(
                data=SimpleNamespace(delete_many=lambda **kwargs: vector_delete_calls.append(kwargs))
            )
        )

        service.delete_dataset(dataset_id)

        assert queries[Document].deleted is True
        assert queries[Segment].deleted is True
        assert queries[KeywordTable].deleted is True
        assert queries[DatasetQuery].deleted is True
        assert len(vector_delete_calls) == 1

    def test_delete_dataset_should_swallow_exception_when_vector_delete_fails(self):
        dataset_id = uuid4()
        queries = {
            Document: _QueryStub(),
            Segment: _QueryStub(),
            KeywordTable: _QueryStub(),
            DatasetQuery: _QueryStub(),
        }

        class _Session:
            def query(self, model):
                return queries[model]

        service = self._build_service(db=_DBStub(_Session()))
        service.vector_database_service = SimpleNamespace(
            collection=SimpleNamespace(
                data=SimpleNamespace(
                    delete_many=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("delete-vector-failed"))
                )
            )
        )

        # delete_dataset 内部已捕获异常，此处仅验证不会把异常抛给调用方。
        service.delete_dataset(dataset_id)

    def test_delete_document_should_delete_vectors_segments_and_keywords(self):
        dataset_id = uuid4()
        document_id = uuid4()
        segment_id_1 = uuid4()
        segment_id_2 = uuid4()
        vector_delete_calls = []
        keyword_delete_calls = []

        segment_list_query = _QueryStub(all_result=[(segment_id_1,), (segment_id_2,)])
        segment_delete_query = _QueryStub()

        class _Session:
            def __init__(self):
                self.segment_query_count = 0

            def query(self, model):
                if model is Segment:
                    self.segment_query_count += 1
                    if self.segment_query_count == 1:
                        return segment_list_query
                    return segment_delete_query
                return _QueryStub()

        db = _DBStub(_Session())
        service = self._build_service(db=db)
        service.vector_database_service = SimpleNamespace(
            collection=SimpleNamespace(
                data=SimpleNamespace(delete_many=lambda **kwargs: vector_delete_calls.append(kwargs))
            )
        )
        service.keyword_table_service = SimpleNamespace(
            delete_keyword_table_from_ids=lambda *args, **_kwargs: keyword_delete_calls.append(args)
        )

        service.delete_document(dataset_id, document_id)

        assert len(vector_delete_calls) == 1
        assert segment_delete_query.deleted is True
        assert keyword_delete_calls[0][0] == dataset_id
        assert keyword_delete_calls[0][1] == [str(segment_id_1), str(segment_id_2)]
