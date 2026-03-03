from types import SimpleNamespace

import pytest

from pkg.paginator import Paginator
from pkg.response import HttpCode, Response


APP_ID = "00000000-0000-0000-0000-000000000001"
WORKFLOW_ID = "00000000-0000-0000-0000-000000000002"
DATASET_ID = "00000000-0000-0000-0000-000000000003"
PROVIDER_ID = "00000000-0000-0000-0000-000000000004"
PUBLIC_STRING_APP_ID = "builtin-assistant"


def _assert_health(data: dict):
    assert data["status"] in {"healthy", "degraded", "unhealthy"}
    assert data["service"] == "llmops-api"
    assert "components" in data
    assert "database" in data["components"]
    assert "metrics" in data
    assert "status_code" in data["metrics"]


def _assert_categories(data: dict):
    assert "categories" in data
    assert isinstance(data["categories"], list)


def _page_paginator():
    paginator = Paginator(db=SimpleNamespace())
    paginator.current_page = 1
    paginator.page_size = 20
    paginator.total_page = 1
    paginator.total_record = 0
    return paginator


BATCH_A_VALIDATE_CASES = [
    {
        "name": "assistant_conversations_limit_invalid",
        "method": "get",
        "url": "/assistant-agent/conversations",
        "kwargs": {"query_string": {"limit": 0}},
    },
    {
        "name": "recent_conversations_limit_invalid",
        "method": "get",
        "url": "/conversations/recent",
        "kwargs": {"query_string": {"limit": 0}},
    },
    {
        "name": "public_apps_page_invalid",
        "method": "get",
        "url": "/public/apps",
        "kwargs": {"query_string": {"current_page": 0}},
    },
    {
        "name": "public_workflows_page_invalid",
        "method": "get",
        "url": "/public/workflows",
        "kwargs": {"query_string": {"current_page": 0}},
    },
    {"name": "ai_chat_missing_question", "method": "post", "url": "/ai/chat", "kwargs": {"json": {}}},
    {
        "name": "api_tool_icon_preview_missing_name",
        "method": "post",
        "url": "/api-tools/generate-icon-preview",
        "kwargs": {"json": {}},
    },
    {
        "name": "share_app_to_square_missing_category",
        "method": "post",
        "url": f"/apps/{APP_ID}/share-to-square",
        "kwargs": {"json": {}},
    },
    {
        "name": "app_icon_preview_missing_name",
        "method": "post",
        "url": "/apps/generate-icon-preview",
        "kwargs": {"json": {}},
    },
    {
        "name": "auth_reset_password_missing_fields",
        "method": "post",
        "url": "/auth/reset-password",
        "kwargs": {"json": {}},
    },
    {
        "name": "auth_send_reset_code_missing_email",
        "method": "post",
        "url": "/auth/send-reset-code",
        "kwargs": {"json": {}},
    },
    {
        "name": "dataset_icon_preview_missing_name",
        "method": "post",
        "url": "/datasets/generate-icon-preview",
        "kwargs": {"json": {}},
    },
    {
        "name": "share_workflow_to_square_missing_category",
        "method": "post",
        "url": f"/workflows/{WORKFLOW_ID}/share-to-square",
        "kwargs": {"json": {}},
    },
    {
        "name": "workflow_icon_preview_missing_name",
        "method": "post",
        "url": "/workflows/generate-icon-preview",
        "kwargs": {"json": {}},
    },
]


