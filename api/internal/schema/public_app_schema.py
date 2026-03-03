"""公共应用Schema - 请求和响应验证"""
from flask_wtf import FlaskForm
from marshmallow import Schema, fields
from wtforms import StringField
from wtforms.validators import DataRequired, Length, Optional

from pkg.paginator import PaginatorReq
from internal.entity.app_category_entity import APP_CATEGORIES


class ShareAppToSquareReq(FlaskForm):
    """共享应用到广场请求"""
    category = StringField(
        "category",
        validators=[DataRequired(message="分类不能为空"), Length(max=100)]
    )


class GetPublicAppsWithPageReq(PaginatorReq):
    """获取公共应用列表请求"""
    category = StringField("category", default="all", validators=[Optional()])
    sort_by = StringField("sort_by", default="latest", validators=[Optional()])
    search_word = StringField("search_word", default="", validators=[Optional()])



class PublicAppResp(Schema):
    """公共应用响应"""
    id = fields.String()
    name = fields.String()
    icon = fields.String()
    description = fields.String()
    category = fields.String()
    view_count = fields.Integer()
    like_count = fields.Integer()
    fork_count = fields.Integer()
    favorite_count = fields.Integer()
    creator_name = fields.String()
    published_at = fields.Integer()
    created_at = fields.Integer()
    is_liked = fields.Boolean()
    is_favorited = fields.Boolean()


class GetPublicAppsWithPageResp(Schema):
    """获取公共应用列表响应"""
    apps = fields.List(fields.Nested(PublicAppResp))


class AppCategoryResp(Schema):
    """应用分类响应"""
    value = fields.String()
    label = fields.String()


class GetAppCategoriesResp(Schema):
    """获取应用分类列表响应"""
    categories = fields.List(fields.Nested(AppCategoryResp))

    class Meta:
        strict = True

    def dump(self, obj, **kwargs):
        """自定义序列化"""
        return {"categories": APP_CATEGORIES}


class LikeAppResp(Schema):
    """点赞应用响应"""
    is_liked = fields.Boolean()
    like_count = fields.Integer()


class FavoriteAppResp(Schema):
    """收藏应用响应"""
    is_favorited = fields.Boolean()


class ForkAppResp(Schema):
    """Fork应用响应"""
    id = fields.String()
    name = fields.String()
