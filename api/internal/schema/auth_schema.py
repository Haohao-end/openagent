from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired, Email, Length, regexp
from pkg.password import password_pattern
from marshmallow import Schema, fields

class PasswordLoginReq(FlaskForm):
    """账号密码登陆请求结构"""
    email = StringField('email', validators=[
        DataRequired(),
        Email("登陆邮箱格式错误"),
        Length(min=3, max=254, message="登陆邮箱长度在5~254之间")
    ])
    password = StringField('password', validators=[
        DataRequired("密码不能为空"),
        regexp(regex=password_pattern, message="密码最少包含一个字母,一个数字,并且长度在8~16")
    ])

class PasswordLoginResp(Schema):
    """账号密码授权认证响应结构"""
    access_token = fields.String(allow_none=True)
    expire_at = fields.Integer(allow_none=True)
    challenge_required = fields.Boolean()
    challenge_id = fields.String(allow_none=True)
    challenge_type = fields.String(allow_none=True)
    masked_email = fields.String(allow_none=True)
    risk_reason = fields.String(allow_none=True)

class SendResetCodeReq(FlaskForm):
    """发送重置验证码请求结构"""
    email = StringField('email', validators=[
        DataRequired("邮箱不能为空"),
        Email("邮箱格式错误"),
        Length(min=3, max=254, message="邮箱长度在3~254之间")
    ])

class ResetPasswordReq(FlaskForm):
    """重置密码请求结构"""
    email = StringField('email', validators=[
        DataRequired("邮箱不能为空"),
        Email("邮箱格式错误"),
    ])
    code = StringField('code', validators=[
        DataRequired("验证码不能为空"),
        Length(min=6, max=6, message="验证码必须是6位数字")
    ])
    new_password = StringField('new_password', validators=[
        DataRequired("新密码不能为空"),
        regexp(regex=password_pattern, message="密码最少包含一个字母,一个数字,并且长度在8~16")
    ])


class VerifyLoginChallengeReq(FlaskForm):
    """登录二次验证请求结构"""
    challenge_id = StringField('challenge_id', validators=[
        DataRequired("challenge_id 不能为空"),
        Length(min=1, max=128, message="challenge_id 参数错误"),
    ])
    code = StringField('code', validators=[
        DataRequired("验证码不能为空"),
        Length(min=6, max=6, message="验证码必须是6位数字")
    ])


class ResendLoginChallengeReq(FlaskForm):
    """重发登录二次验证验证码请求结构"""
    challenge_id = StringField('challenge_id', validators=[
        DataRequired("challenge_id 不能为空"),
        Length(min=1, max=128, message="challenge_id 参数错误"),
    ])
