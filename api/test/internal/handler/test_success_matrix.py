from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from uuid import UUID

import pytest

from pkg.paginator import Paginator
from pkg.response import HttpCode, Response


APP_ID = "00000000-0000-0000-0000-000000000001"
PROVIDER_ID = "00000000-0000-0000-0000-000000000002"
DATASET_ID = "00000000-0000-0000-0000-000000000003"
DOCUMENT_ID = "00000000-0000-0000-0000-000000000004"
SEGMENT_ID = "00000000-0000-0000-0000-000000000005"
WORKFLOW_ID = "00000000-0000-0000-0000-000000000006"
CONVERSATION_ID = "00000000-0000-0000-0000-000000000007"
TASK_ID = "00000000-0000-0000-0000-000000000008"
MESSAGE_ID = "00000000-0000-0000-0000-000000000009"


def _oauth_obj():
    return SimpleNamespace(get_authorization_url=lambda: "https://oauth.example.com/auth")


def _upload_file_obj():
    return SimpleNamespace(
        id=APP_ID,
        account_id=APP_ID,
        name="a.txt",
        key="cos-key-1",
        size=1,
        extension="txt",
        mime_type="text/plain",
        created_at=datetime.now(UTC),
    )


def _dt():
    return datetime(2024, 1, 2, 3, 4, 5)


def _uuid(value: str) -> UUID:
    return UUID(value)


def _account_obj(name: str = "tester"):
    return SimpleNamespace(
        name=name,
        avatar=f"https://a.com/{name}.png",
    )


def _paginator():
    paginator = Paginator(db=SimpleNamespace())
    paginator.total_page = 1
    paginator.total_record = 1
    paginator.current_page = 1
    paginator.page_size = 20
    return paginator


def _agent_thought_obj():
    return SimpleNamespace(
        id=_uuid(TASK_ID),
        position=1,
        event="agent_message",
        thought="思考中",
        observation="观察结果",
        tool="google_serper",
        tool_input='{"q":"weather"}',
        latency=0.12,
        created_at=_dt(),
    )


def _message_obj():
    return SimpleNamespace(
        id=_uuid(MESSAGE_ID),
        conversation_id=_uuid(CONVERSATION_ID),
        query="今天天气如何？",
        image_urls=["https://a.com/1.png"],
        answer="晴天",
        total_token_count=128,
        latency=0.42,
        agent_thoughts=[_agent_thought_obj()],
        suggested_questions=["明天呢？"],
        created_at=_dt(),
    )


def _app_obj():
    return SimpleNamespace(
        id=_uuid(APP_ID),
        debug_conversation_id=_uuid(CONVERSATION_ID),
        name="Agent Demo",
        icon="https://a.com/app.png",
        description="应用描述",
        status="published",
        is_public=False,
        category="general",
        draft_app_config=SimpleNamespace(
            updated_at=_dt(),
            preset_prompt="draft prompt",
            model_config={"provider": "openai", "model": "gpt-4o-mini"},
        ),
        app_config=SimpleNamespace(
            preset_prompt="published prompt",
            model_config={"provider": "openai", "model": "gpt-4o"},
        ),
        account=_account_obj("app-owner"),
        updated_at=_dt(),
        created_at=_dt(),
    )


def _history_obj():
    return SimpleNamespace(
        id=_uuid("00000000-0000-0000-0000-000000000010"),
        app_id=_uuid(APP_ID),
        version=3,
        config_type="published",
        model_config={"provider": "deepseek", "model": "deepseek-chat"},
        dialog_round=3,
        preset_prompt="published prompt",
        tools=[],
        workflows=[],
        datasets=[],
        retrieval_config={"retrieval_strategy": "semantic", "k": 10, "score": 0.5},
        long_term_memory={"enable": True},
        opening_statement="hello",
        opening_questions=["q1"],
        speech_to_text={"enable": True},
        text_to_speech={"enable": True, "voice": "alex", "auto_play": True},
        suggested_after_answer={"enable": True},
        review_config={"enable": False},
        updated_at=_dt(),
        created_at=_dt(),
        is_current_published=True,
        display_config={
            "model_config": {"provider": "deepseek", "model": "deepseek-chat"},
            "dialog_round": 3,
            "preset_prompt": "published prompt",
            "tools": [
                {
                    "type": "builtin_tool",
                    "provider": {"id": "google", "label": "Google 搜索"},
                    "tool": {"id": "google_serper", "name": "google_serper", "label": "Google 检索"},
                }
            ],
            "workflows": [],
            "datasets": [],
            "retrieval_config": {"retrieval_strategy": "semantic", "k": 10, "score": 0.5},
            "long_term_memory": {"enable": True},
            "opening_statement": "hello",
            "opening_questions": ["q1"],
            "speech_to_text": {"enable": True},
            "text_to_speech": {"enable": True, "voice": "alex", "auto_play": True},
            "suggested_after_answer": {"enable": True},
            "review_config": {"enable": False},
        },
    )


