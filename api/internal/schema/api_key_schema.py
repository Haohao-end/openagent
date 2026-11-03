from flask import request
from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import BooleanField, StringField
from wtforms.validators import Length, ValidationError

from internal.lib.helper import datetime_to_timestamp
from internal.model import ApiKey


def _validate_json_boolean(field: BooleanField) -> None:
    if not request.is_json:
        return

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValidationError("请求内容必须为JSON对象")
    if field.name in payload and not isinstance(payload[field.name], bool):
        raise ValidationError("激活状态必须为布尔值")


class CreateApiKeyReq(FlaskForm):
    """创建API秘钥请求"""
    is_active = BooleanField("is_active")
    remark = StringField("remark", validators=[
        Length(max=100, message="秘钥备注不能超过100个字符")
    ])

    def validate_is_active(self, field: BooleanField) -> None:
        _validate_json_boolean(field)


class UpdateApiKeyReq(FlaskForm):
    """更新API秘钥请求"""
    is_active = BooleanField("is_active")
    remark = StringField("remark", validators=[
        Length(max=100, message="秘钥备注不能超过100个字符")
    ])

    def validate_is_active(self, field: BooleanField) -> None:
        _validate_json_boolean(field)


class UpdateApiKeyIsActiveReq(FlaskForm):
    """更新API秘钥激活请求"""
    is_active = BooleanField("is_active")


class GetApiKeysWithPageResp(Schema):
    """获取API秘钥分页列表数据"""
    MASKED_API_KEY = "****************"
    id = fields.UUID(dump_default="")
    api_key = fields.String(dump_default="")
    is_active = fields.Boolean(dump_default=False)
    remark = fields.String(dump_default="")
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: ApiKey, **kwargs):
        return {
            "id": data.id,
            "api_key": self.MASKED_API_KEY,
            "is_active": data.is_active,
            "remark": data.remark,
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }
