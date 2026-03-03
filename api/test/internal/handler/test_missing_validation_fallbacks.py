from types import SimpleNamespace

import pytest

from pkg.response import HttpCode


APP_ID = "00000000-0000-0000-0000-000000000001"
API_KEY_ID = "00000000-0000-0000-0000-000000000002"
CONVERSATION_ID = "00000000-0000-0000-0000-000000000003"
DATASET_ID = "00000000-0000-0000-0000-000000000004"
DOCUMENT_ID = "00000000-0000-0000-0000-000000000005"
SEGMENT_ID = "00000000-0000-0000-0000-000000000006"


CASES = [
    {
        "name": "api_key_is_active_validation_fallback",
        "method": "post",
        "url": f"/openapi/api-keys/{API_KEY_ID}/is-active",
        "patch_target": "internal.handler.api_key_handler.UpdateApiKeyIsActiveReq",
    },
    {
        "name": "app_summary_validation_fallback",
        "method": "post",
        "url": f"/apps/{APP_ID}/summary",
        "patch_target": "internal.handler.app_handler.UpdateDebugConversationSummaryReq",
    },
    {
        "name": "assistant_intro_validation_fallback",
        "method": "post",
        "url": "/assistant-agent/introduction",
        "patch_target": "internal.handler.assistant_agent_handler.AssistantAgentGenerateIntroduction",
    },
    {
        "name": "conversation_is_pinned_validation_fallback",
        "method": "post",
        "url": f"/conversations/{CONVERSATION_ID}/is-pinned",
        "patch_target": "internal.handler.conversation_handler.UpdateConversationIsPinnedReq",
    },
    {
        "name": "document_enabled_validation_fallback",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/documents/{DOCUMENT_ID}/enabled",
        "patch_target": "internal.handler.document_handler.UpdateDocumentEnabledReq",
    },
    {
        "name": "platform_wechat_config_validation_fallback",
        "method": "post",
        "url": f"/platform/{APP_ID}/wechat-config",
        "patch_target": "internal.handler.platform_handler.UpdateWechatConfigReq",
    },
    {
        "name": "segment_enabled_validation_fallback",
        "method": "post",
        "url": f"/datasets/{DATASET_ID}/documents/{DOCUMENT_ID}/segments/{SEGMENT_ID}/enabled",
        "patch_target": "internal.handler.segment_handler.UpdateSegmentEnabledReq",
    },
    {
        "name": "web_app_conversations_validation_fallback",
        "method": "get",
        "url": "/web-apps/test-token/conversations",
        "patch_target": "internal.handler.web_app_handler.GetConversationsReq",
    },
]


class TestMissingValidationFallbacks:
    @pytest.fixture
    def http_client(self, app):
        with app.test_client() as client:
            yield client

    @pytest.mark.parametrize("case", CASES, ids=[item["name"] for item in CASES])
    def test_should_return_validate_error_when_schema_fails(self, case, http_client, monkeypatch):
        # 这些分支在真实 schema 下很难通过 HTTP 入参触发（部分字段全为 Optional/Boolean 默认值）。
        # 因此这里直接替换 schema 实例，验证 handler 在 validate=False 时的统一兜底行为。
        invalid_req = SimpleNamespace(validate=lambda: False, errors={"mock": ["mock validate error"]})
        monkeypatch.setattr(case["patch_target"], lambda *_args, **_kwargs: invalid_req)

        method = getattr(http_client, case["method"])
        resp = method(case["url"])

        assert resp.status_code == 200
        assert resp.json["code"] == HttpCode.VALIDATE_ERROR
        assert resp.json["message"] == "mock validate error"