def _draft_version_obj():
    return SimpleNamespace(
        id=_uuid("00000000-0000-0000-0000-000000000012"),
        app_id=_uuid(APP_ID),
        version=0,
        config_type="draft",
        model_config={"provider": "deepseek", "model": "deepseek-chat"},
        dialog_round=3,
        preset_prompt="draft prompt",
        tools=[],
        workflows=[],
        datasets=[],
        retrieval_config={"retrieval_strategy": "semantic", "k": 10, "score": 0.5},
        long_term_memory={"enable": True},
        opening_statement="draft hello",
        opening_questions=["draft q1"],
        speech_to_text={"enable": True},
        text_to_speech={"enable": True, "voice": "alex", "auto_play": True},
        suggested_after_answer={"enable": True},
        review_config={"enable": False},
        updated_at=_dt(),
        created_at=_dt(),
        is_current_published=False,
        display_config={
            "model_config": {"provider": "deepseek", "model": "deepseek-chat"},
            "dialog_round": 3,
            "preset_prompt": "draft prompt",
            "tools": [
                {
                    "type": "builtin_tool",
                    "provider": {"id": "google", "label": "Google 搜索"},
                    "tool": {"id": "google_serper", "name": "google_serper", "label": "Google 检索"},
                }
            ],
            "workflows": [],
            "datasets": [],
            "retrieval_config": {"retrieval_strategy": "semantic", "k": 10, "score": 0.5},
            "long_term_memory": {"enable": True},
            "opening_statement": "draft hello",
            "opening_questions": ["draft q1"],
            "speech_to_text": {"enable": True},
            "text_to_speech": {"enable": True, "voice": "alex", "auto_play": True},
            "suggested_after_answer": {"enable": True},
            "review_config": {"enable": False},
        },
    )


def _workflow_obj():
    return SimpleNamespace(
        id=_uuid(WORKFLOW_ID),
        name="Workflow Demo",
        tool_call_name="wf_demo",
        icon="https://a.com/wf.png",
        description="工作流描述",
        status="published",
        is_debug_passed=True,
        is_public=False,
        draft_graph={"nodes": [{}, {}]},
        graph={"nodes": [{}]},
        account=_account_obj("workflow-owner"),
        published_at=_dt(),
        updated_at=_dt(),
        created_at=_dt(),
    )


def _dataset_obj():
    return SimpleNamespace(
        id=_uuid(DATASET_ID),
        name="Dataset Demo",
        icon="https://a.com/ds.png",
        description="知识库描述",
        document_count=5,
        hit_count=9,
        related_app_count=2,
        character_count=1024,
        account=_account_obj("dataset-owner"),
        updated_at=_dt(),
        created_at=_dt(),
    )


def _dataset_query_obj():
    return SimpleNamespace(
        id=_uuid("00000000-0000-0000-0000-000000000011"),
        dataset_id=_uuid(DATASET_ID),
        query="召回测试",
        source="debugger",
        created_at=_dt(),
    )


def _document_obj():
    return SimpleNamespace(
        id=_uuid(DOCUMENT_ID),
        dataset_id=_uuid(DATASET_ID),
        name="文档A",
        segment_count=3,
        character_count=300,
        hit_count=7,
        position=1,
        enabled=True,
        disabled_at=_dt(),
        status="completed",
        error="",
        updated_at=_dt(),
        created_at=_dt(),
    )


def _segment_obj():
    return SimpleNamespace(
        id=_uuid(SEGMENT_ID),
        document_id=_uuid(DOCUMENT_ID),
        dataset_id=_uuid(DATASET_ID),
        position=1,
        content="片段内容",
        keywords=["weather", "query"],
        character_count=16,
        token_count=8,
        hit_count=3,
        hash="hash-1",
        enabled=True,
        disabled_at=_dt(),
        status="completed",
        error="",
        updated_at=_dt(),
        created_at=_dt(),
    )


def _api_tool_provider_obj():
    return SimpleNamespace(
        id=_uuid(PROVIDER_ID),
        name="Weather Provider",
        icon="https://a.com/provider.png",
        description="天气工具提供者",
        openapi_schema="{}",
        headers=[{"key": "Authorization", "value": "Bearer demo"}],
        account=_account_obj("provider-owner"),
        tools=[
            SimpleNamespace(
                id=_uuid("00000000-0000-0000-0000-000000000012"),
                name="get_weather",
                description="查询天气",
                parameters=[{"name": "location", "type": "string", "required": True, "in": "query"}],
            )
        ],
        updated_at=_dt(),
        created_at=_dt(),
    )


def _api_tool_obj():
    provider = _api_tool_provider_obj()
    return SimpleNamespace(
        id=_uuid("00000000-0000-0000-0000-000000000013"),
        name="get_weather",
        description="查询天气",
        parameters=[{"name": "location", "type": "string", "required": True, "in": "query"}],
        provider=provider,
    )


def _api_key_obj():
    return SimpleNamespace(
        id=_uuid("00000000-0000-0000-0000-000000000014"),
        api_key="sk-demo",
        is_active=True,
        remark="测试key",
        updated_at=_dt(),
        created_at=_dt(),
    )


def _conversation_obj():
    return SimpleNamespace(
        id=_uuid(CONVERSATION_ID),
        name="会话A",
        summary="这是一段摘要",
        created_at=_dt(),
    )


def _assert_page_model(data: dict):
    assert data["paginator"]["current_page"] == 1
    assert data["paginator"]["page_size"] == 20
    assert data["paginator"]["total_page"] == 1
    assert data["paginator"]["total_record"] == 1


def _assert_get_app(data: dict):
    assert data["id"] == APP_ID
    assert data["debug_conversation_id"] == CONVERSATION_ID
    assert data["name"] == "Agent Demo"
    assert data["draft_updated_at"] > 0


def _assert_get_apps_with_page(data: dict):
    _assert_page_model(data)
    app = data["list"][0]
    assert app["id"] == APP_ID
    assert app["preset_prompt"] == "published prompt"
    assert app["model_config"]["provider"] == "openai"
    assert app["model_config"]["model"] == "gpt-4o"


