from datetime import datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from internal.handler.web_app_handler import WebAppHandler
from pkg.response import HttpCode, Response


APP_ID = "00000000-0000-0000-0000-000000000001"
WORKFLOW_ID = "00000000-0000-0000-0000-000000000002"
MESSAGE_ID = "00000000-0000-0000-0000-000000000003"
DATASET_ID = "00000000-0000-0000-0000-000000000004"
CONVERSATION_ID = "00000000-0000-0000-0000-000000000005"
TASK_ID = "00000000-0000-0000-0000-000000000006"


def _current_user_stub():
    return SimpleNamespace(
        id=UUID(APP_ID),
        name="tester",
        email="tester@example.com",
        avatar="https://a.com/avatar.png",
        last_login_at=datetime(2024, 1, 1, 0, 0, 0),
        last_login_ip="127.0.0.1",
        created_at=datetime(2024, 1, 1, 0, 0, 0),
    )


def _assert_ping(data: dict):
    assert data["pong"] == "success"


def _assert_account(data: dict):
    assert data["id"] == APP_ID
    assert data["email"] == "tester@example.com"


def _assert_app_published_config(data: dict):
    assert data["model_config"]["provider"] == "openai"
    assert data["model_config"]["model"] == "gpt-4o-mini"


def _assert_draft_app_config(data: dict):
    assert data["model_config"]["provider"] == "openai"
    assert data["dialog_round"] == 6


def _assert_debug_summary(data: dict):
    assert data["summary"] == "memory-summary"


def _assert_analysis(data: dict):
    assert data["total_messages"]["data"] == 12
    assert data["active_accounts"]["pop"] == 0.5


def _assert_documents_status(data: list):
    assert data[0]["status"] == "completed"


def _assert_language_models(data: list):
    assert data[0]["name"] == "openai"


def _assert_language_model(data: dict):
    assert data["name"] == "gpt-4o-mini"


def _assert_web_app(data: dict):
    assert data["id"] == APP_ID
    assert data["name"] == "web"


def _assert_assistant_intro(data: dict):
    assert data["intro"] == "hello"


def _assert_workflow_debug(data: dict):
    assert data["debug"] == "ok"


def _assert_text_to_audio(data: dict):
    assert data["event"] == "tts"


def _assert_conversation_name(data: dict):
    assert data["name"] == "会话标题"


def _assert_wechat_config(data: dict):
    assert data["app_id"] == APP_ID
    assert data["url"].endswith(f"/wechat/{APP_ID}")
    assert data["wechat_app_id"] == "wx-app-id"


