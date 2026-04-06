from datetime import datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from pkg.response import HttpCode
from pkg.paginator import Paginator


APP_ID = "00000000-0000-0000-0000-000000000001"
DATASET_ID = "00000000-0000-0000-0000-000000000002"
UPLOAD_FILE_ID = "00000000-0000-0000-0000-000000000003"


class TestRemainingHandlerSuccessDelegation:
    @pytest.fixture
    def http_client(self, app):
        with app.test_client() as client:
            yield client

    def test_create_app_should_delegate_to_service_and_return_id(self, http_client, monkeypatch):
        captures = {}

        def _create_app(_self, req, account):
            captures["req"] = req
            captures["account"] = account
            return SimpleNamespace(id=UUID(APP_ID))

        monkeypatch.setattr(
            "internal.service.app_service.AppService.create_app",
            _create_app,
        )

        resp = http_client.post(
            "/apps",
            json={
                "name": "Agent Demo",
                "icon": "https://a.com/icon.png",
                "description": "test app",
            },
        )

        assert resp.status_code == 200
        assert resp.json["code"] == HttpCode.SUCCESS
        assert resp.json["data"]["id"] == APP_ID
        assert captures["req"].name.data == "Agent Demo"
        assert captures["req"].icon.data == "https://a.com/icon.png"

    def test_create_documents_should_delegate_to_service_and_return_batch(self, http_client, monkeypatch):
        captures = {}

        def _create_documents(_self, dataset_id, upload_file_ids, process_type, rule, account):
            captures["dataset_id"] = dataset_id
            captures["upload_file_ids"] = upload_file_ids
            captures["process_type"] = process_type
            captures["rule"] = rule
            captures["account"] = account
            return (
                [
                    SimpleNamespace(
                        id=UUID(UPLOAD_FILE_ID),
                        name="doc-a",
                        status="waiting",
                        created_at=datetime(2024, 1, 1, 0, 0, 0),
                    )
                ],
                "batch-1",
            )

        monkeypatch.setattr(
            "internal.service.document_service.DocumentService.create_documents",
            _create_documents,
        )

        resp = http_client.post(
            f"/datasets/{DATASET_ID}/documents",
            json={
                "upload_file_ids": [UPLOAD_FILE_ID],
                "process_type": "automatic",
                "rule": {},
            },
        )

        assert resp.status_code == 200
        assert resp.json["code"] == HttpCode.SUCCESS
        assert resp.json["data"]["batch"] == "batch-1"
        assert captures["dataset_id"] == UUID(DATASET_ID)
        assert captures["upload_file_ids"] == [UPLOAD_FILE_ID]
        assert captures["process_type"] == "automatic"

    def test_get_assistant_agent_messages_should_delegate_with_parsed_request(self, http_client, monkeypatch):
        current_user_stub = SimpleNamespace(id=UUID(APP_ID))
        monkeypatch.setattr("internal.handler.assistant_agent_handler.current_user", current_user_stub)
        captures = {}

        def _get_messages(_self, req, account):
            captures["req"] = req
            captures["account"] = account
            paginator = Paginator(db=SimpleNamespace())
            paginator.current_page = 1
            paginator.page_size = 20
            paginator.total_page = 1
            paginator.total_record = 1
            return (
                [
                    SimpleNamespace(
                        id=UUID("00000000-0000-0000-0000-000000000004"),
                        conversation_id=UUID("00000000-0000-0000-0000-000000000005"),
                        query="hello",
                        image_urls=[],
                        answer="hi",
                        total_token_count=10,
                        latency=0.1,
                        agent_thoughts=[
                            SimpleNamespace(
                                id=UUID("00000000-0000-0000-0000-000000000006"),
                                position=1,
                                event="agent_message",
                                thought="thinking",
                                observation="",
                                tool="",
                                tool_input="",
                                latency=0.05,
                                created_at=datetime(2024, 1, 1, 0, 0, 0),
                            )
                        ],
                        suggested_questions=[],
                        created_at=datetime(2024, 1, 1, 0, 0, 0),
                    )
                ],
                paginator,
            )

        monkeypatch.setattr(
            "internal.service.assistant_agent_service.AssistantAgentService.get_conversation_messages_with_page",
            _get_messages,
        )

        resp = http_client.get(
            "/assistant-agent/messages",
            query_string={"current_page": 1, "page_size": 20},
        )

        assert resp.status_code == 200
        assert resp.json["code"] == HttpCode.SUCCESS
        assert resp.json["data"]["paginator"]["current_page"] == 1
        assert len(resp.json["data"]["list"]) == 1
        assert resp.json["data"]["list"][0]["id"] == "00000000-0000-0000-0000-000000000004"
        assert resp.json["data"]["list"][0]["conversation_id"] == "00000000-0000-0000-0000-000000000005"
        assert resp.json["data"]["list"][0]["query"] == "hello"
        assert resp.json["data"]["list"][0]["answer"] == "hi"
        assert resp.json["data"]["list"][0]["agent_thoughts"][0]["thought"] == "thinking"
        assert captures["req"].current_page.data == 1
        assert captures["req"].page_size.data == 20
        assert captures["account"] is current_user_stub

    def test_get_likes_should_delegate_with_query_filters(self, http_client, monkeypatch):
        current_user_stub = SimpleNamespace(id=UUID(APP_ID), is_authenticated=True)
        monkeypatch.setattr("internal.handler.like_handler.current_user", current_user_stub)
        captures = {}

        def _get_likes(_self, account, search_word="", resource_type="all"):
            captures["account"] = account
            captures["search_word"] = search_word
            captures["resource_type"] = resource_type
            return []

        monkeypatch.setattr(
            "internal.service.like_service.LikeService.get_likes",
            _get_likes,
        )

        resp = http_client.get(
            "/likes",
            query_string={"search_word": "天气", "resource_type": "app"},
        )

        assert resp.status_code == 200
        assert resp.json["code"] == HttpCode.SUCCESS
        assert resp.json["data"] == []
        assert captures["account"] is current_user_stub
        assert captures["search_word"] == "天气"
        assert captures["resource_type"] == "app"

    def test_get_favorites_should_delegate_with_query_filters(self, http_client, monkeypatch):
        current_user_stub = SimpleNamespace(id=UUID(APP_ID), is_authenticated=True)
        monkeypatch.setattr("internal.handler.favorite_handler.current_user", current_user_stub)
        captures = {}

        def _get_favorites(_self, account, search_word="", resource_type="all"):
            captures["account"] = account
            captures["search_word"] = search_word
            captures["resource_type"] = resource_type
            return []

        monkeypatch.setattr(
            "internal.service.favorite_service.FavoriteService.get_favorites",
            _get_favorites,
        )

        resp = http_client.get(
            "/favorites",
            query_string={"search_word": "代码", "resource_type": "workflow"},
        )

        assert resp.status_code == 200
        assert resp.json["code"] == HttpCode.SUCCESS
        assert resp.json["data"] == []
        assert captures["account"] is current_user_stub
        assert captures["search_word"] == "代码"
        assert captures["resource_type"] == "workflow"