def _assert_publish_histories_with_page(data: dict):
    _assert_page_model(data)
    assert data["list"][0]["version"] == 3
    assert data["list"][0]["config_type"] == "published"
    assert data["list"][0]["config"]["model_config"]["provider"] == "deepseek"
    assert data["list"][0]["is_current_published"] is True
    assert data["list"][0]["created_at"] > 0


def _assert_get_versions(data: dict):
    assert len(data["list"]) == 2
    assert data["list"][0]["config_type"] == "draft"
    assert data["list"][0]["label"] == "草稿"
    assert data["list"][0]["config"]["tools"][0]["provider"]["label"] == "Google 搜索"
    assert data["list"][1]["config_type"] == "published"
    assert data["list"][1]["is_current_published"] is True
    assert data["list"][1]["label"] == "版本 #003"


def _assert_message_page(data: dict):
    _assert_page_model(data)
    message = data["list"][0]
    assert message["id"] == MESSAGE_ID
    assert message["answer"] == "晴天"
    assert message["created_at"] > 0
    assert message["agent_thoughts"][0]["tool"] == "google_serper"
    assert message["agent_thoughts"][0]["created_at"] > 0


def _assert_get_workflow(data: dict):
    assert data["id"] == WORKFLOW_ID
    assert data["node_count"] == 2
    assert data["is_debug_passed"] is True


def _assert_get_workflow_draft_graph(data: dict):
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["node_type"] == "start"
    assert data["edges"] == []


def _assert_get_workflows_with_page(data: dict):
    _assert_page_model(data)
    workflow = data["list"][0]
    assert workflow["id"] == WORKFLOW_ID
    assert workflow["node_count"] == 2
    assert workflow["status"] == "published"


def _assert_get_dataset(data: dict):
    assert data["id"] == DATASET_ID
    assert data["document_count"] == 5
    assert data["hit_count"] == 9
    assert data["upload_at"] > 0


def _assert_get_datasets_with_page(data: dict):
    _assert_page_model(data)
    dataset = data["list"][0]
    assert dataset["id"] == DATASET_ID
    assert dataset["document_count"] == 5
    assert dataset["upload_at"] > 0


def _assert_get_dataset_queries(data: list):
    assert data[0]["dataset_id"] == DATASET_ID
    assert data[0]["query"] == "召回测试"
    assert data[0]["created_at"] > 0


def _assert_get_document(data: dict):
    assert data["id"] == DOCUMENT_ID
    assert data["dataset_id"] == DATASET_ID
    assert data["segment_count"] == 3
    assert data["disabled_at"] > 0


def _assert_get_documents_with_page(data: dict):
    _assert_page_model(data)
    document = data["list"][0]
    assert document["id"] == DOCUMENT_ID
    assert document["character_count"] == 300
    assert document["disabled_at"] > 0


def _assert_get_segment(data: dict):
    assert data["id"] == SEGMENT_ID
    assert data["document_id"] == DOCUMENT_ID
    assert data["hash"] == "hash-1"
    assert data["disabled_at"] > 0


def _assert_get_segments_with_page(data: dict):
    _assert_page_model(data)
    segment = data["list"][0]
    assert segment["id"] == SEGMENT_ID
    assert segment["token_count"] == 8
    assert segment["disabled_at"] > 0


def _assert_get_api_tool_provider(data: dict):
    assert data["id"] == PROVIDER_ID
    assert data["name"] == "Weather Provider"
    assert data["headers"][0]["key"] == "Authorization"


def _assert_get_api_tools_with_page(data: dict):
    _assert_page_model(data)
    provider = data["list"][0]
    assert provider["id"] == PROVIDER_ID
    assert provider["tools"][0]["name"] == "get_weather"
    assert "in" not in provider["tools"][0]["inputs"][0]


def _assert_get_api_tool(data: dict):
    assert data["name"] == "get_weather"
    assert data["provider"]["id"] == PROVIDER_ID
    assert "in" not in data["inputs"][0]


def _assert_get_api_keys_with_page(data: dict):
    _assert_page_model(data)
    api_key = data["list"][0]
    assert api_key["api_key"] == "****************"
    assert api_key["is_active"] is True


def _assert_get_web_app_conversations(data: list):
    assert data[0]["id"] == CONVERSATION_ID
    assert data[0]["name"] == "会话A"
    assert data[0]["created_at"] > 0