BATCH_B_SUCCESS_CASES = [
    {
        "name": "health_success",
        "method": "get",
        "url": "/health",
        "kwargs": {},
        "patches": [],
        "assertion": _assert_health,
    },
    {
        "name": "public_app_categories_success",
        "method": "get",
        "url": "/public/apps/categories",
        "kwargs": {},
        "patches": [],
        "assertion": _assert_categories,
    },
    {
        "name": "ai_chat_success",
        "method": "post",
        "url": "/ai/chat",
        "kwargs": {"json": {"question": "如何写单测?"}},
        "patches": [
            (
                "internal.service.ai_service.AIService.code_assistant_chat",
                Response(code=HttpCode.SUCCESS, data={"content": "ok"}),
            )
        ],
    },
    {
        "name": "api_tool_icon_preview_success",
        "method": "post",
        "url": "/api-tools/generate-icon-preview",
        "kwargs": {"json": {"name": "tool-a", "description": "desc"}},
        "patches": [
            (
                "internal.service.api_tool_service.ApiToolService.generate_icon_preview",
                "https://a.com/tool-preview.png",
            )
        ],
    },
    {
        "name": "app_share_to_square_success",
        "method": "post",
        "url": f"/apps/{APP_ID}/share-to-square",
        "kwargs": {"json": {"category": "general"}},
        "patches": [
            (
                "internal.service.public_app_service.PublicAppService.share_app_to_square",
                None,
            )
        ],
    },
    {
        "name": "app_icon_preview_success",
        "method": "post",
        "url": "/apps/generate-icon-preview",
        "kwargs": {"json": {"name": "app-a", "description": "desc"}},
        "patches": [
            (
                "internal.service.app_service.AppService.generate_icon_preview",
                "https://a.com/app-preview.png",
            )
        ],
    },
    {
        "name": "auth_reset_password_success",
        "method": "post",
        "url": "/auth/reset-password",
        "kwargs": {
            "json": {
                "email": "tester@example.com",
                "code": "123456",
                "new_password": "NewPass123",
            }
        },
        "patches": [
            (
                "internal.service.account_service.AccountService.reset_password",
                None,
            )
        ],
    },
    {
        "name": "auth_send_reset_code_success",
        "method": "post",
        "url": "/auth/send-reset-code",
        "kwargs": {"json": {"email": "tester@example.com"}},
        "patches": [
            (
                "internal.service.account_service.AccountService.send_reset_code",
                None,
            )
        ],
    },
    {
        "name": "dataset_icon_preview_success",
        "method": "post",
        "url": "/datasets/generate-icon-preview",
        "kwargs": {"json": {"name": "dataset-a", "description": "desc"}},
        "patches": [
            (
                "internal.service.dataset_service.DatasetService.generate_icon_preview",
                "https://a.com/dataset-preview.png",
            )
        ],
    },
    {
        "name": "public_app_detail_success",
        "method": "get",
        "url": f"/public/apps/{PUBLIC_STRING_APP_ID}",
        "kwargs": {},
        "patches": [
            (
                "internal.service.public_app_service.PublicAppService.get_public_app_detail",
                {"id": PUBLIC_STRING_APP_ID, "name": "public-app"},
            )
        ],
    },
    {
        "name": "public_app_analysis_success",
        "method": "get",
        "url": f"/public/apps/{PUBLIC_STRING_APP_ID}/analysis",
        "kwargs": {},
        "patches": [
            (
                "internal.service.public_app_service.PublicAppService.get_public_app_analysis",
                {"view_count": 10, "like_count": 2},
            )
        ],
    },
    {
        "name": "public_app_my_favorites_success",
        "method": "get",
        "url": "/public/apps/my-favorites",
        "kwargs": {},
        "patches": [
            ("internal.service.public_app_service.PublicAppService.get_my_favorites", [])
        ],
    },
    {
        "name": "public_workflow_detail_success",
        "method": "get",
        "url": f"/public/workflows/{WORKFLOW_ID}",
        "kwargs": {},
        "patches": [
            (
                "internal.service.public_workflow_service.PublicWorkflowService.get_public_workflow_detail",
                {"id": WORKFLOW_ID, "name": "workflow-public"},
            )
        ],
    },
    {
        "name": "public_apps_with_page_success",
        "method": "get",
        "url": "/public/apps",
        "kwargs": {"query_string": {"current_page": 1, "page_size": 20}},
        "patches": [
            (
                "internal.service.public_app_service.PublicAppService.get_public_apps_with_page",
                ([], _page_paginator()),
            )
        ],
    },
    {
        "name": "public_workflows_with_page_success",
        "method": "get",
        "url": "/public/workflows",
        "kwargs": {"query_string": {"current_page": 1, "page_size": 20}},
        "patches": [
            (
                "internal.service.public_workflow_service.PublicWorkflowService.get_public_workflows_with_page",
                ([], _page_paginator()),
            )
        ],
    },
    {
        "name": "public_workflow_draft_graph_success",
        "method": "get",
        "url": f"/public/workflows/{WORKFLOW_ID}/draft-graph",
        "kwargs": {},
        "patches": [
            (
                "internal.service.public_workflow_service.PublicWorkflowService.get_public_workflow_draft_graph",
                {"nodes": [], "edges": []},
            )
        ],
    },
    {
        "name": "api_tool_regenerate_icon_success",
        "method": "post",
        "url": f"/api-tools/{PROVIDER_ID}/regenerate-icon",
        "kwargs": {"json": {}},
        "patches": [
            (
                "internal.service.api_tool_service.ApiToolService.regenerate_icon",
                "https://a.com/tool.png",
            )
        ],
    },
    {
        "name": "app_unshare_from_square_success",
        "method": "post",
        "url": f"/apps/{APP_ID}/unshare-from-square",
        "kwargs": {"json": {}},
        "patches": [
            (
                "internal.service.public_app_service.PublicAppService.unshare_app_from_square",
                None,
            )
        ],
    },
    {
        "name": "dataset_regenerate_icon_success",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/regenerate-icon",
        "kwargs": {"json": {}},
        "patches": [
            (
                "internal.service.dataset_service.DatasetService.regenerate_icon",
                "https://a.com/dataset.png",
            )
        ],
    },
    {
        "name": "public_app_fork_success",
        "method": "post",
        "url": f"/public/apps/{PUBLIC_STRING_APP_ID}/fork",
        "kwargs": {"json": {}},
        "patches": [
            (
                "internal.service.public_app_service.PublicAppService.fork_public_app",
                SimpleNamespace(id=APP_ID, name="forked-app"),
            )
        ],
    },
    {
        "name": "public_app_favorite_success",
        "method": "post",
        "url": f"/public/apps/{APP_ID}/favorite",
        "kwargs": {"json": {}},
        "patches": [
            (
                "internal.service.public_app_service.PublicAppService.favorite_app",
                {"is_favorited": True},
            )
        ],
    },
    {
        "name": "public_app_like_success",
        "method": "post",
        "url": f"/public/apps/{APP_ID}/like",
        "kwargs": {"json": {}},
        "patches": [
            (
                "internal.service.public_app_service.PublicAppService.like_app",
                {"is_liked": True, "like_count": 1},
            )
        ],
    },
    {
        "name": "public_workflow_favorite_success",
        "method": "post",
        "url": f"/public/workflows/{WORKFLOW_ID}/favorite",
        "kwargs": {"json": {}},
        "patches": [
            (
                "internal.service.public_workflow_service.PublicWorkflowService.favorite_workflow",
                {"is_favorited": True, "favorite_count": 1},
            )
        ],
    },
    {
        "name": "workflow_share_to_square_success",
        "method": "post",
        "url": f"/workflows/{WORKFLOW_ID}/share-to-square",
        "kwargs": {"json": {"category": "general"}},
        "patches": [
            (
                "internal.service.public_workflow_service.PublicWorkflowService.share_workflow_to_square",
                None,
            )
        ],
    },
    {
        "name": "public_workflow_fork_success",
        "method": "post",
        "url": f"/public/workflows/{WORKFLOW_ID}/fork",
        "kwargs": {"json": {}},
        "patches": [
            (
                "internal.service.public_workflow_service.PublicWorkflowService.fork_public_workflow",
                SimpleNamespace(id=WORKFLOW_ID, name="forked-workflow"),
            )
        ],
    },
    {
        "name": "public_workflow_like_success",
        "method": "post",
        "url": f"/public/workflows/{WORKFLOW_ID}/like",
        "kwargs": {"json": {}},
        "patches": [
            (
                "internal.service.public_workflow_service.PublicWorkflowService.like_workflow",
                {"is_liked": True, "like_count": 2},
            )
        ],
    },
    {
        "name": "workflow_regenerate_icon_success",
        "method": "post",
        "url": f"/workflows/{WORKFLOW_ID}/regenerate-icon",
        "kwargs": {"json": {}},
        "patches": [
            (
                "internal.service.workflow_service.WorkflowService.regenerate_icon",
                "https://a.com/workflow.png",
            )
        ],
    },
    {
        "name": "workflow_icon_preview_success",
        "method": "post",
        "url": "/workflows/generate-icon-preview",
        "kwargs": {"json": {"name": "wf-a", "description": "desc"}},
        "patches": [
            (
                "internal.service.workflow_service.WorkflowService.generate_icon_preview",
                "https://a.com/workflow-preview.png",
            )
        ],
    },
    {
        "name": "workflow_share_success",
        "method": "post",
        "url": f"/workflows/{WORKFLOW_ID}/share",
        "kwargs": {"json": {"is_public": True}},
        "patches": [
            (
                "internal.service.workflow_service.WorkflowService.share_workflow_to_public",
                None,
            )
        ],
    },
    {
        "name": "workflow_unshare_from_square_success",
        "method": "post",
        "url": f"/workflows/{WORKFLOW_ID}/unshare-from-square",
        "kwargs": {"json": {}},
        "patches": [
            (
                "internal.service.public_workflow_service.PublicWorkflowService.unshare_workflow_from_square",
                None,
            )
        ],
    },
    {
        "name": "assistant_conversations_success",
        "method": "get",
        "url": "/assistant-agent/conversations",
        "kwargs": {"query_string": {"limit": 20}},
        "patches": [
            (
                "internal.service.assistant_agent_service.AssistantAgentService.get_conversations",
                [],
            )
        ],
    },
    {
        "name": "recent_conversations_success",
        "method": "get",
        "url": "/conversations/recent",
        "kwargs": {"query_string": {"limit": 20}},
        "patches": [
            (
                "internal.service.conversation_service.ConversationService.get_recent_conversations",
                [],
            )
        ],
    },
]


