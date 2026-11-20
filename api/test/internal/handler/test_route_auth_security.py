from types import SimpleNamespace
from uuid import UUID

import pytest

from internal.service import AccountService, ApiKeyService, HomeService, JwtService, OpenAPIService
from pkg.response import HttpCode, Response


HOME_ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000011")
OPENAPI_ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000022")
OPENAPI_APP_ID = "00000000-0000-0000-0000-000000000033"


class TestRouteAuthSecurity:
    @pytest.fixture
    def http_client(self, app, monkeypatch):
        monkeypatch.setitem(app.config, "LOGIN_DISABLED", False)
        with app.test_client() as client:
            yield client

    def test_home_intent_should_reject_missing_authorization(self, http_client):
        resp = http_client.get("/home/intent")

        assert resp.status_code == 200
        assert resp.get_json() == {
            "code": HttpCode.UNAUTHORIZED,
            "message": "该接口需要授权才能访问 请登陆后重试",
            "data": {},
        }

    def test_home_intent_should_accept_bearer_token_and_load_current_user(
        self,
        http_client,
        monkeypatch,
    ):
        account = SimpleNamespace(
            id=HOME_ACCOUNT_ID,
            is_authenticated=True,
            name="tester",
            email="tester@example.com",
        )
        call_state = {}

        monkeypatch.setattr(
            JwtService,
            "parse_token",
            lambda _self, token: {"sub": str(HOME_ACCOUNT_ID), "jti": f"session:{token}"},
        )
        monkeypatch.setattr(
            AccountService,
            "validate_access_session",
            lambda _self, payload: {"id": payload["jti"]},
        )
        monkeypatch.setattr(
            AccountService,
            "get_account",
            lambda _self, account_id: account if account_id == str(HOME_ACCOUNT_ID) else None,
        )

        def _get_user_intent(_self, user):
            call_state["user"] = user
            return {
                "intent": "build_app",
                "confidence": 0.88,
                "suggested_actions": [
                    {"label": "创建应用", "action": "create_app", "icon": "sparkles"}
                ],
                "is_default": False,
            }

        monkeypatch.setattr(HomeService, "get_user_intent", _get_user_intent)

        resp = http_client.get(
            "/home/intent",
            headers={"Authorization": "Bearer home-token"},
        )

        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["code"] == HttpCode.SUCCESS
        assert payload["data"]["intent"] == "build_app"
        assert payload["data"]["confidence"] == pytest.approx(0.88)
        assert payload["data"]["suggested_actions"][0]["action"] == "create_app"
        assert call_state["user"].id == account.id
        assert call_state["user"].is_authenticated is True

    def test_openapi_chat_should_reject_missing_api_key_authorization(self, http_client):
        resp = http_client.post("/openapi/chat", json={"app_id": OPENAPI_APP_ID, "query": "hello"})

        assert resp.status_code == 200
        assert resp.get_json() == {
            "code": HttpCode.UNAUTHORIZED,
            "message": "该接口需要授权才能访问 请登陆后重试",
            "data": {},
        }

    def test_openapi_chat_should_accept_api_key_and_load_api_key_account(
        self,
        http_client,
        monkeypatch,
    ):
        account = SimpleNamespace(
            id=OPENAPI_ACCOUNT_ID,
            is_authenticated=True,
            name="tester",
            email="tester@example.com",
        )
        call_state = {}

        api_key_id = UUID("00000000-0000-0000-0000-000000000044")
        monkeypatch.setattr(
            ApiKeyService,
            "get_api_by_by_credential",
            lambda _self, credential: SimpleNamespace(
                id=api_key_id,
                account_id=account.id,
                is_active=True,
                account=account,
                credential=credential,
            ),
        )
        monkeypatch.setattr(
            ApiKeyService,
            "check_rate_limit",
            lambda _self, _api_key_record, **_kwargs: (True, 1, 60),
        )

        def _chat(_self, req, current_account):
            call_state["account"] = current_account
            call_state["app_id"] = req.app_id.data
            return Response(code=HttpCode.SUCCESS, data={"ok": True, "query": req.query.data})

        monkeypatch.setattr(OpenAPIService, "chat", _chat)

        resp = http_client.post(
            "/openapi/chat",
            headers={"Authorization": "Bearer api-key-token"},
            json={"app_id": OPENAPI_APP_ID, "query": "hello"},
        )

        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["code"] == HttpCode.SUCCESS
        assert payload["data"]["ok"] is True
        assert payload["data"]["query"] == "hello"
        assert call_state["account"].id == account.id
        assert call_state["account"].is_authenticated is True
        assert call_state["app_id"] == OPENAPI_APP_ID

    def test_openapi_chat_should_reject_when_rate_limit_exceeded(
        self,
        http_client,
        monkeypatch,
    ):
        account = SimpleNamespace(
            id=OPENAPI_ACCOUNT_ID,
            is_authenticated=True,
            name="tester",
            email="tester@example.com",
        )
        api_key_id = UUID("00000000-0000-0000-0000-000000000044")

        monkeypatch.setattr(
            ApiKeyService,
            "get_api_by_by_credential",
            lambda _self, credential: SimpleNamespace(
                id=api_key_id,
                account_id=account.id,
                is_active=True,
                account=account,
                credential=credential,
            ),
        )
        monkeypatch.setattr(
            ApiKeyService,
            "check_rate_limit",
            lambda _self, _api_key_record, **_kwargs: (False, 60, 60),
        )

        resp = http_client.post(
            "/openapi/chat",
            headers={"Authorization": "Bearer api-key-token"},
            json={"app_id": OPENAPI_APP_ID, "query": "hello"},
        )

        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["code"] == HttpCode.FORBIDDEN
        assert "API密钥调用频率超出限制" in payload["message"]

    def test_openapi_chat_should_reject_when_scope_unauthorized(
        self,
        http_client,
        monkeypatch,
    ):
        account = SimpleNamespace(
            id=OPENAPI_ACCOUNT_ID,
            is_authenticated=True,
            name="tester",
            email="tester@example.com",
        )
        api_key_id = UUID("00000000-0000-0000-0000-000000000044")

        monkeypatch.setattr(
            ApiKeyService,
            "get_api_by_by_credential",
            lambda _self, credential: SimpleNamespace(
                id=api_key_id,
                account_id=account.id,
                is_active=True,
                account=account,
                credential=credential,
                scopes=["unrelated_scope"],
            ),
        )
        monkeypatch.setattr(
            ApiKeyService,
            "check_rate_limit",
            lambda _self, _api_key_record, **_kwargs: (True, 1, 60),
        )

        resp = http_client.post(
            "/openapi/chat",
            headers={"Authorization": "Bearer api-key-token"},
            json={"app_id": OPENAPI_APP_ID, "query": "hello"},
        )

        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["code"] == HttpCode.FORBIDDEN
        assert "该密钥没有调用此接口的权限" in payload["message"]

    def test_openapi_chat_should_allow_legacy_key_with_none_scope_for_chat(
        self,
        http_client,
        monkeypatch,
    ):
        account = SimpleNamespace(
            id=OPENAPI_ACCOUNT_ID,
            is_authenticated=True,
            name="tester",
            email="tester@example.com",
        )
        api_key_id = UUID("00000000-0000-0000-0000-000000000044")

        monkeypatch.setattr(
            ApiKeyService,
            "get_api_by_by_credential",
            lambda _self, credential: SimpleNamespace(
                id=api_key_id,
                account_id=account.id,
                is_active=True,
                account=account,
                credential=credential,
                scopes=None,
            ),
        )
        monkeypatch.setattr(
            ApiKeyService,
            "check_rate_limit",
            lambda _self, _api_key_record, **_kwargs: (True, 1, 60),
        )
        monkeypatch.setattr(
            OpenAPIService,
            "chat",
            lambda _self, req, current_account: Response(
                code=HttpCode.SUCCESS,
                data={"ok": True},
            ),
        )

        resp = http_client.post(
            "/openapi/chat",
            headers={"Authorization": "Bearer api-key-token"},
            json={"app_id": OPENAPI_APP_ID, "query": "hello"},
        )

        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["code"] == HttpCode.SUCCESS
        assert payload["data"]["ok"] is True

