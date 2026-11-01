from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.documents import Document as LCDocument

from internal.core.retrievers import FullTextRetriever, SemanticRetriever


class _FakeKeywordQuery:
    def __init__(self, keyword_tables):
        self.keyword_tables = keyword_tables

    def with_entities(self, *_args, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return [(table,) for table in self.keyword_tables]


class _FakeSegmentQuery:
    def __init__(self, segments):
        self.segments = segments

    def filter(self, *criteria, **_kwargs):
        for criterion in criteria:
            field = getattr(getattr(criterion, "left", None), "key", None)
            values = getattr(getattr(criterion, "right", None), "value", None)
            if field and values is not None:
                self.segments = [item for item in self.segments if getattr(item, field, None) in values]
        return self

    def all(self):
        return self.segments


class _FakeSession:
    def __init__(self, keyword_tables, segments, documents=()):
        self.keyword_tables = keyword_tables
        self.segments = segments
        self.documents = documents

    def query(self, model):
        model_name = getattr(model, "__name__", "")
        if model_name == "KeywordTable":
            return _FakeKeywordQuery(self.keyword_tables)
        if model_name == "Document":
            return _FakeSegmentQuery(self.documents)
        return _FakeSegmentQuery(self.segments)


class _FakeJiebaService:
    def __init__(self, keywords):
        self.keywords = keywords
        self.calls = []

    def extract_keywords(self, query, top_k):
        self.calls.append((query, top_k))
        return self.keywords


def test_full_text_retriever_should_rank_by_keyword_frequency_and_keep_metadata():
    dataset_id = uuid4()
    seg_1 = SimpleNamespace(
        id="seg-1",
        content="first",
        account_id=uuid4(),
        dataset_id=dataset_id,
        document_id="doc-1",
        node_id=uuid4(),
        enabled=True,
        status="completed",
    )
    seg_2 = SimpleNamespace(
        id="seg-2",
        content="second",
        account_id=uuid4(),
        dataset_id=dataset_id,
        document_id="doc-2",
        node_id=uuid4(),
        enabled=True,
        status="completed",
    )
    db = SimpleNamespace(
        session=_FakeSession(
            keyword_tables=[
                {"python": ["seg-1", "seg-2"], "ai": ["seg-2", "seg-3"]},
                {"other": ["seg-4"]},
            ],
            segments=[seg_1, seg_2],
            documents=[
                SimpleNamespace(id="doc-1", enabled=True, status="completed"),
                SimpleNamespace(id="doc-2", enabled=True, status="completed"),
            ],
        )
    )
    jieba_service = _FakeJiebaService(["python", "ai"])

    retriever = FullTextRetriever.model_construct(
        db=db,
        dataset_ids=[dataset_id],
        jieba_service=jieba_service,
        search_kwargs={"k": 2},
    )
    docs = retriever._get_relevant_documents("python ai", run_manager=None)

    assert jieba_service.calls == [("python ai", 10)]
    assert [doc.page_content for doc in docs] == ["second", "first"]
    assert docs[0].metadata["segment_id"] == "seg-2"
    assert docs[0].metadata["score"] == 0


def test_full_text_retriever_should_return_empty_when_no_keyword_hits():
    db = SimpleNamespace(session=_FakeSession(keyword_tables=[{"python": ["seg-1"]}], segments=[]))
    jieba_service = _FakeJiebaService(["unknown"])
    retriever = FullTextRetriever.model_construct(
        db=db,
        dataset_ids=[uuid4()],
        jieba_service=jieba_service,
        search_kwargs={},
    )

    docs = retriever._get_relevant_documents("no hit", run_manager=None)

    assert docs == []


def test_full_text_retriever_should_exclude_disabled_segments_and_documents():
    dataset_id = uuid4()
    enabled_document = SimpleNamespace(id="enabled-doc", enabled=True, status="completed")
    disabled_document = SimpleNamespace(id="disabled-doc", enabled=False, status="completed")
    error_document = SimpleNamespace(id="error-doc", enabled=True, status="error")

    def segment(segment_id, document_id, enabled=True, status="completed"):
        return SimpleNamespace(id=segment_id, content=segment_id, account_id=uuid4(), dataset_id=dataset_id,
                                document_id=document_id, node_id=uuid4(), enabled=enabled, status=status)

    active = segment("active", enabled_document.id)
    disabled_segment = segment("disabled-segment", enabled_document.id, enabled=False)
    disabled_document_segment = segment("disabled-document", disabled_document.id)
    error_document_segment = segment("error-document", error_document.id)
    error_segment = segment("error-segment", enabled_document.id, status="error")
    db = SimpleNamespace(session=_FakeSession(
        [{"match": [active.id, disabled_segment.id, disabled_document_segment.id, error_document_segment.id, error_segment.id]}],
        [active, disabled_segment, disabled_document_segment, error_document_segment, error_segment],
        [enabled_document, disabled_document, error_document],
    ))
    retriever = FullTextRetriever.model_construct(
        db=db, dataset_ids=[dataset_id], jieba_service=_FakeJiebaService(["match"]), search_kwargs={}
    )

    docs = retriever._get_relevant_documents("match", run_manager=None)

    assert [doc.page_content for doc in docs] == ["active"]
    assert docs[0].metadata["document_enabled"] is True
    assert docs[0].metadata["segment_enabled"] is True


def test_full_text_retriever_backfills_ranked_hits_across_stale_batches():
    dataset_id, other_dataset_id = uuid4(), uuid4()
    documents = [SimpleNamespace(id=f"doc-{i}", enabled=True, status="completed") for i in range(3)]
    segments = [SimpleNamespace(
        id=f"segment-{i}", content=f"match-{i}", account_id=uuid4(),
        dataset_id=other_dataset_id if i == 2 else dataset_id, document_id=documents[i].id,
        node_id=uuid4(), enabled=True, status="completed",
    ) for i in range(3)]
    ids = [segments[2].id] * 3 + [
        f"stale-{i}" for i in range(100) for _ in range(2)
    ] + [segments[1].id] * 2 + [segments[0].id]
    retriever = FullTextRetriever.model_construct(
        db=SimpleNamespace(session=_FakeSession([{"match": ids}], segments, documents)),
        dataset_ids=[dataset_id], jieba_service=_FakeJiebaService(["match"]), search_kwargs={"k": 2},
    )

    docs = retriever._get_relevant_documents("match", run_manager=None)
    assert [doc.page_content for doc in docs] == ["match-1", "match-0"]


def test_semantic_retriever_should_apply_filters_and_attach_scores(monkeypatch):
    class _FilterBuilder:
        def __init__(self, prop):
            self.prop = prop

        def contains_any(self, values):
            return ("contains_any", self.prop, values)

        def equal(self, value):
            return ("equal", self.prop, value)

    class _FakeFilter:
        @staticmethod
        def by_property(prop):
            return _FilterBuilder(prop)

        @staticmethod
        def all_of(conditions):
            return ("all_of", conditions)

    class _FakeVectorStore:
        def __init__(self):
            self.calls = []

        def similarity_search_with_relevance_scores(self, **kwargs):
            self.calls.append(kwargs)
            return [
                (LCDocument(page_content="doc-1", metadata={}), 0.91),
                (LCDocument(page_content="doc-2", metadata={"existing": 1}), 0.72),
            ]

    monkeypatch.setattr("internal.core.retrievers.semantic.Filter", _FakeFilter)
    vector_store = _FakeVectorStore()
    dataset_ids = [uuid4(), uuid4()]
    retriever = SemanticRetriever.model_construct(
        dataset_ids=dataset_ids,
        vector_store=vector_store,
        search_kwargs={"k": 3, "alpha": 0.4},
    )

    docs = retriever._get_relevant_documents("query", run_manager=None)
    retriever._get_relevant_documents("next query", run_manager=None)

    assert vector_store.calls[0]["query"] == "query"
    assert vector_store.calls[1]["query"] == "next query"
    assert vector_store.calls[0]["k"] == 3
    assert vector_store.calls[1]["k"] == 3
    assert vector_store.calls[0]["alpha"] == 0.4
    assert vector_store.calls[0]["filters"][0] == "all_of"
    assert docs[0].metadata["score"] == 0.91
    assert docs[1].metadata["score"] == 0.72
    assert retriever.search_kwargs["k"] == 3
    assert retriever.search_kwargs["alpha"] == 0.4


@pytest.mark.parametrize("search_result", [None, []])
def test_semantic_retriever_should_return_empty_when_no_results(search_result):
    class _FakeVectorStore:
        @staticmethod
        def similarity_search_with_relevance_scores(**_kwargs):
            return search_result

    retriever = SemanticRetriever.model_construct(
        dataset_ids=[uuid4()],
        vector_store=_FakeVectorStore(),
        search_kwargs={},
    )

    docs = retriever._get_relevant_documents("query", run_manager=None)

    assert docs == []