JSON_CASES = [
    {
        "name": "ping_success",
        "method": "get",
        "url": "/ping",
        "kwargs": {},
        "patches": [],
        "assertion": _assert_ping,
    },
    {
        "name": "account_profile_success",
        "method": "get",
        "url": "/account",
        "kwargs": {},
        "raw_patches": [("internal.handler.account_handler.current_user", _current_user_stub())],
        "patches": [],
        "assertion": _assert_account,
    },
    {
        "name": "auth_logout_success",
        "method": "post",
        "url": "/auth/logout",
        "kwargs": {"json": {}},
        "raw_patches": [("internal.handler.auth_handler.logout_user", lambda: None)],
        "patches": [],
    },
    {
        "name": "get_published_config_success",
        "method": "get",
        "url": f"/apps/{APP_ID}/published-config",
        "kwargs": {},
        "patches": [
            (
                "internal.service.app_service.AppService.get_published_config",
                {"model_config": {"provider": "openai", "model": "gpt-4o-mini"}},
            )
        ],
        "assertion": _assert_app_published_config,
    },
    {
        "name": "get_draft_app_config_success",
        "method": "get",
        "url": f"/apps/{APP_ID}/draft-app-config",
        "kwargs": {},
        "patches": [
            (
                "internal.service.app_service.AppService.get_draft_app_config",
                {
                    "model_config": {"provider": "openai", "model": "gpt-4o-mini"},
                    "dialog_round": 6,
                },
            )
        ],
        "assertion": _assert_draft_app_config,
    },
    {
        "name": "get_debug_summary_success",
        "method": "get",
        "url": f"/apps/{APP_ID}/summary",
        "kwargs": {},
        "patches": [
            (
                "internal.service.app_service.AppService.get_debug_conversation_summary",
                "memory-summary",
            )
        ],
        "assertion": _assert_debug_summary,
    },
    {
        "name": "analysis_success",
        "method": "get",
        "url": f"/analysis/{APP_ID}",
        "kwargs": {},
        "patches": [
            (
                "internal.service.analysis_service.AnalysisService.get_app_analysis",
                {
                    "total_messages": {"data": 12, "pop": 0.1},
                    "active_accounts": {"data": 3, "pop": 0.5},
                },
            )
        ],
        "assertion": _assert_analysis,
    },
    {
        "name": "assistant_generate_intro_success",
        "method": "post",
        "url": "/assistant-agent/introduction",
        "kwargs": {"json": {}},
        "patches": [
            (
                "internal.service.assistant_agent_service.AssistantAgentService.generate_introduction",
                Response(code=HttpCode.SUCCESS, data={"intro": "hello"}),
            )
        ],
        "assertion": _assert_assistant_intro,
    },
    {
        "name": "audio_text_to_audio_success",
        "method": "post",
        "url": "/audio/text-to-audio",
        "kwargs": {"json": {"message_id": MESSAGE_ID, "text": "你好"}},
        "patches": [
            (
                "internal.service.audio_service.AudioService.text_to_audio",
                Response(code=HttpCode.SUCCESS, data={"event": "tts"}),
            )
        ],
        "assertion": _assert_text_to_audio,
    },
    {
        "name": "get_documents_status_success",
        "method": "get",
        "url": f"/datasets/{DATASET_ID}/documents/batch/batch-1",
        "kwargs": {},
        "patches": [
            (
                "internal.service.document_service.DocumentService.get_documents_status",
                [{"id": "doc-1", "status": "completed"}],
            )
        ],
        "assertion": _assert_documents_status,
    },
    {
        "name": "get_language_models_success",
        "method": "get",
        "url": "/language-models",
        "kwargs": {},
        "patches": [
            (
                "internal.service.language_model_service.LanguageModelService.get_language_models",
                [{"name": "openai", "models": []}],
            )
        ],
        "assertion": _assert_language_models,
    },
    {
        "name": "get_language_model_success",
        "method": "get",
        "url": "/language-models/openai/gpt-4o-mini",
        "kwargs": {},
        "patches": [
            (
                "internal.service.language_model_service.LanguageModelService.get_language_model",
                {"name": "gpt-4o-mini", "model_type": "chat"},
            )
        ],
        "assertion": _assert_language_model,
    },
    {
        "name": "get_web_app_success",
        "method": "get",
        "url": "/web-apps/test-token",
        "kwargs": {},
        "patches": [
            (
                "internal.service.web_app_service.WebAppService.get_web_app_info",
                {"id": APP_ID, "name": "web"},
            )
        ],
        "assertion": _assert_web_app,
    },
    {
        "name": "get_conversation_name_success",
        "method": "get",
        "url": f"/conversations/{CONVERSATION_ID}/name",
        "kwargs": {},
        "patches": [
            (
                "internal.service.conversation_service.ConversationService.get_conversation",
                SimpleNamespace(name="会话标题"),
            )
        ],
        "assertion": _assert_conversation_name,
    },
    {
        "name": "get_wechat_config_success",
        "method": "get",
        "url": f"/platform/{APP_ID}/wechat-config",
        "kwargs": {},
        "patches": [
            (
                "internal.service.platform_service.PlatformService.get_wechat_config",
                SimpleNamespace(
                    app_id=UUID(APP_ID),
                    wechat_app_id="wx-app-id",
                    wechat_app_secret="wx-secret",
                    wechat_token="wx-token",
                    status="configured",
                    updated_at=datetime(2024, 1, 1, 0, 0, 0),
                    created_at=datetime(2024, 1, 1, 0, 0, 0),
                ),
            )
        ],
        "assertion": _assert_wechat_config,
    },
    {
        "name": "workflow_debug_success",
        "method": "post",
        "url": f"/workflows/{WORKFLOW_ID}/debug",
        "kwargs": {"json": {"input": "value"}},
        "patches": [
            (
                "internal.service.workflow_service.WorkflowService.debug_workflow",
                Response(code=HttpCode.SUCCESS, data={"debug": "ok"}),
            )
        ],
        "assertion": _assert_workflow_debug,
    },
]


class TestRemainingHandlerMatrix:
    """补齐剩余路由的成功路径测试，统一验证 handler 到 service 的委托关系。"""

    @pytest.fixture
    def http_client(self, app):
        """使用独立命名的测试客户端，避免触发全局 client->db 自动回滚夹具。"""
        with app.test_client() as client:
            yield client

    @pytest.mark.parametrize("case", JSON_CASES, ids=[item["name"] for item in JSON_CASES])
    def test_should_cover_remaining_json_routes(self, case, http_client, monkeypatch):
        for target, value in case.get("raw_patches", []):
            monkeypatch.setattr(target, value)

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

    def test_should_return_binary_icon_for_language_model_provider(self, http_client, monkeypatch):
        monkeypatch.setattr(
            "internal.service.language_model_service.LanguageModelService.get_language_model_icon",
            lambda *_args, **_kwargs: (b"icon-bytes", "image/png"),
        )

        resp = http_client.get("/language-models/openai/icon")

        assert resp.status_code == 200
        assert resp.mimetype == "image/png"
        assert resp.data == b"icon-bytes"

    def test_should_delegate_wechat_get_request_to_service(self, http_client, monkeypatch):
        captures = {}

        # 被 patch 到类方法时，首参数是实例 self，第二个参数才是 app_id。
        def _wechat(_self, app_id):
            captures["app_id"] = app_id
            return "wechat-get-ok"

        monkeypatch.setattr(
            "internal.service.wechat_service.WechatService.wechat",
            _wechat,
        )

        resp = http_client.get(f"/wechat/{APP_ID}")

        assert resp.status_code == 200
        assert resp.data.decode("utf-8") == "wechat-get-ok"
        assert captures["app_id"] == UUID(APP_ID)

    def test_should_delegate_wechat_post_request_to_service(self, http_client, monkeypatch):
        captures = {}

        # 被 patch 到类方法时，首参数是实例 self，第二个参数才是 app_id。
        def _wechat(_self, app_id):
            captures["app_id"] = app_id
            return "wechat-post-ok"

        monkeypatch.setattr(
            "internal.service.wechat_service.WechatService.wechat",
            _wechat,
        )

        resp = http_client.post(f"/wechat/{APP_ID}", data="<xml></xml>", content_type="application/xml")

        assert resp.status_code == 200
        assert resp.data.decode("utf-8") == "wechat-post-ok"
        assert captures["app_id"] == UUID(APP_ID)

    def test_should_delegate_assistant_stop_with_task_id_and_current_user(self, http_client, monkeypatch):
        current_user_stub = SimpleNamespace(id=UUID(APP_ID))
        captures = {}
        monkeypatch.setattr("internal.handler.assistant_agent_handler.current_user", current_user_stub)
        monkeypatch.setattr(
            "internal.service.assistant_agent_service.AssistantAgentService.stop_chat",
            lambda _self, task_id, account: captures.update({"task_id": task_id, "account": account}),
        )

        resp = http_client.post(f"/assistant-agent/chat/{TASK_ID}/stop", json={})

        assert resp.status_code == 200
        assert captures["task_id"] == UUID(TASK_ID)
        assert captures["account"] is current_user_stub

    def test_should_delegate_web_app_stop_with_token_task_id_and_current_user(self, http_client, monkeypatch):
        current_user_stub = SimpleNamespace(id=UUID(APP_ID), is_authenticated=True)
        captures = {}
        monkeypatch.setattr("internal.handler.web_app_handler.current_user", current_user_stub)
        monkeypatch.setattr(
            "internal.service.web_app_service.WebAppService.stop_web_app_chat",
            lambda _self, token, task_id, account: captures.update(
                {"token": token, "task_id": task_id, "account": account}
            ),
        )

        resp = http_client.post(f"/web-apps/test-token/chat/{TASK_ID}/stop", json={})

        assert resp.status_code == 200
        assert captures["token"] == "test-token"
        assert captures["task_id"] == UUID(TASK_ID)
        assert captures["account"] is current_user_stub

    def test_should_reuse_visitor_cookie_actor_for_web_app_stop_when_cookie_is_valid(self, http_client, monkeypatch):
        visitor_id = uuid4()
        captures = {}
        http_client.application.config["WEB_APP_VISITOR_COOKIE_SECRET"] = "webapp-cookie-secret"
        monkeypatch.setattr(
            "internal.handler.web_app_handler.current_user",
            SimpleNamespace(id=UUID(APP_ID), is_authenticated=False),
        )
        monkeypatch.setattr(
            "internal.service.web_app_service.WebAppService.stop_web_app_chat",
            lambda _self, token, task_id, account: captures.update(
                {"token": token, "task_id": task_id, "account": account}
            ),
        )

        with http_client.application.test_request_context("/"):
            signed_cookie = WebAppHandler._encode_visitor_cookie(visitor_id)
        http_client.set_cookie("llmops_webapp_visitor_id", signed_cookie)
        resp = http_client.post(f"/web-apps/test-token/chat/{TASK_ID}/stop", json={})

        assert resp.status_code == 200
        assert captures["token"] == "test-token"
        assert captures["task_id"] == UUID(TASK_ID)
        assert captures["account"].id == visitor_id
        assert getattr(captures["account"], "is_authenticated", True) is False

    def test_should_regenerate_visitor_cookie_when_cookie_signature_is_invalid(self, http_client, monkeypatch):
        forged_visitor_id = uuid4()
        captures = {}
        http_client.application.config["WEB_APP_VISITOR_COOKIE_SECRET"] = "webapp-cookie-secret"
        http_client.application.config["WEB_APP_VISITOR_COOKIE_SECURE"] = True
        monkeypatch.setattr(
            "internal.handler.web_app_handler.current_user",
            SimpleNamespace(id=UUID(APP_ID), is_authenticated=False),
        )
        monkeypatch.setattr(
            "internal.service.web_app_service.WebAppService.stop_web_app_chat",
            lambda _self, token, task_id, account: captures.update(
                {"token": token, "task_id": task_id, "account": account}
            ),
        )

        # 伪造未签名 cookie（值本身是合法 UUID），应被识别为无效并重新下发签名 cookie。
        http_client.set_cookie("llmops_webapp_visitor_id", str(forged_visitor_id))
        resp = http_client.post(f"/web-apps/test-token/chat/{TASK_ID}/stop", json={})

        assert resp.status_code == 200
        assert captures["token"] == "test-token"
        assert captures["task_id"] == UUID(TASK_ID)
        assert isinstance(captures["account"].id, UUID)
        assert captures["account"].id != forged_visitor_id
        set_cookie = resp.headers.get("Set-Cookie", "")
        assert "llmops_webapp_visitor_id=" in set_cookie
        assert "Secure" in set_cookie

    def test_should_fallback_to_plain_uuid_cookie_when_cookie_secret_missing(self, http_client, monkeypatch):
        visitor_id = uuid4()
        app = http_client.application
        app.config["WEB_APP_VISITOR_COOKIE_SECRET"] = ""
        app.config["SECRET_KEY"] = ""
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

        with app.test_request_context("/"):
            assert WebAppHandler._get_visitor_cookie_signer() is None
            cookie_value = WebAppHandler._encode_visitor_cookie(visitor_id)

        assert cookie_value == str(visitor_id)
