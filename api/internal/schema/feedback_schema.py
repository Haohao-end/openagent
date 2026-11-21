from flask import request
from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional, AnyOf, NumberRange, ValidationError, StopValidation


def _raw_json_value(field) -> tuple[object, bool]:
    """读取 JSON 原始值，避免列表等类型被 WTForms 静默转换后漏检。"""
    if not request.is_json:
        return None, False
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or field.name not in payload:
        return None, False
    return payload[field.name], True


def _require_string(_form, field: StringField) -> None:
    """JSON 请求中非字符串值不会经过 WTForms 强制转换，需显式拦截。"""
    value, present = _raw_json_value(field)
    if present:
        if value is not None and not isinstance(value, str):
            raise StopValidation("该字段必须为字符串")
        return
    if field.data is not None and not isinstance(field.data, str):
        raise StopValidation("该字段必须为字符串")


def _require_rating_int(_form, field: IntegerField) -> None:
    """JSON 中的布尔值会被 IntegerField 静默强转成 0/1，需要读取原始报文拦截。"""
    value, present = _raw_json_value(field)
    if not present or value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError("评分必须为整数")


class FeedbackCreateReq(FlaskForm):
    target_id = StringField('target_id', validators=[_require_string, DataRequired()])
    target_type = StringField('target_type', validators=[_require_string, DataRequired(), AnyOf(['message', 'span'])])
    rating = IntegerField('rating', validators=[Optional(), _require_rating_int, AnyOf([-1, 1])])
    content = TextAreaField('content', validators=[_require_string, Optional()])


class FeedbackListReq(FlaskForm):
    app_id = StringField('app_id', validators=[Optional()])
    target_type = StringField('target_type', validators=[Optional(), AnyOf(['message', 'span'])])
    page = IntegerField('page', validators=[Optional(), NumberRange(min=1, max=100000)])
    limit = IntegerField('limit', validators=[Optional(), NumberRange(min=1, max=100)])
