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


class TestFaissService:
    def test_init_should_load_local_faiss_index(self, monkeypatch):
        fake_faiss = SimpleNamespace(as_retriever=lambda **_kwargs: SimpleNamespace())
        monkeypatch.setattr(
            "internal.service.faiss_service.FAISS.load_local",
            staticmethod(lambda **_kwargs: fake_faiss),
        )

        service = FaissService(embeddings_service=SimpleNamespace(embeddings="embeddings-client"))

        assert service.faiss is fake_faiss

    def test_convert_faiss_to_tool_should_return_invokable_tool(self, monkeypatch):
        class _Retriever:
            def __or__(self, _other):
                return SimpleNamespace(invoke=lambda query: f"retrieved:{query}")

        fake_faiss = SimpleNamespace(as_retriever=lambda **_kwargs: _Retriever())
        monkeypatch.setattr(
            "internal.service.faiss_service.FAISS.load_local",
            staticmethod(lambda **_kwargs: fake_faiss),
        )

        service = FaissService(embeddings_service=SimpleNamespace(embeddings="embeddings-client"))
        tool = service.convert_faiss_to_tool()
        result = tool.invoke({"query": "weather in shanghai"})

        assert result == "retrieved:weather in shanghai"
