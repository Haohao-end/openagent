"""公共工作流Schema"""
from flask_wtf import FlaskForm
from marshmallow import Schema, fields
from wtforms import StringField
from wtforms.validators import DataRequired, Length, Optional

from pkg.paginator import PaginatorReq


class ShareWorkflowToSquareReq(FlaskForm):
    """共享工作流到广场请求"""
    category = StringField(
        "category",
        validators=[DataRequired(message="分类不能为空"), Length(max=100)]
    )


class GetPublicWorkflowsWithPageReq(PaginatorReq):
    """获取公共工作流列表请求"""
    category = StringField("category", default="all", validators=[Optional()])
    sort_by = StringField("sort_by", default="latest", validators=[Optional()])
    search_word = StringField("search_word", default="", validators=[Optional()])


class PublicWorkflowResp(Schema):
    """公共工作流响应"""
    id = fields.String()
    name = fields.String()
    icon = fields.String()
    description = fields.String()
    category = fields.String()
    view_count = fields.Integer()
    like_count = fields.Integer()
    fork_count = fields.Integer()
    favorite_count = fields.Integer()  # 新增收藏数
    published_at = fields.Integer()
    created_at = fields.Integer()
    is_liked = fields.Boolean()
    is_favorited = fields.Boolean()
    account_name = fields.String()  # 新增发布者名称


class LikeWorkflowResp(Schema):
    """点赞工作流响应"""
    is_liked = fields.Boolean()
    like_count = fields.Integer()


class FavoriteWorkflowResp(Schema):
    """收藏工作流响应"""
    is_favorited = fields.Boolean()
    favorite_count = fields.Integer()  # 新增收藏数


class ForkWorkflowResp(Schema):
    """Fork工作流响应"""
    id = fields.String()
    name = fields.String()
