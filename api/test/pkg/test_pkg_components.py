import base64
from types import SimpleNamespace

import pytest
from flask import Flask

from pkg.oauth.github_oauth import GithubOAuth
from pkg.oauth.google_oauth import GoogleOAuth
from pkg.oauth.oauth import OAuth, OAuthUserInfo
from pkg.paginator.paginator import Paginator
from pkg.password.password import compare_password, hash_password, validate_password
from pkg.response.http_code import HttpCode
from pkg.response.response import (
    Response,
    compact_generate_response,
    fail_json,
    fail_message,
    forbidden_message,
    message,
    not_found_message,
    success_json,
    success_message,
    unauthorized_message,
    validate_error_json,
)
from pkg.sqlalchemy.sqlalchemy import SQLAlchemy


class _Resp:
    def __init__(self, payload, raise_error=None):
        self._payload = payload
        self._raise_error = raise_error

    def raise_for_status(self):
        if self._raise_error is not None:
            raise self._raise_error

    def json(self):
        return self._payload


class _DummyOAuth(OAuth):
    def get_provider(self) -> str:
        return "dummy"

    def get_authorization_url(self) -> str:
        return "https://dummy/oauth"

    def get_access_token(self, code: str) -> str:
        return code

    def get_raw_user_info(self, token: str) -> dict:
        return {"id": token, "name": "demo", "email": "demo@example.com"}

    def _transform_user_info(self, raw_info: dict) -> OAuthUserInfo:
        return OAuthUserInfo(
            id=str(raw_info["id"]),
            name=str(raw_info["name"]),
            email=str(raw_info["email"]),
        )


class TestOAuthProviders:
    def test_oauth_base_get_user_info_should_transform_raw_payload(self):
        oauth = _DummyOAuth(client_id="c", client_secret="s", redirect_uri="https://redirect")

        info = oauth.get_user_info("token-1")

        assert info == OAuthUserInfo(id="token-1", name="demo", email="demo@example.com")

    def test_oauth_abstract_method_bodies_should_be_callable_directly(self):
        # 覆盖抽象方法中的默认 pass 分支。
        assert OAuth.get_provider(SimpleNamespace()) is None
        assert OAuth.get_authorization_url(SimpleNamespace()) is None
        assert OAuth.get_access_token(SimpleNamespace(), "code") is None
        assert OAuth.get_raw_user_info(SimpleNamespace(), "token") is None
        assert OAuth._transform_user_info(SimpleNamespace(), {}) is None

    def test_github_oauth_should_cover_main_paths(self, monkeypatch):
        oauth = GithubOAuth(client_id="cid", client_secret="sec", redirect_uri="https://a.com/callback")
        assert oauth.get_provider() == "github"
        assert "client_id=cid" in oauth.get_authorization_url()
        assert "scope=user%3Aemail" in oauth.get_authorization_url()

        captured = {}

        def _fake_post(url, data=None, headers=None):
            captured["url"] = url
            captured["data"] = data
            captured["headers"] = headers
            return _Resp({"access_token": "gh-token"})

        monkeypatch.setattr("pkg.oauth.github_oauth.requests.post", _fake_post)
        token = oauth.get_access_token("code-1")
        assert token == "gh-token"
        assert captured["data"]["code"] == "code-1"
        assert captured["headers"]["Accept"] == "application/json"

        monkeypatch.setattr(
            "pkg.oauth.github_oauth.requests.post",
            lambda *_args, **_kwargs: _Resp({"error": "bad-code"}),
        )
        with pytest.raises(ValueError):
            oauth.get_access_token("bad")

        responses = [
            _Resp({"id": 7, "login": "octo", "name": "Octo"}),
            _Resp([{"email": "octo@example.com", "primary": True}]),
        ]
        monkeypatch.setattr("pkg.oauth.github_oauth.requests.get", lambda *_args, **_kwargs: responses.pop(0))
        raw_info = oauth.get_raw_user_info("gh-token")
        assert raw_info["email"] == "octo@example.com"

        info_with_fallback = oauth._transform_user_info({"id": 9, "login": "octo", "name": None, "email": None})
        assert info_with_fallback.name == "octo"
        assert info_with_fallback.email == "9+octo@user.no-reply@github.com"

        info_with_default_name = oauth._transform_user_info({"id": 10, "login": None, "name": None, "email": None})
        # 当前实现对 login=None 会得到字符串 "None"。
        assert info_with_default_name.name == "None"

        info_without_fallback = oauth._transform_user_info({"id": 11, "login": "octo", "name": "Octo", "email": "octo@x.com"})
        assert info_without_fallback.name == "Octo"
        assert info_without_fallback.email == "octo@x.com"

    def test_google_oauth_should_cover_main_paths(self, monkeypatch):
        oauth = GoogleOAuth(client_id="cid", client_secret="sec", redirect_uri="https://a.com/callback")
        assert oauth.get_provider() == "google"
        url = oauth.get_authorization_url()
        assert "response_type=code" in url
        assert "scope=openid+email+profile" in url

        post_calls = []
        monkeypatch.setattr(
            "pkg.oauth.google_oauth.requests.post",
            lambda url, data=None, timeout=None: post_calls.append((url, data, timeout)) or _Resp({"access_token": "gg-token"}),
        )
        token = oauth.get_access_token("code-2")
        assert token == "gg-token"
        assert post_calls[0][2] == 15

        monkeypatch.setattr(
            "pkg.oauth.google_oauth.requests.post",
            lambda *_args, **_kwargs: _Resp({"error": "no-token"}),
        )
        with pytest.raises(ValueError):
            oauth.get_access_token("bad")

        get_calls = []
        monkeypatch.setattr(
            "pkg.oauth.google_oauth.requests.get",
            lambda url, headers=None, timeout=None: get_calls.append((url, headers, timeout))
            or _Resp({"sub": "u-1", "name": "Google Demo", "email": "gd@example.com"}),
        )
        raw_info = oauth.get_raw_user_info("google-token")
        assert raw_info["sub"] == "u-1"
        assert get_calls[0][1]["Authorization"] == "Bearer google-token"
        assert get_calls[0][2] == 15

        transformed = oauth._transform_user_info({"sub": "u-2", "given_name": "Given", "email": None})
        assert transformed.name == "Given"
        assert transformed.email == "u-2@user.no-reply.google.com"

        transformed_with_email = oauth._transform_user_info({"sub": "u-3", "name": "Google User", "email": "u3@example.com"})
        assert transformed_with_email.name == "Google User"
        assert transformed_with_email.email == "u3@example.com"


