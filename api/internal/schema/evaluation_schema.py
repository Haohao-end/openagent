from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class CreateEvaluationReq(FlaskForm):
    """创建评测集请求"""
    name = StringField("name", validators=[
        DataRequired(message="评测集名称不能为空"),
        Length(max=255, message="评测集名称不能超过255个字符"),
    ])


class UpdateEvaluationReq(FlaskForm):
    """更新评测集请求"""
    name = StringField("name", validators=[
        DataRequired(message="评测集名称不能为空"),
        Length(max=255, message="评测集名称不能超过255个字符"),
    ])


class GetEvaluationsReq(FlaskForm):
    """获取评测集列表请求"""
    page = IntegerField("page", default=1, validators=[
        Optional(),
        NumberRange(min=1, message="页码必须大于等于1"),
    ])
    limit = IntegerField("limit", default=20, validators=[
        Optional(),
        NumberRange(min=1, max=100, message="每页数量必须在1到100之间"),
    ])
