from flask_wtf import FlaskForm
from marshmallow import Schema, fields
from wtforms import StringField
from wtforms.validators import DataRequired, Optional, AnyOf

class AuthorizeReq(FlaskForm):
    """第三方授权认证登陆"""
    code = StringField("code",validators=[
        DataRequired("code代码不能为空")
    ])
    intent = StringField("intent", validators=[
        Optional(),
        AnyOf(["login", "bind"], message="intent 参数错误"),
    ])

class AuthorizeResp(Schema):
    """第三方授权认证响应结构"""
    access_token = fields.String(allow_none=True)
    expire_at = fields.Integer(allow_none=True)
    challenge_required = fields.Boolean()
    challenge_id = fields.String(allow_none=True)
    challenge_type = fields.String(allow_none=True)
    masked_email = fields.String(allow_none=True)
    risk_reason = fields.String(allow_none=True)
