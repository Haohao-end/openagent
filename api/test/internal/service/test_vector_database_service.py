from contextlib import contextmanager
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4
import json

import pytest
from werkzeug.datastructures import FileStorage

from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.entity.app_entity import DEFAULT_APP_CONFIG
from internal.entity.conversation_entity import InvokeFrom
from internal.entity.workflow_entity import WorkflowStatus
from internal.exception import FailException, NotFoundException
from internal.model import ApiTool, AppDatasetJoin, Dataset, Message, Workflow
from internal.service.app_config_service import AppConfigService
from internal.service.assistant_agent_service import AssistantAgentService
from internal.service.cos_service import CosService
from internal.service.embeddings_service import EmbeddingsService
from internal.service.faiss_service import FaissService
from internal.service.upload_file_service import UploadFileService
from internal.service.vector_database_service import VectorDatabaseService


@contextmanager
def _null_context():
    yield


class _QueryStub:
    def __init__(self, *, all_result=None):
        self._all_result = all_result if all_result is not None else []

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return self._all_result


class TestVectorDatabaseService:
    def test_vector_store_property_should_construct_store_instance(self, monkeypatch):
        captures = []

        class _FakeVectorStore:
            def __init__(self, **kwargs):
                captures.append(kwargs)

        monkeypatch.setattr("internal.service.vector_database_service.WeaviateVectorStore", _FakeVectorStore)
        client = SimpleNamespace(collections=SimpleNamespace(get=lambda name: f"collection:{name}"))
        service = VectorDatabaseService(
            weaviate=SimpleNamespace(client=client),
            embeddings_service=SimpleNamespace(cache_backed_embeddings="cache-emb"),
        )

        vector_store = service.vector_store

        assert isinstance(vector_store, _FakeVectorStore)
        assert captures[0]["client"] is client
        assert captures[0]["index_name"] == "Dataset"
        assert captures[0]["text_key"] == "text"
        assert captures[0]["embedding"] == "cache-emb"

    def test_collection_property_should_return_named_collection(self):
        client = SimpleNamespace(collections=SimpleNamespace(get=lambda name: f"collection:{name}"))
        service = VectorDatabaseService(
            weaviate=SimpleNamespace(client=client),
            embeddings_service=SimpleNamespace(cache_backed_embeddings="cache-emb"),
        )

        assert service.collection == "collection:Dataset"
