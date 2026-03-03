from __future__ import annotations

from uuid import uuid4

from internal.schema.api_key_schema import (
    CreateApiKeyReq,
    GetApiKeysWithPageResp,
    UpdateApiKeyIsActiveReq,
    UpdateApiKeyReq,
)
from internal.schema.audio_schema import AudioToTextReq, MessageToAudioReq, TextToAudioReq
from internal.schema.platform_schema import GetWechatConfigResp, UpdateWechatConfigReq
from internal.schema.upload_file_schema import UploadFileReq, UploadFileResp, UploadImageReq
from test.internal.schema.utils import ns, upload, utc_dt


def _validate_form(form_request, form_cls, *, data=None, json=None, content_type=None):
    with form_request(data=data, json=json, content_type=content_type):
        form = form_cls(meta={"csrf": False})
        return form.validate(), form


def test_create_and_update_api_key_req_should_validate_remark_length(form_request):
    ok, form = _validate_form(form_request, CreateApiKeyReq, data={"remark": "x" * 100, "is_active": "y"})
    assert ok, form.errors

    ok, form = _validate_form(form_request, CreateApiKeyReq, data={"remark": "x" * 101})
    assert not ok
    assert "remark" in form.errors

    ok, form = _validate_form(form_request, UpdateApiKeyReq, data={"remark": "x" * 100})
    assert ok, form.errors

    ok, form = _validate_form(form_request, UpdateApiKeyReq, data={"remark": "x" * 101})
    assert not ok
    assert "remark" in form.errors


def test_update_api_key_is_active_req_should_accept_boolean_field(form_request):
    ok, form = _validate_form(form_request, UpdateApiKeyIsActiveReq, data={"is_active": "y"})
    assert ok, form.errors
    assert form.is_active.data is True


def test_get_api_keys_with_page_resp_should_dump_expected_fields():
    api_key = ns(
        id=uuid4(),
        api_key="sk-test",
        is_active=True,
        remark="remark",
        updated_at=utc_dt(2024, 1, 2, 0, 0, 0),
        created_at=utc_dt(2024, 1, 1, 0, 0, 0),
    )
    data = GetApiKeysWithPageResp().dump(api_key)
    assert data["api_key"] == "****************"
    assert data["is_active"] is True
    assert data["updated_at"] == int(utc_dt(2024, 1, 2, 0, 0, 0).timestamp())
    assert data["created_at"] == int(utc_dt(2024, 1, 1, 0, 0, 0).timestamp())


def test_get_wechat_config_resp_should_include_env_prefix(monkeypatch):
    monkeypatch.setenv("SERVICE_API_PREFIX", "https://api.example.com")
    monkeypatch.setenv("SERVICE_IP", "10.0.0.1")

    config = ns(
        app_id=uuid4(),
        wechat_app_id="wx-app-id",
        wechat_app_secret="wx-secret",
        wechat_token="wx-token",
        status="enabled",
        updated_at=utc_dt(2024, 1, 2, 0, 0, 0),
        created_at=utc_dt(2024, 1, 1, 0, 0, 0),
    )
    data = GetWechatConfigResp().dump(config)
    assert data["url"].startswith("https://api.example.com/wechat/")
    assert data["ip"] == "10.0.0.1"
    assert data["wechat_app_id"] == "wx-app-id"


def test_update_wechat_config_req_should_allow_empty_optional_fields(form_request):
    ok, form = _validate_form(
        form_request,
        UpdateWechatConfigReq,
        data={
            "wechat_app_id": "",
            "wechat_app_secret": "",
            "wechat_token": "",
        },
    )
    assert ok, form.errors


def test_audio_to_text_req_should_validate_file_extension(form_request):
    ok, form = _validate_form(
        form_request,
        AudioToTextReq,
        data={"file": upload("voice.wav")},
        content_type="multipart/form-data",
    )
    assert ok, form.errors

    ok, form = _validate_form(
        form_request,
        AudioToTextReq,
        data={"file": upload("voice.mp3")},
        content_type="multipart/form-data",
    )
    assert not ok
    assert "file" in form.errors


def test_message_to_audio_req_should_require_message_id(form_request):
    ok, form = _validate_form(form_request, MessageToAudioReq, data={"message_id": "msg-1"})
    assert ok, form.errors

    ok, form = _validate_form(form_request, MessageToAudioReq, data={"message_id": ""})
    assert not ok
    assert "message_id" in form.errors


def test_text_to_audio_req_should_validate_text_length(form_request):
    ok, form = _validate_form(form_request, TextToAudioReq, data={"text": "x" * 5000})
    assert ok, form.errors

    ok, form = _validate_form(form_request, TextToAudioReq, data={"text": "x" * 5001})
    assert not ok
    assert "text" in form.errors


def test_upload_file_req_should_validate_document_extension(form_request):
    ok, form = _validate_form(
        form_request,
        UploadFileReq,
        data={"file": upload("document.txt")},
        content_type="multipart/form-data",
    )
    assert ok, form.errors

    ok, form = _validate_form(
        form_request,
        UploadFileReq,
        data={"file": upload("document.exe")},
        content_type="multipart/form-data",
    )
    assert not ok
    assert "file" in form.errors


def test_upload_image_req_should_validate_image_extension(form_request):
    ok, form = _validate_form(
        form_request,
        UploadImageReq,
        data={"file": upload("image.png")},
        content_type="multipart/form-data",
    )
    assert ok, form.errors

    ok, form = _validate_form(
        form_request,
        UploadImageReq,
        data={"file": upload("image.bmp")},
        content_type="multipart/form-data",
    )
    assert not ok
    assert "file" in form.errors


def test_upload_file_resp_should_dump_expected_fields():
    upload_file = ns(
        id=uuid4(),
        account_id=uuid4(),
        name="a.txt",
        key="storage/a.txt",
        size=123,
        extension="txt",
        mime_type="text/plain",
        created_at=utc_dt(2024, 1, 1, 0, 0, 0),
    )
    data = UploadFileResp().dump(upload_file)
    assert data["name"] == "a.txt"
    assert data["extension"] == "txt"
    assert data["mime_type"] == "text/plain"
    assert data["created_at"] == int(utc_dt(2024, 1, 1, 0, 0, 0).timestamp())
