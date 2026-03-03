from __future__ import annotations

from uuid import uuid4

import pytest

from internal.entity.app_entity import AppStatus
from internal.schema.app_schema import (
    CreateAppReq,
    DebugChatReq,
    FallbackHistoryToDraftReq,
    GetAppResp,
    GetAppsWithPageResp,
    GetDebugConversationMessagesWithPageReq,
    GetDebugConversationMessagesWithPageResp,
    GetPublishHistoriesWithPageResp,
)
from internal.schema.assistant_agent_schema import (
    AssistantAgentChat,
    AssistantAgentGenerateIntroduction,
    GetAssistantAgentMessagesWithPageReq,
    GetAssistantAgentMessagesWithPageResp,
)
from internal.schema.conversation_schema import (
    GetConversationMessagesWithPageReq,
    GetConversationMessagesWithPageResp,
    UpdateConversationIsPinnedReq,
    UpdateConversationNameReq,
)
from internal.schema.openapi_schema import OpenAPIChatReq
from internal.schema.web_app_schema import (
    GetConversationsReq,
    GetConversationsResp,
    GetWebAppResp,
    WebAppChatReq,
)
from test.internal.schema.utils import ns, utc_dt


def _validate_form(form_request, form_cls, *, data=None, json=None, content_type=None):
    with form_request(data=data, json=json, content_type=content_type):
        form = form_cls(meta={"csrf": False})
        return form.validate(), form


def _message_payload():
    thought = ns(
        id=uuid4(),
        position=1,
        event="tool_call",
        thought="thinking",
        observation="obs",
        tool="search",
        tool_input='{"q":"x"}',
        latency=0.33,
        created_at=utc_dt(2024, 1, 1, 1, 0, 0),
    )
    return ns(
        id=uuid4(),
        conversation_id=uuid4(),
        query="hello",
        image_urls=["https://img.example.com/1.png"],
        answer="world",
        total_token_count=10,
        latency=0.22,
        agent_thoughts=[thought],
        suggested_questions=["q1"],
        created_at=utc_dt(2024, 1, 1, 2, 0, 0),
    )


def test_create_app_req_should_validate_required_fields(form_request):
    ok, form = _validate_form(
        form_request,
        CreateAppReq,
        data={
            "name": "助手",
            "icon": "https://img.example.com/app.png",
            "description": "desc",
        },
    )
    assert ok, form.errors

    ok, form = _validate_form(
        form_request,
        CreateAppReq,
        data={
            "name": "",
            "icon": "bad-url",
            "description": "desc",
        },
    )
    assert not ok
    assert "name" in form.errors
    assert "icon" in form.errors


@pytest.mark.parametrize(
    ("status", "expected_prompt", "expected_model"),
    [
        (
            AppStatus.PUBLISHED.value,
            "published-prompt",
            {"provider": "openai", "model": "gpt-4o-mini"},
        ),
        (
            AppStatus.DRAFT.value,
            "draft-prompt",
            {"provider": "azure-openai", "model": "gpt-4o"},
        ),
    ],
)
def test_get_apps_with_page_resp_should_select_config_by_status(status, expected_prompt, expected_model):
    app = ns(
        id=uuid4(),
        name="app",
        icon="https://img.example.com/app.png",
        description="desc",
        status=status,
        app_config=ns(
            preset_prompt="published-prompt",
            model_config={"provider": "openai", "model": "gpt-4o-mini", "extra": "ignored"},
        ),
        draft_app_config=ns(
            preset_prompt="draft-prompt",
            model_config={"provider": "azure-openai", "model": "gpt-4o", "extra": "ignored"},
            updated_at=utc_dt(2024, 1, 3, 0, 0, 0),
        ),
        updated_at=utc_dt(2024, 1, 2, 0, 0, 0),
        created_at=utc_dt(2024, 1, 1, 0, 0, 0),
    )

    data = GetAppsWithPageResp().dump(app)
    assert data["preset_prompt"] == expected_prompt
    assert data["model_config"] == expected_model


def test_get_app_resp_should_render_empty_debug_conversation_id_when_none():
    app = ns(
        id=uuid4(),
        debug_conversation_id=None,
        name="app",
        icon="https://img.example.com/app.png",
        description="desc",
        status=AppStatus.DRAFT.value,
        is_public=False,
        category="general",
        draft_app_config=ns(updated_at=utc_dt(2024, 1, 2, 0, 0, 0)),
        updated_at=utc_dt(2024, 1, 3, 0, 0, 0),
        created_at=utc_dt(2024, 1, 1, 0, 0, 0),
    )
    data = GetAppResp().dump(app)
    assert data["debug_conversation_id"] == ""


def test_get_publish_histories_resp_should_dump_version_payload():
    version = ns(
        id=uuid4(),
        version=2,
        created_at=utc_dt(2024, 1, 1, 0, 0, 0),
    )
    data = GetPublishHistoriesWithPageResp().dump(version)
    assert data["version"] == 2
    assert data["created_at"] == int(utc_dt(2024, 1, 1, 0, 0, 0).timestamp())


def test_fallback_history_to_draft_req_should_validate_uuid(form_request):
    ok, form = _validate_form(
        form_request,
        FallbackHistoryToDraftReq,
        data={"app_config_version_id": str(uuid4())},
    )
    assert ok, form.errors

    ok, form = _validate_form(
        form_request,
        FallbackHistoryToDraftReq,
        data={"app_config_version_id": "bad-id"},
    )
    assert not ok
    assert "app_config_version_id" in form.errors


def test_debug_chat_req_should_validate_image_urls(form_request):
    ok, form = _validate_form(
        form_request,
        DebugChatReq,
        data={"query": "hello", "image_urls": ["https://img.example.com/1.png"]},
    )
    assert ok, form.errors

    ok, form = _validate_form(
        form_request,
        DebugChatReq,
        data={"query": "hello", "image_urls": ["https://img.example.com/1.png"] * 6},
    )
    assert not ok
    assert "image_urls" in form.errors

    ok, form = _validate_form(
        form_request,
        DebugChatReq,
        data={"query": "hello", "image_urls": ["not-url"]},
    )
    assert not ok
    assert "image_urls" in form.errors


def test_debug_chat_req_validate_image_urls_should_ignore_non_list_input(form_request):
    with form_request():
        form = DebugChatReq(meta={"csrf": False})
        form.image_urls.data = None  # type: ignore[assignment]
        assert form.validate_image_urls(form.image_urls) == []


def test_get_debug_conversation_messages_with_page_req_should_validate_cursor(form_request):
    ok, form = _validate_form(form_request, GetDebugConversationMessagesWithPageReq, data={"created_at": "0"})
    assert ok, form.errors

    ok, form = _validate_form(form_request, GetDebugConversationMessagesWithPageReq, data={"created_at": "-1"})
    assert not ok
    assert "created_at" in form.errors


def test_get_debug_conversation_messages_with_page_resp_should_dump_agent_thoughts():
    data = GetDebugConversationMessagesWithPageResp().dump(_message_payload())
    assert data["query"] == "hello"
    assert len(data["agent_thoughts"]) == 1
    assert "created_at" in data["agent_thoughts"][0]


def test_conversation_schema_should_validate_and_dump(form_request):
    ok, form = _validate_form(form_request, GetConversationMessagesWithPageReq, data={"created_at": "0"})
    assert ok, form.errors

    ok, form = _validate_form(form_request, GetConversationMessagesWithPageReq, data={"created_at": "-1"})
    assert not ok
    assert "created_at" in form.errors

    payload = GetConversationMessagesWithPageResp().dump(_message_payload())
    assert payload["answer"] == "world"
    assert payload["total_token_count"] == 10

    ok, form = _validate_form(form_request, UpdateConversationNameReq, data={"name": "n" * 100})
    assert ok, form.errors
    ok, form = _validate_form(form_request, UpdateConversationNameReq, data={"name": "n" * 101})
    assert not ok
    assert "name" in form.errors

    ok, form = _validate_form(form_request, UpdateConversationIsPinnedReq, data={"is_pinned": "y"})
    assert ok, form.errors
    assert form.is_pinned.data is True


def test_web_app_schema_should_validate_and_dump(form_request):
    app = ns(
        id=uuid4(),
        icon="https://img.example.com/app.png",
        name="app",
        description="desc",
        app_config=ns(
            opening_statement="hi",
            opening_questions=["q1", "q2"],
            suggested_after_answer={"enable": True},
        ),
    )
    app_payload = GetWebAppResp().dump(app)
    assert app_payload["app_config"]["opening_statement"] == "hi"

    ok, form = _validate_form(
        form_request,
        WebAppChatReq,
        data={
            "conversation_id": str(uuid4()),
            "query": "hello",
            "image_urls": ["https://img.example.com/1.png"],
        },
    )
    assert ok, form.errors

    ok, form = _validate_form(
        form_request,
        WebAppChatReq,
        data={"conversation_id": "bad-id", "query": "hello"},
    )
    assert not ok
    assert "conversation_id" in form.errors

    ok, form = _validate_form(form_request, GetConversationsReq, data={"is_pinned": "y"})
    assert ok, form.errors
    assert form.is_pinned.data is True

    conversation = ns(
        id=uuid4(),
        name="conv",
        summary="summary",
        created_at=utc_dt(2024, 1, 1, 0, 0, 0),
    )
    conv_payload = GetConversationsResp().dump(conversation)
    assert conv_payload["name"] == "conv"
    assert conv_payload["created_at"] == int(utc_dt(2024, 1, 1, 0, 0, 0).timestamp())


def test_openapi_chat_req_should_validate_conversation_and_images(form_request):
    ok, form = _validate_form(
        form_request,
        OpenAPIChatReq,
        data={
            "app_id": str(uuid4()),
            "end_user_id": str(uuid4()),
            "conversation_id": str(uuid4()),
            "query": "hello",
            "image_urls": ["https://img.example.com/1.png"],
            "stream": "y",
        },
    )
    assert ok, form.errors

    ok, form = _validate_form(
        form_request,
        OpenAPIChatReq,
        data={
            "app_id": str(uuid4()),
            "conversation_id": "bad-id",
            "query": "hello",
        },
    )
    assert not ok
    assert "conversation_id" in form.errors

    ok, form = _validate_form(
        form_request,
        OpenAPIChatReq,
        data={
            "app_id": str(uuid4()),
            "conversation_id": str(uuid4()),
            "query": "hello",
        },
    )
    assert not ok
    assert "conversation_id" in form.errors

    ok, form = _validate_form(
        form_request,
        OpenAPIChatReq,
        data={
            "app_id": str(uuid4()),
            "query": "hello",
            "image_urls": ["https://img.example.com/1.png"] * 6,
        },
    )
    assert not ok
    assert "image_urls" in form.errors

    ok, form = _validate_form(
        form_request,
        OpenAPIChatReq,
        data={
            "app_id": str(uuid4()),
            "query": "hello",
            "image_urls": ["bad-url"],
        },
    )
    assert not ok
    assert "image_urls" in form.errors


def test_openapi_chat_req_validate_image_urls_should_ignore_non_list_input(form_request):
    with form_request():
        form = OpenAPIChatReq(meta={"csrf": False})
        form.image_urls.data = None  # type: ignore[assignment]
        assert form.validate_image_urls(form.image_urls) == []


def test_assistant_agent_schema_should_validate_and_dump(form_request):
    ok, form = _validate_form(
        form_request,
        AssistantAgentChat,
        data={"query": "hello", "image_urls": ["https://img.example.com/1.png"]},
    )
    assert ok, form.errors

    ok, form = _validate_form(
        form_request,
        AssistantAgentChat,
        data={"query": "hello", "image_urls": ["bad-url"]},
    )
    assert not ok
    assert "image_urls" in form.errors

    ok, form = _validate_form(
        form_request,
        AssistantAgentChat,
        data={"query": "hello", "image_urls": ["https://img.example.com/1.png"] * 6},
    )
    assert not ok
    assert "image_urls" in form.errors

    ok, form = _validate_form(form_request, GetAssistantAgentMessagesWithPageReq, data={"created_at": "0"})
    assert ok, form.errors

    ok, form = _validate_form(form_request, GetAssistantAgentMessagesWithPageReq, data={"created_at": "-1"})
    assert not ok
    assert "created_at" in form.errors

    payload = GetAssistantAgentMessagesWithPageResp().dump(_message_payload())
    assert payload["answer"] == "world"
    assert len(payload["agent_thoughts"]) == 1

    ok, form = _validate_form(form_request, AssistantAgentGenerateIntroduction, data={})
    assert ok, form.errors


def test_assistant_agent_chat_validate_image_urls_should_ignore_non_list_input(form_request):
    with form_request():
        form = AssistantAgentChat(meta={"csrf": False})
        form.image_urls.data = None  # type: ignore[assignment]
        assert form.validate_image_urls(form.image_urls) == []


def test_web_app_chat_req_should_validate_image_url_length_and_format(form_request):
    ok, form = _validate_form(
        form_request,
        WebAppChatReq,
        data={"query": "hello", "image_urls": ["https://img.example.com/1.png"] * 6},
    )
    assert not ok
    assert "image_urls" in form.errors

    ok, form = _validate_form(
        form_request,
        WebAppChatReq,
        data={"query": "hello", "image_urls": ["bad-url"]},
    )
    assert not ok
    assert "image_urls" in form.errors


def test_web_app_chat_req_validate_image_urls_should_ignore_non_list_input(form_request):
    with form_request():
        form = WebAppChatReq(meta={"csrf": False})
        form.image_urls.data = None  # type: ignore[assignment]
        assert form.validate_image_urls(form.image_urls) == []