CASES = [
    # app
    {
        "name": "update_app_success",
        "method": "post",
        "url": f"/apps/{APP_ID}",
        "kwargs": {"json": {"name": "demo", "icon": "https://a.com/a.png", "description": "d"}},
        "patches": [("internal.service.app_service.AppService.update_app", None)],
    },
    {
        "name": "update_draft_config_success",
        "method": "post",
        "url": f"/apps/{APP_ID}/draft-app-config",
        "kwargs": {"json": {"preset_prompt": "hello"}},
        "patches": [("internal.service.app_service.AppService.update_draft_app_config", None)],
    },
    {
        "name": "publish_success",
        "method": "post",
        "url": f"/apps/{APP_ID}/publish",
        "kwargs": {"json": {}},
        "patches": [("internal.service.app_service.AppService.publish_draft_app_config", None)],
    },
    {
        "name": "cancel_publish_success",
        "method": "post",
        "url": f"/apps/{APP_ID}/cancel-publish",
        "kwargs": {"json": {}},
        "patches": [("internal.service.app_service.AppService.cancel_publish_app_config", None)],
    },
    {
        "name": "fallback_history_success",
        "method": "post",
        "url": f"/apps/{APP_ID}/fallback-history",
        "kwargs": {"json": {"app_config_version_id": APP_ID}},
        "patches": [("internal.service.app_service.AppService.fallback_history_to_draft", None)],
    },
    {
        "name": "update_debug_summary_success",
        "method": "post",
        "url": f"/apps/{APP_ID}/summary",
        "kwargs": {"json": {"summary": "memory"}},
        "patches": [("internal.service.app_service.AppService.update_debug_conversation_summary", None)],
    },
    {
        "name": "delete_debug_conversation_success",
        "method": "post",
        "url": f"/apps/{APP_ID}/conversations/delete-debug-conversation",
        "kwargs": {"json": {}},
        "patches": [("internal.service.app_service.AppService.delete_debug_conversation", None)],
    },
    {
        "name": "stop_debug_chat_success",
        "method": "post",
        "url": f"/apps/{APP_ID}/conversations/tasks/{TASK_ID}/stop",
        "kwargs": {"json": {}},
        "patches": [("internal.service.app_service.AppService.stop_debug_chat", None)],
    },
    {
        "name": "debug_chat_success",
        "method": "post",
        "url": f"/apps/{APP_ID}/conversations",
        "kwargs": {"json": {"query": "hello"}},
        "patches": [
            (
                "internal.service.app_service.AppService.debug_chat",
                Response(code=HttpCode.SUCCESS, data={"answer": "ok"}),
            )
        ],
    },
    {
        "name": "prompt_compare_chat_success",
        "method": "post",
        "url": f"/apps/{APP_ID}/prompt-compare/chat",
        "kwargs": {
            "json": {
                "lane_id": "lane-1",
                "query": "hello",
                "preset_prompt": "你是一个助手",
                "model_config": {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "parameters": {},
                },
                "history": [],
            }
        },
        "patches": [
            (
                "internal.service.app_service.AppService.prompt_compare_chat",
                Response(code=HttpCode.SUCCESS, data={"answer": "ok"}),
            )
        ],
    },
    {
        "name": "stop_prompt_compare_chat_success",
        "method": "post",
        "url": f"/apps/{APP_ID}/prompt-compare/tasks/{TASK_ID}/stop",
        "kwargs": {"json": {}},
        "patches": [("internal.service.app_service.AppService.stop_prompt_compare_chat", None)],
    },
    {
        "name": "delete_app_success",
        "method": "post",
        "url": f"/apps/{APP_ID}/delete",
        "kwargs": {"json": {}},
        "patches": [("internal.service.app_service.AppService.delete_app", None)],
    },
    {
        "name": "copy_app_success",
        "method": "post",
        "url": f"/apps/{APP_ID}/copy",
        "kwargs": {"json": {}},
        "patches": [("internal.service.app_service.AppService.copy_app", SimpleNamespace(id=APP_ID))],
    },
    {
        "name": "regenerate_web_app_token_success",
        "method": "post",
        "url": f"/apps/{APP_ID}/published-config/regenerate-web-app-token",
        "kwargs": {"json": {}},
        "patches": [("internal.service.app_service.AppService.regenerate_web_app_token", "token-1")],
    },
    # api tool
    {
        "name": "create_api_tool_success",
        "method": "post",
        "url": "/api-tools",
        "kwargs": {"json": {"name": "tool", "icon": "https://a.com/a.png", "openapi_schema": "{}", "headers": []}},
        "patches": [("internal.service.api_tool_service.ApiToolService.create_api_tool", None)],
    },
    {
        "name": "update_api_tool_success",
        "method": "post",
        "url": f"/api-tools/{PROVIDER_ID}",
        "kwargs": {"json": {"name": "tool", "icon": "https://a.com/a.png", "openapi_schema": "{}", "headers": []}},
        "patches": [("internal.service.api_tool_service.ApiToolService.update_api_tool_provider", None)],
    },
    {
        "name": "delete_api_tool_success",
        "method": "post",
        "url": f"/api-tools/{PROVIDER_ID}/delete",
        "kwargs": {"json": {}},
        "patches": [("internal.service.api_tool_service.ApiToolService.delete_api_tool_provider", None)],
    },
    {
        "name": "validate_openapi_schema_success",
        "method": "post",
        "url": "/api-tools/validate-openapi-schema",
        "kwargs": {"json": {"openapi_schema": "{}"}},
        "patches": [("internal.service.api_tool_service.ApiToolService.parse_openapi_schema", None)],
    },
    # account/auth/oauth
    {
        "name": "update_account_password_success",
        "method": "post",
        "url": "/account/password",
        "kwargs": {"json": {"current_password": "OldPass123", "new_password": "Abcd1234"}},
        "patches": [("internal.service.account_service.AccountService.change_password", None)],
    },
    {
        "name": "send_change_email_code_success",
        "method": "post",
        "url": "/account/email/send-code",
        "kwargs": {"json": {"email": "next@example.com"}},
        "patches": [("internal.service.account_service.AccountService.send_change_email_code", None)],
    },
    {
        "name": "update_account_email_success",
        "method": "post",
        "url": "/account/email",
        "kwargs": {
            "json": {
                "email": "next@example.com",
                "code": "123456",
                "current_password": "OldPass123",
            }
        },
        "patches": [("internal.service.account_service.AccountService.update_email", None)],
    },
    {
        "name": "update_account_name_success",
        "method": "post",
        "url": "/account/name",
        "kwargs": {"json": {"name": "tester"}},
        "patches": [("internal.service.account_service.AccountService.update_account", None)],
    },
    {
        "name": "update_account_avatar_success",
        "method": "post",
        "url": "/account/avatar",
        "kwargs": {"json": {"avatar": "https://a.com/a.png"}},
        "patches": [("internal.service.account_service.AccountService.update_account", None)],
    },
    {
        "name": "password_login_success",
        "method": "post",
        "url": "/auth/password-login",
        "kwargs": {"json": {"email": "test@example.com", "password": "Abcd1234"}},
        "patches": [("internal.service.account_service.AccountService.password_login", {"access_token": "t", "expire_at": 1})],
    },
    {
        "name": "verify_login_challenge_success",
        "method": "post",
        "url": "/auth/login-challenge/verify",
        "kwargs": {"json": {"challenge_id": "challenge-1", "code": "123456"}},
        "patches": [("internal.service.account_service.AccountService.verify_login_challenge", {"access_token": "t", "expire_at": 1})],
    },
    {
        "name": "resend_login_challenge_success",
        "method": "post",
        "url": "/auth/login-challenge/resend",
        "kwargs": {"json": {"challenge_id": "challenge-1"}},
        "patches": [("internal.service.account_service.AccountService.resend_login_challenge", {"challenge_required": True})],
    },
    {
        "name": "oauth_provider_success",
        "method": "get",
        "url": "/oauth/github",
        "kwargs": {},
        "patches": [("internal.service.oauth_service.OAuthService.get_oauth_by_provider_name", _oauth_obj())],
    },
    {
        "name": "oauth_authorize_success",
        "method": "post",
        "url": "/oauth/authorize/github",
        "kwargs": {"json": {"code": "abc"}},
        "patches": [("internal.service.oauth_service.OAuthService.oauth_login", {"access_token": "t", "expire_at": 1})],
    },
    {
        "name": "unbind_account_oauth_success",
        "method": "post",
        "url": "/account/oauth/github/unbind",
        "kwargs": {"json": {}},
        "patches": [("internal.service.oauth_service.OAuthService.unbind_oauth", None)],
    },
    {
        "name": "revoke_account_session_success",
        "method": "post",
        "url": f"/account/sessions/{MESSAGE_ID}/revoke",
        "kwargs": {"json": {}},
        "patches": [("internal.service.account_service.AccountService.revoke_account_session", None)],
    },
    {
        "name": "revoke_other_account_sessions_success",
        "method": "post",
        "url": "/account/sessions/revoke-others",
        "kwargs": {"json": {}},
        "patches": [("internal.service.account_service.AccountService.revoke_other_account_sessions", None)],
    },
    # dataset/document/segment
    {
        "name": "create_dataset_success",
        "method": "post",
        "url": "/datasets",
        "kwargs": {"json": {"name": "ds", "icon": "https://a.com/a.png", "description": ""}},
        "patches": [("internal.service.dataset_service.DatasetService.create_dataset", None)],
    },
    {
        "name": "update_dataset_success",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}",
        "kwargs": {"json": {"name": "ds", "icon": "https://a.com/a.png", "description": ""}},
        "patches": [("internal.service.dataset_service.DatasetService.update_dataset", None)],
    },
    {
        "name": "delete_dataset_success",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/delete",
        "kwargs": {"json": {}},
        "patches": [("internal.service.dataset_service.DatasetService.delete_dataset", None)],
    },
    {
        "name": "dataset_hit_success",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/hit",
        "kwargs": {"json": {"query": "hello", "retrieval_strategy": "semantic", "k": 2, "score": 0.5}},
        "patches": [("internal.service.dataset_service.DatasetService.hit", {"result": []})],
    },
    {
        "name": "update_document_name_success",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/documents/{DOCUMENT_ID}/name",
        "kwargs": {"json": {"name": "doc-1"}},
        "patches": [("internal.service.document_service.DocumentService.update_document", None)],
    },
    {
        "name": "update_document_enabled_success",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/documents/{DOCUMENT_ID}/enabled",
        "kwargs": {"json": {"enabled": True}},
        "patches": [("internal.service.document_service.DocumentService.update_document_enabled", None)],
    },
    {
        "name": "delete_document_success",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/documents/{DOCUMENT_ID}/delete",
        "kwargs": {"json": {}},
        "patches": [("internal.service.document_service.DocumentService.delete_document", None)],
    },
    {
        "name": "create_segment_success",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/documents/{DOCUMENT_ID}/segments",
        "kwargs": {"json": {"content": "hello", "keywords": ["k1"]}},
        "patches": [("internal.service.segment_service.SegmentService.create_segment", None)],
    },
    {
        "name": "update_segment_success",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/documents/{DOCUMENT_ID}/segments/{SEGMENT_ID}",
        "kwargs": {"json": {"content": "hello", "keywords": ["k1"]}},
        "patches": [("internal.service.segment_service.SegmentService.update_segment", None)],
    },
    {
        "name": "update_segment_enabled_success",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/documents/{DOCUMENT_ID}/segments/{SEGMENT_ID}/enabled",
        "kwargs": {"json": {"enabled": True}},
        "patches": [("internal.service.segment_service.SegmentService.update_segment_enabled", None)],
    },
    {
        "name": "delete_segment_success",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/documents/{DOCUMENT_ID}/segments/{SEGMENT_ID}/delete",
        "kwargs": {"json": {}},
        "patches": [("internal.service.segment_service.SegmentService.delete_segment", None)],
    },
    # ai/assistant/audio/upload
    {
        "name": "optimize_prompt_success",
        "method": "post",
        "url": "/ai/optimize-prompt",
        "kwargs": {"json": {"prompt": "hello"}},
        "patches": [("internal.service.ai_service.AIService.optimize_prompt", Response(code=HttpCode.SUCCESS, data={"ok": True}))],
    },
    {
        "name": "suggested_questions_success",
        "method": "post",
        "url": "/ai/suggested-questions",
        "kwargs": {"json": {"message_id": MESSAGE_ID}},
        "patches": [("internal.service.ai_service.AIService.generate_suggested_questions_from_message_id", ["q1", "q2"])],
    },
    {
        "name": "openapi_schema_chat_success",
        "method": "post",
        "url": "/ai/openapi-schema-chat",
        "kwargs": {"json": {"question": "帮我生成天气schema"}},
        "patches": [(
            "internal.service.ai_service.AIService.openapi_schema_assistant_chat",
            Response(code=HttpCode.SUCCESS, data={"ok": True}),
        )],
    },
    {
        "name": "assistant_chat_success",
        "method": "post",
        "url": "/assistant-agent/chat",
        "kwargs": {"json": {"query": "hello"}},
        "patches": [("internal.service.assistant_agent_service.AssistantAgentService.chat", Response(code=HttpCode.SUCCESS, data={"ok": True}))],
    },
    {
        "name": "assistant_stop_success",
        "method": "post",
        "url": f"/assistant-agent/chat/{TASK_ID}/stop",
        "kwargs": {"json": {}},
        "patches": [("internal.service.assistant_agent_service.AssistantAgentService.stop_chat", None)],
    },
    {
        "name": "assistant_delete_conversation_success",
        "method": "post",
        "url": "/assistant-agent/delete-conversation",
        "kwargs": {"json": {}},
        "patches": [("internal.service.assistant_agent_service.AssistantAgentService.delete_conversation", None)],
    },
    {
        "name": "audio_to_text_success",
        "method": "post",
        "url": "/audio/audio-to-text",
        "kwargs": {"data": {"file": (BytesIO(b"wav"), "a.wav")}},
        "patches": [("internal.service.audio_service.AudioService.audio_to_text", "text")],
    },
    {
        "name": "message_to_audio_success",
        "method": "post",
        "url": "/audio/message-to-audio",
        "kwargs": {"json": {"message_id": MESSAGE_ID}},
        "patches": [("internal.service.audio_service.AudioService.message_to_audio", Response(code=HttpCode.SUCCESS, data={"ok": True}))],
    },
    {
        "name": "upload_file_success",
        "method": "post",
        "url": "/upload-files/file",
        "kwargs": {"data": {"file": (BytesIO(b"hello"), "a.txt")}},
        "patches": [("internal.service.cos_service.CosService.upload_file", _upload_file_obj())],
    },
    {
        "name": "upload_image_success",
        "method": "post",
        "url": "/upload-files/image",
        "kwargs": {"data": {"file": (BytesIO(b"png"), "a.png")}},
        "patches": [
            ("internal.service.cos_service.CosService.upload_file", _upload_file_obj()),
            ("internal.service.cos_service.CosService.get_file_url", "https://a.com/a.png"),
        ],
    },
    # openapi/web-app
    {
        "name": "openapi_chat_success",
        "method": "post",
        "url": "/openapi/chat",
        "kwargs": {"json": {"app_id": APP_ID, "query": "hello"}},
        "patches": [("internal.service.openapi_service.OpenAPIService.chat", Response(code=HttpCode.SUCCESS, data={"ok": True}))],
    },
    {
        "name": "stop_web_app_chat_success",
        "method": "post",
        "url": f"/web-apps/test-token/chat/{TASK_ID}/stop",
        "kwargs": {"json": {}},
        "patches": [("internal.service.web_app_service.WebAppService.stop_web_app_chat", None)],
    },
    {
        "name": "web_app_chat_success",
        "method": "post",
        "url": "/web-apps/test-token/chat",
        "kwargs": {"json": {"query": "hello"}},
        "patches": [("internal.service.web_app_service.WebAppService.web_app_chat", Response(code=HttpCode.SUCCESS, data={"ok": True}))],
    },
    # conversation
    {
        "name": "delete_conversation_success",
        "method": "post",
        "url": f"/conversations/{CONVERSATION_ID}/delete",
        "kwargs": {"json": {}},
        "patches": [("internal.service.conversation_service.ConversationService.delete_conversation", None)],
    },
    {
        "name": "delete_message_success",
        "method": "post",
        "url": f"/conversations/{CONVERSATION_ID}/messages/{MESSAGE_ID}/delete",
        "kwargs": {"json": {}},
        "patches": [("internal.service.conversation_service.ConversationService.delete_message", None)],
    },
    {
        "name": "delete_message_legacy_route_success",
        "method": "post",
        "url": f"/conversations/{CONVERSATION_ID}/messages/{MESSAGE_ID}",
        "kwargs": {"json": {}},
        "patches": [("internal.service.conversation_service.ConversationService.delete_message", None)],
    },
    {
        "name": "update_conversation_name_success",
        "method": "post",
        "url": f"/conversations/{CONVERSATION_ID}/name",
        "kwargs": {"json": {"name": "chat-1"}},
        "patches": [("internal.service.conversation_service.ConversationService.update_conversation", None)],
    },
    {
        "name": "update_conversation_is_pinned_success",
        "method": "post",
        "url": f"/conversations/{CONVERSATION_ID}/is-pinned",
        "kwargs": {"json": {"is_pinned": True}},
        "patches": [("internal.service.conversation_service.ConversationService.update_conversation", None)],
    },
    # api key
    {
        "name": "create_api_key_success",
        "method": "post",
        "url": "/openapi/api-keys",
        "kwargs": {"json": {"is_active": True, "remark": "ok"}},
        "patches": [("internal.service.api_key_service.ApiKeyService.create_api_key", None)],
    },
    {
        "name": "update_api_key_success",
        "method": "post",
        "url": f"/openapi/api-keys/{PROVIDER_ID}",
        "kwargs": {"json": {"is_active": True, "remark": "ok"}},
        "patches": [("internal.service.api_key_service.ApiKeyService.update_api_key", None)],
    },
    {
        "name": "update_api_key_is_active_success",
        "method": "post",
        "url": f"/openapi/api-keys/{PROVIDER_ID}/is-active",
        "kwargs": {"json": {"is_active": True}},
        "patches": [("internal.service.api_key_service.ApiKeyService.update_api_key", None)],
    },
    {
        "name": "delete_api_key_success",
        "method": "post",
        "url": f"/openapi/api-keys/{PROVIDER_ID}/delete",
        "kwargs": {"json": {}},
        "patches": [("internal.service.api_key_service.ApiKeyService.delete_api_key", None)],
    },
    # workflow/platform
    {
        "name": "create_workflow_success",
        "method": "post",
        "url": "/workflows",
        "kwargs": {
            "json": {
                "name": "wf",
                "tool_call_name": "tool_1",
                "icon": "https://a.com/a.png",
                "description": "desc",
            }
        },
        "patches": [("internal.service.workflow_service.WorkflowService.create_workflow", SimpleNamespace(id=WORKFLOW_ID))],
    },
    {
        "name": "update_workflow_success",
        "method": "post",
        "url": f"/workflows/{WORKFLOW_ID}",
        "kwargs": {
            "json": {
                "name": "wf",
                "tool_call_name": "tool_1",
                "icon": "https://a.com/a.png",
                "description": "desc",
            }
        },
        "patches": [("internal.service.workflow_service.WorkflowService.update_workflow", None)],
    },
    {
        "name": "delete_workflow_success",
        "method": "post",
        "url": f"/workflows/{WORKFLOW_ID}/delete",
        "kwargs": {"json": {}},
        "patches": [("internal.service.workflow_service.WorkflowService.delete_workflow", None)],
    },
    {
        "name": "update_workflow_draft_graph_success",
        "method": "post",
        "url": f"/workflows/{WORKFLOW_ID}/draft-graph",
        "kwargs": {"json": {"nodes": [], "edges": []}},
        "patches": [("internal.service.workflow_service.WorkflowService.update_draft_graph", None)],
    },
    {
        "name": "publish_workflow_success",
        "method": "post",
        "url": f"/workflows/{WORKFLOW_ID}/publish",
        "kwargs": {"json": {}},
        "patches": [("internal.service.workflow_service.WorkflowService.publish_workflow", None)],
    },
    {
        "name": "cancel_publish_workflow_success",
        "method": "post",
        "url": f"/workflows/{WORKFLOW_ID}/cancel-publish",
        "kwargs": {"json": {}},
        "patches": [("internal.service.workflow_service.WorkflowService.cancel_publish_workflow", None)],
    },
    {
        "name": "update_platform_wechat_config_success",
        "method": "post",
        "url": f"/platform/{APP_ID}/wechat-config",
        "kwargs": {"json": {"wechat_app_id": "id", "wechat_app_secret": "secret", "wechat_token": "token"}},
        "patches": [("internal.service.platform_service.PlatformService.update_wechat_config", None)],
    },
]