class TestRouteGapBatchMatrix:
    @pytest.fixture
    def http_client(self, app):
        with app.test_client() as client:
            yield client

    @pytest.mark.parametrize("case", BATCH_A_VALIDATE_CASES, ids=[c["name"] for c in BATCH_A_VALIDATE_CASES])
    def test_batch_a_should_cover_validate_routes(self, case, http_client):
        method = getattr(http_client, case["method"])
        resp = method(case["url"], **case["kwargs"])

        assert resp.status_code == 200
        assert resp.json["code"] == HttpCode.VALIDATE_ERROR

    @pytest.mark.parametrize("case", BATCH_B_SUCCESS_CASES, ids=[c["name"] for c in BATCH_B_SUCCESS_CASES])
    def test_batch_b_should_cover_success_routes(self, case, http_client, monkeypatch):
        for target, return_value in case["patches"]:
            monkeypatch.setattr(
                target,
                lambda *args, _value=return_value, **kwargs: _value,
            )

        method = getattr(http_client, case["method"])
        resp = method(case["url"], **case["kwargs"])

        assert resp.status_code == 200
        assert resp.json["code"] == HttpCode.SUCCESS
        if "assertion" in case:
            case["assertion"](resp.json["data"])

    def test_public_apps_with_page_should_fallback_to_anonymous_when_current_user_unavailable(
        self,
        http_client,
        monkeypatch,
    ):
        class _BrokenUser:
            @property
            def is_authenticated(self):
                raise RuntimeError("no-request-user")

        monkeypatch.setattr("internal.handler.public_app_handler.current_user", _BrokenUser())
        monkeypatch.setattr(
            "internal.service.public_app_service.PublicAppService.get_public_apps_with_page",
            lambda *_args, **_kwargs: ([], _page_paginator()),
        )

        resp = http_client.get(
            "/public/apps",
            query_string={"current_page": 1, "page_size": 20},
        )

        assert resp.status_code == 200
        assert resp.json["code"] == HttpCode.SUCCESS
        assert resp.json["data"]["list"] == []

    def test_public_workflows_with_page_should_fallback_to_anonymous_when_current_user_unavailable(
        self,
        http_client,
        monkeypatch,
    ):
        class _BrokenUser:
            @property
            def is_authenticated(self):
                raise RuntimeError("no-request-user")

        monkeypatch.setattr("internal.handler.public_workflow_handler.current_user", _BrokenUser())
        monkeypatch.setattr(
            "internal.service.public_workflow_service.PublicWorkflowService.get_public_workflows_with_page",
            lambda *_args, **_kwargs: ([], _page_paginator()),
        )

        resp = http_client.get(
            "/public/workflows",
            query_string={"current_page": 1, "page_size": 20},
        )

        assert resp.status_code == 200
        assert resp.json["code"] == HttpCode.SUCCESS
        assert resp.json["data"]["list"] == []
