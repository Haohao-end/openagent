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


class TestProcessRuleService:
    def test_get_text_splitter_by_process_rule_should_pass_rule_arguments(self, monkeypatch):
        captures = {}

        class _FakeSplitter:
            def __init__(self, **kwargs):
                captures.update(kwargs)

        monkeypatch.setattr("internal.service.process_rule_service.RecursiveCharacterTextSplitter", _FakeSplitter)
        process_rule = SimpleNamespace(
            rule={
                "segment": {
                    "chunk_size": 256,
                    "chunk_overlap": 32,
                    "separators": ["\n\n", "\n", ""],
                }
            }
        )

        splitter = ProcessRuleService.get_text_splitter_by_process_rule(process_rule)

        assert isinstance(splitter, _FakeSplitter)
        assert captures["chunk_size"] == 256
        assert captures["chunk_overlap"] == 32
        assert captures["is_separator_regex"] is True

    def test_clean_text_by_process_rule_should_remove_url_and_email_and_spaces(self):
        process_rule = SimpleNamespace(
            rule={
                "pre_process_rules": [
                    {"id": "remove_extra_space", "enabled": True},
                    {"id": "remove_url_and_email", "enabled": True},
                ]
            }
        )
        text = "联系我: demo@example.com   \n\n\n访问 https://example.com/page"

        result = ProcessRuleService.clean_text_by_process_rule(text, process_rule)

        assert "demo@example.com" not in result
        assert "https://example.com/page" not in result
        assert "\n\n\n" not in result