CASES += [
    # GET detail/list serialization
    {
        "name": "get_app_detail_serialization_success",
        "method": "get",
        "url": f"/apps/{APP_ID}",
        "kwargs": {},
        "patches": [("internal.service.app_service.AppService.get_app", _app_obj())],
        "assertion": _assert_get_app,
    },
    {
        "name": "get_apps_with_page_serialization_success",
        "method": "get",
        "url": "/apps",
        "kwargs": {},
        "patches": [("internal.service.app_service.AppService.get_apps_with_page", ([_app_obj()], _paginator()))],
        "assertion": _assert_get_apps_with_page,
    },
    {
        "name": "get_publish_histories_with_page_serialization_success",
        "method": "get",
        "url": f"/apps/{APP_ID}/publish-histories",
        "kwargs": {},
        "patches": [("internal.service.app_service.AppService.get_publish_histories_with_page", ([_history_obj()], _paginator()))],
        "assertion": _assert_publish_histories_with_page,
    },
    {
        "name": "get_versions_success",
        "method": "get",
        "url": f"/apps/{APP_ID}/versions",
        "kwargs": {},
        "patches": [("internal.service.app_service.AppService.get_versions", [_draft_version_obj(), _history_obj()])],
        "assertion": _assert_get_versions,
    },
    {
        "name": "get_debug_messages_with_page_serialization_success",
        "method": "get",
        "url": f"/apps/{APP_ID}/conversations/messages",
        "kwargs": {},
        "patches": [("internal.service.app_service.AppService.get_debug_conversation_messages_with_page", ([_message_obj()], _paginator()))],
        "assertion": _assert_message_page,
    },
    {
        "name": "get_workflow_detail_serialization_success",
        "method": "get",
        "url": f"/workflows/{WORKFLOW_ID}",
        "kwargs": {},
        "patches": [("internal.service.workflow_service.WorkflowService.get_workflow", _workflow_obj())],
        "assertion": _assert_get_workflow,
    },
    {
        "name": "get_workflow_draft_graph_success",
        "method": "get",
        "url": f"/workflows/{WORKFLOW_ID}/draft-graph",
        "kwargs": {},
        "patches": [("internal.service.workflow_service.WorkflowService.get_draft_graph", {"nodes": [{"node_type": "start"}], "edges": []})],
        "assertion": _assert_get_workflow_draft_graph,
    },
    {
        "name": "get_workflows_with_page_serialization_success",
        "method": "get",
        "url": "/workflows",
        "kwargs": {},
        "patches": [("internal.service.workflow_service.WorkflowService.get_workflows_with_page", ([_workflow_obj()], _paginator()))],
        "assertion": _assert_get_workflows_with_page,
    },
    {
        "name": "get_dataset_detail_serialization_success",
        "method": "get",
        "url": f"/datasets/{DATASET_ID}",
        "kwargs": {},
        "patches": [("internal.service.dataset_service.DatasetService.get_dataset", _dataset_obj())],
        "assertion": _assert_get_dataset,
    },
    {
        "name": "get_datasets_with_page_serialization_success",
        "method": "get",
        "url": "/datasets",
        "kwargs": {},
        "patches": [("internal.service.dataset_service.DatasetService.get_datasets_with_page", ([_dataset_obj()], _paginator()))],
        "assertion": _assert_get_datasets_with_page,
    },
    {
        "name": "get_dataset_queries_serialization_success",
        "method": "get",
        "url": f"/datasets/{DATASET_ID}/queries",
        "kwargs": {},
        "patches": [("internal.service.dataset_service.DatasetService.get_dataset_queries", [_dataset_query_obj()])],
        "assertion": _assert_get_dataset_queries,
    },
    {
        "name": "get_document_detail_serialization_success",
        "method": "get",
        "url": f"/datasets/{DATASET_ID}/documents/{DOCUMENT_ID}",
        "kwargs": {},
        "patches": [("internal.service.document_service.DocumentService.get_document", _document_obj())],
        "assertion": _assert_get_document,
    },
    {
        "name": "get_documents_with_page_serialization_success",
        "method": "get",
        "url": f"/datasets/{DATASET_ID}/documents",
        "kwargs": {},
        "patches": [("internal.service.document_service.DocumentService.get_documents_with_page", ([_document_obj()], _paginator()))],
        "assertion": _assert_get_documents_with_page,
    },
    {
        "name": "get_segment_detail_serialization_success",
        "method": "get",
        "url": f"/datasets/{DATASET_ID}/documents/{DOCUMENT_ID}/segments/{SEGMENT_ID}",
        "kwargs": {},
        "patches": [("internal.service.segment_service.SegmentService.get_segment", _segment_obj())],
        "assertion": _assert_get_segment,
    },
    {
        "name": "get_segments_with_page_serialization_success",
        "method": "get",
        "url": f"/datasets/{DATASET_ID}/documents/{DOCUMENT_ID}/segments",
        "kwargs": {},
        "patches": [("internal.service.segment_service.SegmentService.get_segments_with_page", ([_segment_obj()], _paginator()))],
        "assertion": _assert_get_segments_with_page,
    },
    {
        "name": "get_api_tool_provider_detail_serialization_success",
        "method": "get",
        "url": f"/api-tools/{PROVIDER_ID}",
        "kwargs": {},
        "patches": [("internal.service.api_tool_service.ApiToolService.get_api_tool_provider", _api_tool_provider_obj())],
        "assertion": _assert_get_api_tool_provider,
    },
    {
        "name": "get_api_tools_with_page_serialization_success",
        "method": "get",
        "url": "/api-tools",
        "kwargs": {},
        "patches": [("internal.service.api_tool_service.ApiToolService.get_api_tool_providers_wiith_page", ([_api_tool_provider_obj()], _paginator()))],
        "assertion": _assert_get_api_tools_with_page,
    },
    {
        "name": "get_api_tool_detail_serialization_success",
        "method": "get",
        "url": f"/api-tools/{PROVIDER_ID}/tools/get_weather",
        "kwargs": {},
        "patches": [("internal.service.api_tool_service.ApiToolService.get_api_tool", _api_tool_obj())],
        "assertion": _assert_get_api_tool,
    },
    {
        "name": "get_api_keys_with_page_serialization_success",
        "method": "get",
        "url": "/openapi/api-keys",
        "kwargs": {},
        "patches": [("internal.service.api_key_service.ApiKeyService.get_api_keys_with_page", ([_api_key_obj()], _paginator()))],
        "assertion": _assert_get_api_keys_with_page,
    },
    {
        "name": "get_conversation_messages_with_page_serialization_success",
        "method": "get",
        "url": f"/conversations/{CONVERSATION_ID}/messages",
        "kwargs": {},
        "patches": [("internal.service.conversation_service.ConversationService.get_conversation_messages_with_page", ([_message_obj()], _paginator()))],
        "assertion": _assert_message_page,
    },
    {
        "name": "get_web_app_conversations_serialization_success",
        "method": "get",
        "url": "/web-apps/test-token/conversations",
        "kwargs": {},
        "patches": [("internal.service.web_app_service.WebAppService.get_conversations", [_conversation_obj()])],
        "assertion": _assert_get_web_app_conversations,
    },
]


class TestSuccessMatrix:
    @pytest.fixture
    def http_client(self, app):
        """使用独立客户端，避免触发全局 client->db 自动事务夹具。"""
        with app.test_client() as client:
            yield client

    @pytest.mark.parametrize("case", CASES, ids=[item["name"] for item in CASES])
    def test_success_paths_without_db_side_effect(self, case, http_client, monkeypatch):
        for target, return_value in case["patches"]:
            monkeypatch.setattr(
                target,
                (lambda *args, _value=return_value, **kwargs: _value),
            )

        method = getattr(http_client, case["method"])
        resp = method(case["url"], **case["kwargs"])

        assert resp.status_code == 200
        assert resp.json["code"] == HttpCode.SUCCESS
        if "assertion" in case:
            case["assertion"](resp.json["data"])
