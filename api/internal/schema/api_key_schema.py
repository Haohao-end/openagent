from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import BooleanField, StringField
from wtforms.validators import Length

from internal.lib.helper import datetime_to_timestamp
from internal.model import ApiKey


class CreateApiKeyReq(FlaskForm):
    """创建API秘钥请求"""
    is_active = BooleanField("is_active")
    remark = StringField("remark", validators=[
        Length(max=100, message="秘钥备注不能超过100个字符")
    ])


class UpdateApiKeyReq(FlaskForm):
    """更新API秘钥请求"""
    is_active = BooleanField("is_active")
    remark = StringField("remark", validators=[
        Length(max=100, message="秘钥备注不能超过100个字符")
    ])


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
