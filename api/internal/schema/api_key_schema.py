from datetime import UTC, datetime

from flask import has_request_context, request
from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import BooleanField, IntegerField, StringField
from wtforms.validators import Length, StopValidation, ValidationError

from internal.lib.helper import datetime_to_timestamp
from internal.model import ApiKey


class ApiKeyExpirationField(IntegerField):
    """Parse JSON numbers without WTForms coercing invalid values first."""

    def process_formdata(self, valuelist: list[str]) -> None:
        if has_request_context() and request.is_json:
            payload = request.get_json(silent=True)
            if isinstance(payload, dict) and self.name in payload:
                self.data = payload[self.name]
                return
        super().process_formdata(valuelist)


def _validate_form_boolean(_form, field: BooleanField) -> None:
    if request.is_json or field.name not in request.form:
        return
    value = request.form.get(field.name, "").strip().lower()
    if value in {"true", "1", "yes", "y", "on"}:
        field.data = True
    elif value in {"false", "0", "no", "n", "off"}:
        field.data = False
    else:
        raise ValidationError("激活状态必须为布尔值")


def _validate_json_boolean(field: BooleanField) -> None:
    if not request.is_json:
        return

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValidationError("请求内容必须为JSON对象")
    if field.name in payload and not isinstance(payload[field.name], bool):
        raise ValidationError("激活状态必须为布尔值")


def _validate_json_remark(_form: FlaskForm, field: StringField) -> None:
    if not request.is_json:
        return

    payload = request.get_json(silent=True)
    if isinstance(payload, dict) and field.name in payload and not isinstance(payload[field.name], str):
        raise StopValidation("秘钥备注必须为字符串")


def _validate_json_expires_at(_form: FlaskForm, field: IntegerField) -> None:
    """Accept optional Unix epoch seconds and reject JSON coercion."""
    if request.is_json:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raise ValidationError("请求内容必须为JSON对象")
        if field.name in payload:
            value = payload[field.name]
            if value is None:
                field.data = None
                return
            if isinstance(value, bool) or not isinstance(value, int):
                raise StopValidation("失效时间必须为Unix秒级时间戳")
            field.data = value

    if field.data is None:
        return
    try:
        datetime.fromtimestamp(field.data, UTC)
    except (OverflowError, OSError, ValueError):
        raise StopValidation("失效时间超出有效范围")


class CreateApiKeyReq(FlaskForm):
    """创建API秘钥请求"""
    is_active = BooleanField("is_active", validators=[_validate_form_boolean])
    remark = StringField("remark", validators=[
        _validate_json_remark,
        Length(max=100, message="秘钥备注不能超过100个字符")
    ])
    expires_at = ApiKeyExpirationField("expires_at", validators=[_validate_json_expires_at])

    def validate_is_active(self, field: BooleanField) -> None:
        _validate_json_boolean(field)


class UpdateApiKeyReq(FlaskForm):
    """更新API秘钥请求"""
    is_active = BooleanField("is_active", validators=[_validate_form_boolean])
    remark = StringField("remark", validators=[
        _validate_json_remark,
        Length(max=100, message="秘钥备注不能超过100个字符")
    ])
    expires_at = ApiKeyExpirationField("expires_at", validators=[_validate_json_expires_at])

    def validate_is_active(self, field: BooleanField) -> None:
        _validate_json_boolean(field)


class UpdateApiKeyIsActiveReq(FlaskForm):
    """更新API秘钥激活请求"""
    is_active = BooleanField("is_active", validators=[_validate_form_boolean])


class GetApiKeysWithPageResp(Schema):
    """获取API秘钥分页列表数据"""
    MASKED_API_KEY = "****************"
    id = fields.UUID(dump_default="")
    api_key = fields.String(dump_default="")
    is_active = fields.Boolean(dump_default=False)
    remark = fields.String(dump_default="")
    expires_at = fields.Integer(dump_default=0)
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: ApiKey, **kwargs):
        return {
            "id": data.id,
            "api_key": self.MASKED_API_KEY,
            "is_active": data.is_active,
            "remark": data.remark,
            "expires_at": datetime_to_timestamp(getattr(data, "expires_at", None)),
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }
