from contextlib import contextmanager
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4
import json

import pytest
from langchain_core.documents import Document
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
        captured = {}
        monkeypatch.setattr(
            "internal.service.faiss_service.os.path.exists",
            lambda _path: True,
        )
        monkeypatch.setattr(
            "internal.service.faiss_service.FAISS.load_local",
            staticmethod(lambda **kwargs: captured.update(kwargs) or fake_faiss),
        )

        service = FaissService(
            embeddings_service=SimpleNamespace(
                embeddings="embeddings-client",
                cache_backed_embeddings="cached-embeddings-client",
            )
        )

        assert service.faiss is fake_faiss
        assert captured["embeddings"] == "cached-embeddings-client"

    def test_init_should_create_empty_faiss_index_when_store_missing(self, monkeypatch):
        fake_faiss = SimpleNamespace(save_local=lambda *_args, **_kwargs: None)
        monkeypatch.setattr(
            "internal.service.faiss_service.os.path.exists",
            lambda _path: False,
        )
        monkeypatch.setattr(
            "internal.service.faiss_service.os.makedirs",
            lambda *_args, **_kwargs: None,
        )
        monkeypatch.setattr(
            "internal.service.faiss_service.FaissService._create_empty_vector_store",
            lambda self: fake_faiss,
        )

        service = FaissService(
            embeddings_service=SimpleNamespace(
                embeddings="embeddings-client",
                cache_backed_embeddings="cached-embeddings-client",
                embedding_dimension=1536,
            )
        )

        assert service.faiss is fake_faiss

    def test_convert_faiss_to_tool_should_return_invokable_tool(self, monkeypatch):
        fake_document = SimpleNamespace(
            metadata={
                "app_id": "app-1",
                "is_public": True,
                "published_at": 123,
                "a2a_card_url": "/public/apps/app-1/a2a/agent-card",
                "a2a_message_url": "/public/apps/app-1/a2a/messages",
            },
            page_content="Agent名称: 客服Agent",
        )
        fake_faiss = SimpleNamespace(
            index=SimpleNamespace(ntotal=1),
            similarity_search=lambda *_args, **_kwargs: [fake_document],
            save_local=lambda *_args, **_kwargs: None,
        )
        monkeypatch.setattr(
            "internal.service.faiss_service.os.path.exists",
            lambda _path: True,
        )
        monkeypatch.setattr(
            "internal.service.faiss_service.FAISS.load_local",
            staticmethod(lambda **_kwargs: fake_faiss),
        )

        service = FaissService(
            embeddings_service=SimpleNamespace(
                embeddings="embeddings-client",
                cache_backed_embeddings="cached-embeddings-client",
            )
        )
        tool = service.convert_faiss_to_tool()
        result = tool.invoke({"query": "weather in shanghai"})

        assert result["matches"][0]["app_id"] == "app-1"

    def test_upsert_documents_should_embed_before_mutating_index(self, monkeypatch):
        events = []

        class _FakeCacheEmbeddings:
            def embed_documents(self, texts):
                events.append(("embed", list(texts)))
                return [[0.1], [0.2]]

        class _FakeFaiss:
            def __init__(self):
                self.index_to_docstore_id = {0: "app-1"}

            def delete(self, ids):
                events.append(("delete", ids))

            def add_embeddings(self, text_embeddings, metadatas, ids):
                events.append(("add", list(text_embeddings), metadatas, ids))

            def save_local(self, *_args, **_kwargs):
                events.append(("save",))

        fake_faiss = _FakeFaiss()
        monkeypatch.setattr(
            "internal.service.faiss_service.os.path.exists",
            lambda _path: True,
        )
        monkeypatch.setattr(
            "internal.service.faiss_service.FAISS.load_local",
            staticmethod(lambda **_kwargs: fake_faiss),
        )

        service = FaissService(
            embeddings_service=SimpleNamespace(
                embeddings="embeddings-client",
                cache_backed_embeddings=_FakeCacheEmbeddings(),
                embedding_dimension=1536,
            )
        )

        service.upsert_documents(
            [
                Document(page_content="Agent名称: 护肤Agent", metadata={"app_id": "app-1"}),
                Document(page_content="Agent名称: 客服Agent", metadata={"app_id": "app-2"}),
            ]
        )

        assert events == [
            ("embed", ["Agent名称: 护肤Agent", "Agent名称: 客服Agent"]),
            ("delete", ["app-1"]),
            (
                "add",
                [("Agent名称: 护肤Agent", [0.1]), ("Agent名称: 客服Agent", [0.2])],
                [{"app_id": "app-1"}, {"app_id": "app-2"}],
                ["app-1", "app-2"],
            ),
            ("save",),
        ]

    def test_delete_by_app_ids_should_ignore_missing_ids(self, monkeypatch):
        calls = {"delete": [], "save": 0}

        class _FakeFaiss:
            def __init__(self):
                self.index_to_docstore_id = {0: "app-1"}

            def delete(self, ids):
                calls["delete"].append(ids)

            def save_local(self, *_args, **_kwargs):
                calls["save"] += 1

        fake_faiss = _FakeFaiss()
        monkeypatch.setattr(
            "internal.service.faiss_service.os.path.exists",
            lambda _path: True,
        )
        monkeypatch.setattr(
            "internal.service.faiss_service.FAISS.load_local",
            staticmethod(lambda **_kwargs: fake_faiss),
        )

        service = FaissService(
            embeddings_service=SimpleNamespace(
                embeddings="embeddings-client",
                cache_backed_embeddings="cached-embeddings-client",
                embedding_dimension=1536,
            )
        )

        service.delete_by_app_ids(["missing-app-id", ""])

        assert calls["delete"] == []
        assert calls["save"] == 0
