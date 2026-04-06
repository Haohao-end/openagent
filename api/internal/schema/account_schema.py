from marshmallow import Schema, fields, pre_dump
from internal.model import Account
from internal.lib.helper import datetime_to_timestamp
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField
from wtforms.validators import AnyOf, DataRequired, regexp, Length, NumberRange, URL, Optional, Email
from pkg.password import password_pattern


class AccountOAuthBindingResp(Schema):
    """账号 OAuth 绑定状态"""
    provider = fields.String(dump_default="")
    bound = fields.Boolean(dump_default=False)
    bound_at = fields.Integer(dump_default=0)

class GetCurrentUserResp(Schema):
    """获取当前登陆账号响应"""
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    email = fields.String(dump_default="")
    avatar = fields.String(dump_default="")
    last_login_at = fields.Integer(dump_default=0)
    last_login_ip = fields.String(dump_default="")
    last_login_location = fields.String(dump_default="")
    created_at = fields.Integer(dump_default=0)
    password_set = fields.Boolean(dump_default=False)
    oauth_bindings = fields.List(fields.Nested(AccountOAuthBindingResp), dump_default=[])

    @pre_dump
    def process_data(self, data: Account | dict, **kwargs):
        def _timestamp(value):
            return datetime_to_timestamp(value)

        if isinstance(data, dict):
            oauth_bindings = []
            for binding in data.get("oauth_bindings", []) or []:
                oauth_bindings.append({
                    "provider": binding.get("provider", ""),
                    "bound": bool(binding.get("bound", False)),
                    "bound_at": _timestamp(binding.get("bound_at")),
                })

            return {
                "id": data.get("id"),
                "name": data.get("name", ""),
                "email": data.get("email", ""),
                "avatar": data.get("avatar", ""),
                "last_login_at": _timestamp(data.get("last_login_at")),
                "last_login_ip": data.get("last_login_ip", ""),
                "last_login_location": data.get("last_login_location", ""),
                "created_at": _timestamp(data.get("created_at")),
                "password_set": bool(data.get("password_set", False)),
                "oauth_bindings": oauth_bindings,
            }

        return {
            "id": data.id,
            "name": data.name,
            "email": data.email,
            "avatar": data.avatar,
            "last_login_at": _timestamp(data.last_login_at),
            "last_login_ip": data.last_login_ip,
            "last_login_location": getattr(data, "last_login_location", ""),
            "created_at": _timestamp(data.created_at),
            "password_set": bool(getattr(data, "is_password_set", False)),
            "oauth_bindings": [],
        }


class AccountSessionResp(Schema):
    """账号会话响应"""
    id = fields.UUID(dump_default="")
    current = fields.Boolean(dump_default=False)
    legacy = fields.Boolean(dump_default=False)
    device_name = fields.String(dump_default="")
    user_agent = fields.String(dump_default="")
    ip = fields.String(dump_default="")
    location = fields.String(dump_default="")
    created_at = fields.Integer(dump_default=0)
    last_active_at = fields.Integer(dump_default=0)
    expires_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: dict, **kwargs):
        return {
            "id": data.get("id"),
            "current": bool(data.get("current", False)),
            "legacy": bool(data.get("legacy", False)),
            "device_name": data.get("device_name", ""),
            "user_agent": data.get("user_agent", ""),
            "ip": data.get("ip", ""),
            "location": data.get("location", ""),
            "created_at": datetime_to_timestamp(data.get("created_at")),
            "last_active_at": datetime_to_timestamp(data.get("last_active_at")),
            "expires_at": datetime_to_timestamp(data.get("expires_at")),
        }


class GetAccountSessionsResp(Schema):
    """获取账号会话列表响应"""
    session_capable = fields.Boolean(dump_default=False)
    current_session_id = fields.UUID(allow_none=True, dump_default=None)
    sessions = fields.List(fields.Nested(AccountSessionResp), dump_default=[])


class AccountLoginHistoryResp(Schema):
    """账号登录历史响应"""
    id = fields.UUID(dump_default="")
    current = fields.Boolean(dump_default=False)
    legacy = fields.Boolean(dump_default=False)
    device_name = fields.String(dump_default="")
    user_agent = fields.String(dump_default="")
    ip = fields.String(dump_default="")
    location = fields.String(dump_default="")
    status = fields.String(dump_default="active")
    unusual_ip = fields.Boolean(dump_default=False)
    created_at = fields.Integer(dump_default=0)
    last_active_at = fields.Integer(dump_default=0)
    expires_at = fields.Integer(dump_default=0)
    revoked_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: dict, **kwargs):
        return {
            "id": data.get("id"),
            "current": bool(data.get("current", False)),
            "legacy": bool(data.get("legacy", False)),
            "device_name": data.get("device_name", ""),
            "user_agent": data.get("user_agent", ""),
            "ip": data.get("ip", ""),
            "location": data.get("location", ""),
            "status": data.get("status", "active"),
            "unusual_ip": bool(data.get("unusual_ip", False)),
            "created_at": datetime_to_timestamp(data.get("created_at")),
            "last_active_at": datetime_to_timestamp(data.get("last_active_at")),
            "expires_at": datetime_to_timestamp(data.get("expires_at")),
            "revoked_at": datetime_to_timestamp(data.get("revoked_at")),
        }


class GetAccountLoginHistoryResp(Schema):
    """获取账号登录历史响应"""
    history = fields.List(fields.Nested(AccountLoginHistoryResp), dump_default=[])
    total = fields.Integer(dump_default=0)
    current_page = fields.Integer(dump_default=1)
    page_size = fields.Integer(dump_default=20)


class GetAccountLoginHistoryReq(FlaskForm):
    """获取账号登录历史请求"""
    status = StringField("status", default="all", validators=[
        Optional(),
        AnyOf(["all", "active", "revoked", "expired", "legacy"], message="登录状态筛选值错误"),
    ])
    search = StringField("search", default="", validators=[
        Optional(),
        Length(max=255, message="搜索关键词长度不能超过255位"),
    ])
    current_page = IntegerField("current_page", default=1, validators=[
        Optional(),
        NumberRange(min=1, max=9999, message="当前页数的范围在1-9999"),
    ])
    page_size = IntegerField("page_size", default=5, validators=[
        Optional(),
        NumberRange(min=1, max=100, message="每页数据的条数范围在1-100"),
    ])


class UpdatePasswordReq(FlaskForm):
    """更新账号密码请求"""
    current_password = StringField("current_password", validators=[
        Optional(),
        Length(max=128, message="当前密码长度不能超过128位"),
    ])
    new_password = StringField("new_password", validators=[
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


class SendChangeEmailCodeReq(FlaskForm):
    """发送换绑邮箱验证码请求"""
    email = StringField("email", validators=[
        DataRequired("邮箱不能为空"),
        Email("邮箱格式错误"),
        Length(min=3, max=254, message="邮箱长度在3~254之间"),
    ])


class UpdateEmailReq(FlaskForm):
    """更新账号邮箱请求"""
    email = StringField("email", validators=[
        DataRequired("邮箱不能为空"),
        Email("邮箱格式错误"),
        Length(min=3, max=254, message="邮箱长度在3~254之间"),
    ])
    code = StringField("code", validators=[
        DataRequired("验证码不能为空"),
        Length(min=6, max=6, message="验证码必须是6位数字"),
    ])
    current_password = StringField("current_password", validators=[
        Optional(),
        Length(max=128, message="当前密码长度不能超过128位"),
    ])
