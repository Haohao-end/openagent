from marshmallow import Schema, fields, pre_dump
from internal.model import Account
from internal.lib.helper import datetime_to_timestamp
from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired, regexp, Length, URL
from pkg.password import password_pattern

class GetCurrentUserResp(Schema):
    """获取当前登陆账号响应"""
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    email = fields.String(dump_default="")
    avatar = fields.String(dump_default="")
    last_login_at = fields.Integer(dump_default=0)
    last_login_ip = fields.String(dump_default="")
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Account, **kwargs):
        return {
            "id": data.id,
            "name": data.name,
            "email": data.email,
            "avatar": data.avatar,
            "last_login_at": datetime_to_timestamp(data.last_login_at),
            "last_login_ip": data.last_login_ip,
            "created_at": datetime_to_timestamp(data.created_at),
        }


class UpdatePasswordReq(FlaskForm):
    """更新账号密码请求"""
    password = StringField("password", validators=[
        DataRequired(),
        regexp(regex=password_pattern, message="密码最少包含一个字母 一个数字 并且长度为8~16位")
    ])

class UpdateNameReq(FlaskForm):
    """更新账号名称请求"""
    name = StringField("avatar", validators=[
        DataRequired("账号名称不能为空"),
        Length(min=1, max=30, message="账号名称长度在1~30位")
    ])


class UpdateAvatarReq(FlaskForm):
    """更新账号头像请求"""
    avatar = StringField("avatar", validators=[
        DataRequired("账号头像不能为空"),
        URL("账号头像必须是URL图片地址"),
    ])