class TestPaginatorPasswordResponseAndDB:
    def test_paginator_should_calculate_total_pages_and_items(self):
        paginate_calls = []
        db = SimpleNamespace(
            paginate=lambda select, page, per_page, error_out: paginate_calls.append((select, page, per_page, error_out))
            or SimpleNamespace(total=21, items=["a", "b"]),
        )
        req = SimpleNamespace(
            current_page=SimpleNamespace(data=2),
            page_size=SimpleNamespace(data=10),
        )
        paginator = Paginator(db=db, req=req)

        items = paginator.paginate(select="query")

        assert items == ["a", "b"]
        assert paginator.total_record == 21
        assert paginator.total_page == 3
        assert paginate_calls == [("query", 2, 10, False)]

    def test_paginator_should_prefer_query_paginate_when_available(self):
        db_paginate_calls = []
        db = SimpleNamespace(
            paginate=lambda *args, **kwargs: db_paginate_calls.append((args, kwargs)),
        )
        req = SimpleNamespace(
            current_page=SimpleNamespace(data=1),
            page_size=SimpleNamespace(data=20),
        )
        query_paginate_calls = []
        query = SimpleNamespace(
            paginate=lambda page, per_page, error_out: query_paginate_calls.append((page, per_page, error_out))
            or SimpleNamespace(total=1, items=[("row", 1)]),
        )
        paginator = Paginator(db=db, req=req)

        items = paginator.paginate(select=query)

        assert items == [("row", 1)]
        assert paginator.total_record == 1
        assert paginator.total_page == 1
        assert query_paginate_calls == [(1, 20, False)]
        assert db_paginate_calls == []

    def test_password_helpers_should_validate_hash_and_compare(self):
        validate_password("abc12345")
        with pytest.raises(ValueError):
            validate_password("short")

        salt = b"pepper-salt"
        hashed = hash_password("abc12345", salt)
        hashed_base64 = base64.b64encode(hashed)
        salt_base64 = base64.b64encode(salt)
        assert compare_password("abc12345", hashed_base64, salt_base64) is True
        assert compare_password("wrong123", hashed_base64, salt_base64) is False

    def test_response_helpers_should_cover_json_message_and_stream(self):
        app = Flask(__name__)
        with app.test_request_context("/"):
            success_resp, success_status = success_json({"ok": True})
            fail_resp, fail_status = fail_json({"ok": False})
            msg_resp, msg_status = message(code=HttpCode.SUCCESS, msg="done")
            validate_resp, validate_status = validate_error_json({"name": ["required"]})
            validate_none_key_resp, _ = validate_error_json({None: ["required"]})

            assert success_status == 200
            assert fail_status == 200
            assert msg_status == 200
            assert validate_status == 200
            assert success_resp.get_json()["code"] == HttpCode.SUCCESS
            assert fail_resp.get_json()["code"] == HttpCode.FAIL
            assert msg_resp.get_json()["message"] == "done"
            assert validate_resp.get_json()["message"] == "required"
            assert validate_none_key_resp.get_json()["message"] == ""

            assert success_message("ok")[0].get_json()["code"] == HttpCode.SUCCESS
            assert fail_message("bad")[0].get_json()["code"] == HttpCode.FAIL
            assert not_found_message("404")[0].get_json()["code"] == HttpCode.NOT_FOUND
            assert unauthorized_message("401")[0].get_json()["code"] == HttpCode.UNAUTHORIZED
            assert forbidden_message("403")[0].get_json()["code"] == HttpCode.FORBIDDEN

            compact_json, compact_status = compact_generate_response(Response(code=HttpCode.SUCCESS, message="m", data={}))
            assert compact_status == 200
            assert compact_json.get_json()["message"] == "m"

            stream_response = compact_generate_response((chunk for chunk in ["a", "b"]))
            assert stream_response.mimetype == "text/event-stream"
            assert stream_response.get_data(as_text=True) == "ab"

    def test_sqlalchemy_auto_commit_should_commit_and_rollback(self, monkeypatch):
        app = Flask(__name__)
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        db = SQLAlchemy(app)

        with app.app_context():
            commit_calls = []
            rollback_calls = []
            monkeypatch.setattr(db.session, "commit", lambda: commit_calls.append(True))
            monkeypatch.setattr(db.session, "rollback", lambda: rollback_calls.append(True))

            with db.auto_commit():
                pass
            assert commit_calls == [True]

            with pytest.raises(RuntimeError):
                with db.auto_commit():
                    raise RuntimeError("boom")
            assert rollback_calls == [True]
