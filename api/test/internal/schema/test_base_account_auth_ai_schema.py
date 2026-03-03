from __future__ import annotations

from uuid import uuid4

import pytest
from wtforms import Form

from internal.schema.account_schema import (
    GetCurrentUserResp,
    UpdateAvatarReq,
    UpdateNameReq,
    UpdatePasswordReq,
)
from internal.schema.ai_schema import (
    GenerateSuggestedQuestionsReq,
    OpenAPISchemaAssistantChatReq,
    OptimizePromptReq,
)
from internal.schema.auth_schema import PasswordLoginReq, PasswordLoginResp
from internal.schema.oauth_schema import AuthorizeReq, AuthorizeResp
from internal.schema.schema import DictField, ListField
from test.internal.schema.utils import ns, utc_dt


def _validate_form(form_request, form_cls, *, data=None, json=None, content_type=None):
    with form_request(data=data, json=json, content_type=content_type):
        form = form_cls(meta={"csrf": False})
        return form.validate(), form


def test_list_field_should_process_list_and_return_value():
    class _ListForm(Form):
        field = ListField("field")

    field = _ListForm().field
    field.process_formdata(["a", "b"])
    assert field.data == ["a", "b"]
    assert field._value() == ["a", "b"]


def test_list_field_should_keep_default_when_formdata_is_not_list():
    class _ListForm(Form):
        field = ListField("field")

    field = _ListForm().field
    field.process_formdata("invalid")  # type: ignore[arg-type]
    assert field.data is None
    assert field._value() == []


def test_dict_field_should_extract_first_dict_item():
    class _DictForm(Form):
        field = DictField("field")

    field = _DictForm().field
    field.process_formdata([{"a": 1}, {"b": 2}])
    assert field.data == {"a": 1}
    assert field._value() == {"a": 1}


def test_dict_field_should_ignore_invalid_formdata():
    class _DictForm(Form):
        field = DictField("field")

    field = _DictForm().field
    field.process_formdata([])
    assert field.data is None
    assert field._value() is None


def test_get_current_user_resp_should_dump_expected_fields():
    account = ns(
        id=uuid4(),
        name="tester",
        email="tester@example.com",
        avatar="https://img.example.com/avatar.png",
        last_login_at=utc_dt(2024, 1, 2, 3, 4, 5),
        last_login_ip="127.0.0.1",
        created_at=utc_dt(2024, 1, 1, 0, 0, 0),
    )

    data = GetCurrentUserResp().dump(account)

    assert data["name"] == "tester"
    assert data["email"] == "tester@example.com"
    assert data["last_login_ip"] == "127.0.0.1"
    assert data["last_login_at"] == int(utc_dt(2024, 1, 2, 3, 4, 5).timestamp())
    assert data["created_at"] == int(utc_dt(2024, 1, 1, 0, 0, 0).timestamp())


def test_get_current_user_resp_should_convert_none_datetime_to_zero():
    account = ns(
        id=uuid4(),
        name="tester",
        email="tester@example.com",
        avatar="https://img.example.com/avatar.png",
        last_login_at=None,
        last_login_ip="",
        created_at=None,
    )

    data = GetCurrentUserResp().dump(account)
    assert data["last_login_at"] == 0
    assert data["created_at"] == 0


def test_update_password_req_should_validate_pattern(form_request):
    ok, form = _validate_form(form_request, UpdatePasswordReq, data={"password": "Abcd1234"})
    assert ok, form.errors

    ok, form = _validate_form(form_request, UpdatePasswordReq, data={"password": "abcdef"})
    assert not ok
    assert "password" in form.errors


def test_update_name_req_should_check_length_boundary(form_request):
    ok, form = _validate_form(form_request, UpdateNameReq, data={"name": "a" * 30})
    assert ok, form.errors

    ok, form = _validate_form(form_request, UpdateNameReq, data={"name": "a" * 31})
    assert not ok
    assert "name" in form.errors


def test_update_avatar_req_should_require_valid_url(form_request):
    ok, form = _validate_form(form_request, UpdateAvatarReq, data={"avatar": "https://example.com/a.png"})
    assert ok, form.errors

    ok, form = _validate_form(form_request, UpdateAvatarReq, data={"avatar": "not-url"})
    assert not ok
    assert "avatar" in form.errors


def test_password_login_req_should_validate_email_and_password(form_request):
    ok, form = _validate_form(
        form_request,
        PasswordLoginReq,
        data={"email": "user@example.com", "password": "Abcd1234"},
    )
    assert ok, form.errors

    ok, form = _validate_form(
        form_request,
        PasswordLoginReq,
        data={"email": "bad-email", "password": "Abcd1234"},
    )
    assert not ok
    assert "email" in form.errors

    ok, form = _validate_form(
        form_request,
        PasswordLoginReq,
        data={"email": "user@example.com", "password": "short"},
    )
    assert not ok
    assert "password" in form.errors


def test_password_login_resp_should_dump_tokens():
    payload = PasswordLoginResp().dump({"access_token": "token", "expire_at": 123})
    assert payload == {"access_token": "token", "expire_at": 123}


def test_authorize_req_should_require_code(form_request):
    ok, form = _validate_form(form_request, AuthorizeReq, data={"code": "oauth-code"})
    assert ok, form.errors

    ok, form = _validate_form(form_request, AuthorizeReq, data={"code": ""})
    assert not ok
    assert "code" in form.errors


def test_authorize_resp_should_dump_tokens():
    payload = AuthorizeResp().dump({"access_token": "token", "expire_at": 123})
    assert payload == {"access_token": "token", "expire_at": 123}


def test_optimize_prompt_req_should_validate_max_length(form_request):
    ok, form = _validate_form(form_request, OptimizePromptReq, data={"prompt": "x" * 2000})
    assert ok, form.errors

    ok, form = _validate_form(form_request, OptimizePromptReq, data={"prompt": "x" * 2001})
    assert not ok
    assert "prompt" in form.errors


def test_generate_suggested_questions_req_should_validate_uuid(form_request):
    ok, form = _validate_form(form_request, GenerateSuggestedQuestionsReq, data={"message_id": str(uuid4())})
    assert ok, form.errors

    ok, form = _validate_form(form_request, GenerateSuggestedQuestionsReq, data={"message_id": "bad-id"})
    assert not ok
    assert "message_id" in form.errors


def test_openapi_schema_assistant_chat_req_should_validate_length(form_request):
    ok, form = _validate_form(form_request, OpenAPISchemaAssistantChatReq, data={"question": "帮我生成天气插件schema"})
    assert ok, form.errors

    ok, form = _validate_form(form_request, OpenAPISchemaAssistantChatReq, data={"question": "x" * 2001})
    assert not ok
    assert "question" in form.errors
