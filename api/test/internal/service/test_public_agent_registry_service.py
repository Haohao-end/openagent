from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import httpx
from flask import Flask, has_app_context
from openai import APIConnectionError

from internal.service.public_agent_registry_service import PublicAgentRegistryService


def _build_service(**kwargs) -> PublicAgentRegistryService:
    kwargs.setdefault("db", SimpleNamespace(session=SimpleNamespace(query=lambda *_args, **_kwargs: None)))
    kwargs.setdefault("faiss_service", SimpleNamespace())
    return PublicAgentRegistryService(**kwargs)


class TestPublicAgentRegistryService:
    def test_build_public_agent_document_should_only_keep_allowed_metadata(self):
        app_id = uuid4()
        service = _build_service()
        app = SimpleNamespace(
            id=app_id,
            name="客服Agent",
            description="处理退款、售后与投诉",
            tags=["客服", "售后"],
            is_public=True,
            published_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
            app_config=SimpleNamespace(
                opening_statement="你好，我可以处理售后问题",
                tools=[
                    {"provider_id": "google", "tool_id": "google_serper"},
                    {"provider_id": "gaode", "tool_id": "gaode_weather"},
                ],
                workflows=[],
                token="should-not-leak",
                headers={"Authorization": "secret"},
                dataset_id="dataset-1",
            ),
        )

        document = service.build_public_agent_document(app)

        assert document.metadata == {
            "app_id": str(app_id),
            "is_public": True,
            "published_at": int(app.published_at.timestamp()),
            "a2a_card_url": f"/public/apps/{app_id}/a2a/agent-card",
            "a2a_message_url": f"/public/apps/{app_id}/a2a/messages",
        }
        assert "token" not in document.metadata
        assert "headers" not in document.metadata
        assert "dataset_id" not in document.metadata
        assert "Agent名称: 客服Agent" in document.page_content
        assert "Agent描述: 处理退款、售后与投诉" in document.page_content
        assert "Agent标签: 客服, 售后" in document.page_content
        assert "开场白: 你好，我可以处理售后问题" in document.page_content
        assert "工具摘要: google:google_serper, gaode:gaode_weather" in document.page_content

    def test_search_public_apps_should_rebuild_index_when_store_is_empty(self, monkeypatch):
        app_id = uuid4()
        public_app = SimpleNamespace(
            id=app_id,
            name="护肤Agent",
            description="处理油痘肌和护肤问题",
            tags=["护肤"],
            published_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
            app_config=SimpleNamespace(
                opening_statement="专门解答油痘肌、痘痘肌和护肤方案",
                tools=[],
                workflows=[],
            ),
        )
        document = SimpleNamespace(
            metadata={
                "app_id": str(app_id),
                "is_public": True,
                "published_at": 123,
                "a2a_card_url": f"/public/apps/{app_id}/a2a/agent-card",
                "a2a_message_url": f"/public/apps/{app_id}/a2a/messages",
            },
            page_content="Agent名称: 护肤Agent",
        )

        class _QueryStub:
            def filter(self, *_args, **_kwargs):
                return self

            def all(self):
                return [public_app]

        search_calls = []
        rebuild_calls = []
        service = _build_service(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda *_args, **_kwargs: _QueryStub())),
            faiss_service=SimpleNamespace(
                search_public_agents=lambda **kwargs: search_calls.append(kwargs) or (
                    [] if len(search_calls) == 1 else [document]
                )
            ),
        )
        monkeypatch.setattr(
            service,
            "rebuild_public_agent_index",
            lambda: rebuild_calls.append(True) or 1,
        )

        result = service.search_public_apps("油痘肌怎么护肤", limit=3, metadata_filter={"is_public": True})

        assert rebuild_calls == [True]
        assert len(search_calls) == 2
        assert result == [
            {
                "app_id": str(app_id),
                "name": "护肤Agent",
                "description": "处理油痘肌和护肤问题",
                "tags": ["护肤"],
                "published_at": 123,
                "a2a_card_url": f"/public/apps/{app_id}/a2a/agent-card",
                "a2a_message_url": f"/public/apps/{app_id}/a2a/messages",
                "page_content": "Agent名称: 护肤Agent",
            }
        ]

    def test_rebuild_public_agent_index_should_recreate_store_then_upsert_documents(self):
        public_app = SimpleNamespace(
            id=uuid4(),
            name="护肤Agent",
            description="处理油痘肌和护肤问题",
            tags=["护肤"],
            is_public=True,
            published_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
            app_config=SimpleNamespace(
                opening_statement="专门解答油痘肌、痘痘肌和护肤方案",
                tools=[],
                workflows=[],
            ),
        )
        skipped_app = SimpleNamespace(
            id=uuid4(),
            name="空配置Agent",
            description="不会被写入索引",
            tags=[],
            is_public=True,
            published_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
            app_config=None,
        )

        class _QueryStub:
            def filter(self, *_args, **_kwargs):
                return self

            def all(self):
                return [public_app, skipped_app]

        calls = []
        captured_documents = []
        service = _build_service(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda *_args, **_kwargs: _QueryStub())),
            faiss_service=SimpleNamespace(
                recreate_public_agent_store=lambda: calls.append("recreate"),
                upsert_documents=lambda documents: calls.append("upsert") or captured_documents.extend(documents),
            ),
        )

        count = service.rebuild_public_agent_index()

        assert count == 1
        assert calls == ["recreate", "upsert"]
        assert len(captured_documents) == 1
        assert captured_documents[0].metadata["app_id"] == str(public_app.id)

    def test_search_public_apps_should_fallback_to_db_when_faiss_still_empty(self, monkeypatch):
        app_id = uuid4()
        public_app = SimpleNamespace(
            id=app_id,
            name="专业护肤顾问",
            description="提供油痘肌、痘痘肌、敏感肌护理建议",
            tags=["护肤", "油痘肌"],
            published_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
            app_config=SimpleNamespace(
                opening_statement="专门处理油痘肌护肤、痘痘肌护理与护肤方案",
                tools=[],
                workflows=[],
            ),
        )

        class _QueryStub:
            def filter(self, *_args, **_kwargs):
                return self

            def all(self):
                return [public_app]

        rebuild_calls = []
        service = _build_service(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda *_args, **_kwargs: _QueryStub())),
            faiss_service=SimpleNamespace(search_public_agents=lambda **_kwargs: []),
        )
        monkeypatch.setattr(
            service,
            "rebuild_public_agent_index",
            lambda: rebuild_calls.append(True) or 1,
        )

        result = service.search_public_apps("请使用护肤智能体回答我油痘肌该怎么护肤", limit=3)

        assert rebuild_calls == [True]
        assert result == [
            {
                "app_id": str(app_id),
                "name": "专业护肤顾问",
                "description": "提供油痘肌、痘痘肌、敏感肌护理建议",
                "tags": ["护肤", "油痘肌"],
                "published_at": int(public_app.published_at.timestamp()),
                "a2a_card_url": f"/public/apps/{app_id}/a2a/agent-card",
                "a2a_message_url": f"/public/apps/{app_id}/a2a/messages",
                "page_content": (
                    "Agent名称: 专业护肤顾问\n"
                    "Agent描述: 提供油痘肌、痘痘肌、敏感肌护理建议\n"
                    "Agent标签: 护肤, 油痘肌\n"
                    "开场白: 专门处理油痘肌护肤、痘痘肌护理与护肤方案\n"
                    "工具摘要: 无\n"
                    "工作流摘要: 无"
                ),
            }
        ]

    def test_search_public_apps_should_fallback_to_db_when_vector_search_connection_error(self, monkeypatch):
        app_id = uuid4()
        public_app = SimpleNamespace(
            id=app_id,
            name="专业护肤顾问",
            description="提供油痘肌、痘痘肌、敏感肌护理建议",
            tags=["护肤", "油痘肌"],
            published_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
            app_config=SimpleNamespace(
                opening_statement="专门处理油痘肌护肤、痘痘肌护理与护肤方案",
                tools=[],
                workflows=[],
            ),
        )

        class _QueryStub:
            def filter(self, *_args, **_kwargs):
                return self

            def all(self):
                return [public_app]

        rebuild_calls = []
        request = httpx.Request("POST", "https://api.bianxie.ai/v1/embeddings")
        service = _build_service(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda *_args, **_kwargs: _QueryStub())),
            faiss_service=SimpleNamespace(
                search_public_agents=lambda **_kwargs: (_ for _ in ()).throw(
                    APIConnectionError(message="Connection error.", request=request)
                )
            ),
        )
        monkeypatch.setattr(
            service,
            "rebuild_public_agent_index",
            lambda: rebuild_calls.append(True) or 1,
        )

        result = service.search_public_apps("请使用护肤智能体回答我油痘肌该怎么护肤", limit=3)

        assert rebuild_calls == []
        assert result == [
            {
                "app_id": str(app_id),
                "name": "专业护肤顾问",
                "description": "提供油痘肌、痘痘肌、敏感肌护理建议",
                "tags": ["护肤", "油痘肌"],
                "published_at": int(public_app.published_at.timestamp()),
                "a2a_card_url": f"/public/apps/{app_id}/a2a/agent-card",
                "a2a_message_url": f"/public/apps/{app_id}/a2a/messages",
                "page_content": (
                    "Agent名称: 专业护肤顾问\n"
                    "Agent描述: 提供油痘肌、痘痘肌、敏感肌护理建议\n"
                    "Agent标签: 护肤, 油痘肌\n"
                    "开场白: 专门处理油痘肌护肤、痘痘肌护理与护肤方案\n"
                    "工具摘要: 无\n"
                    "工作流摘要: 无"
                ),
            }
        ]

    def test_search_public_apps_should_fallback_to_db_when_rebuild_connection_error(self, monkeypatch):
        app_id = uuid4()
        public_app = SimpleNamespace(
            id=app_id,
            name="专业护肤顾问",
            description="提供油痘肌、痘痘肌、敏感肌护理建议",
            tags=["护肤", "油痘肌"],
            published_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
            app_config=SimpleNamespace(
                opening_statement="专门处理油痘肌护肤、痘痘肌护理与护肤方案",
                tools=[],
                workflows=[],
            ),
        )

        class _QueryStub:
            def filter(self, *_args, **_kwargs):
                return self

            def all(self):
                return [public_app]

        request = httpx.Request("POST", "https://api.bianxie.ai/v1/embeddings")
        service = _build_service(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda *_args, **_kwargs: _QueryStub())),
            faiss_service=SimpleNamespace(search_public_agents=lambda **_kwargs: []),
        )
        monkeypatch.setattr(
            service,
            "rebuild_public_agent_index",
            lambda: (_ for _ in ()).throw(
                APIConnectionError(message="Connection error.", request=request)
            ),
        )

        result = service.search_public_apps("请使用护肤智能体回答我油痘肌该怎么护肤", limit=3)

        assert result == [
            {
                "app_id": str(app_id),
                "name": "专业护肤顾问",
                "description": "提供油痘肌、痘痘肌、敏感肌护理建议",
                "tags": ["护肤", "油痘肌"],
                "published_at": int(public_app.published_at.timestamp()),
                "a2a_card_url": f"/public/apps/{app_id}/a2a/agent-card",
                "a2a_message_url": f"/public/apps/{app_id}/a2a/messages",
                "page_content": (
                    "Agent名称: 专业护肤顾问\n"
                    "Agent描述: 提供油痘肌、痘痘肌、敏感肌护理建议\n"
                    "Agent标签: 护肤, 油痘肌\n"
                    "开场白: 专门处理油痘肌护肤、痘痘肌护理与护肤方案\n"
                    "工具摘要: 无\n"
                    "工作流摘要: 无"
                ),
            }
        ]

    def test_convert_public_agent_search_to_tool_should_reenter_app_context(self, monkeypatch):
        flask_app = Flask(__name__)
        service = _build_service()
        captured = {}

        def _fake_search_public_apps(*, query, limit, metadata_filter, exclude_app_ids=None):
            captured["query"] = query
            captured["limit"] = limit
            captured["metadata_filter"] = metadata_filter
            captured["exclude_app_ids"] = exclude_app_ids
            captured["has_app_context"] = has_app_context()
            return [{"app_id": "demo"}]

        monkeypatch.setattr(service, "search_public_apps", _fake_search_public_apps)

        with flask_app.app_context():
            tool = service.convert_public_agent_search_to_tool()

        result = tool.invoke({"query": "油痘肌 护肤", "limit": 2})

        assert result == {"matches": [{"app_id": "demo"}]}
        assert captured == {
            "query": "油痘肌 护肤",
            "limit": 2,
            "metadata_filter": {"is_public": True},
            "exclude_app_ids": None,
            "has_app_context": True,
        }
