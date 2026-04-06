"""公共应用Schema - 请求和响应验证"""
from flask_wtf import FlaskForm
from marshmallow import Schema, fields
from wtforms import StringField
from wtforms.validators import DataRequired, Length, Optional

from pkg.paginator import PaginatorReq
from internal.entity.tag_entity import APP_TAGS


class ShareAppToSquareReq(FlaskForm):
    """共享应用到广场请求"""
    tags = StringField(
        "tags",
        validators=[Optional(), Length(max=500)]
    )


class GetPublicAppsWithPageReq(PaginatorReq):
    """获取公共应用列表请求"""
    tags = StringField("tags", default="", validators=[Optional()])
    sort_by = StringField("sort_by", default="latest", validators=[Optional()])
    search_word = StringField("search_word", default="", validators=[Optional()])



class PublicAppResp(Schema):
    """公共应用响应"""
    id = fields.String()
    name = fields.String()
    icon = fields.String()
    description = fields.String()
    tags = fields.List(fields.String())
    view_count = fields.Integer()
    like_count = fields.Integer()
    fork_count = fields.Integer()
    favorite_count = fields.Integer()
    creator_name = fields.String()
    creator_avatar = fields.String()  # 新增创建者头像
    published_at = fields.Integer()
    created_at = fields.Integer()
    is_liked = fields.Boolean()
    is_favorited = fields.Boolean()
    is_forked = fields.Boolean()  # 是否已fork


class GetPublicAppsWithPageResp(Schema):
    """获取公共应用列表响应"""
    apps = fields.List(fields.Nested(PublicAppResp))


class AppTagResp(Schema):
    """应用标签响应"""
    id = fields.String()
    name = fields.String()
    priority = fields.Integer()


class GetAppTagsResp(Schema):
    """获取应用标签列表响应"""
    tags = fields.List(fields.Nested(AppTagResp))

    class Meta:
        strict = True

    def dump(self, obj, **kwargs):
        """自定义序列化"""
        return {"tags": APP_TAGS}


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
