"""
标签 Schema 模块

定义标签相关的请求和响应数据结构。
"""

from flask_wtf import FlaskForm
from marshmallow import Schema, fields
from wtforms import StringField
from wtforms.validators import AnyOf, DataRequired, Length, Optional

from internal.entity.tag_entity import TagType
from internal.lib.helper import datetime_to_timestamp
from pkg.paginator import PaginatorReq


class CreateTagReq(FlaskForm):
    """创建标签请求"""
    name = StringField("name", validators=[
        DataRequired("标签名称不能为空"),
        Length(min=1, max=50, message="标签名称长度必须在 1-50 个字符之间"),
    ])
    description = StringField("description", validators=[
        Optional(),
        Length(max=200, message="标签描述长度不能超过 200 个字符"),
    ])
    tag_type = StringField("tag_type", validators=[
        Optional(),
        AnyOf(
            [TagType.CUSTOM.value, TagType.SYSTEM.value, TagType.CATEGORY.value],
            message="标签类型不支持",
        ),
    ])


class UpdateTagReq(FlaskForm):
    """更新标签请求"""
    name = StringField("name", validators=[
        DataRequired("标签名称不能为空"),
        Length(min=1, max=50, message="标签名称长度必须在 1-50 个字符之间"),
    ])
    description = StringField("description", validators=[
        Optional(),
        Length(max=200, message="标签描述长度不能超过 200 个字符"),
    ])


class TagResp(Schema):
    """标签响应"""
    id = fields.UUID()
    name = fields.String()
    description = fields.String()
    tag_type = fields.String()
    status = fields.String()
    created_at = fields.Method("get_created_at")
    updated_at = fields.Method("get_updated_at")

    def get_created_at(self, obj):
        """获取创建时间戳"""
        if hasattr(obj, 'created_at') and obj.created_at:
            return datetime_to_timestamp(obj.created_at)
        return None

    def get_updated_at(self, obj):
        """获取更新时间戳"""
        if hasattr(obj, 'updated_at') and obj.updated_at:
            return datetime_to_timestamp(obj.updated_at)
        return None


class ListTagsResp(Schema):
    """标签列表响应"""
    list = fields.List(fields.Nested(TagResp))
    paginator = fields.Dict()


class GetMyTagsReq(PaginatorReq):
    """获取我的标签请求"""
    pass


class AppTagsSchema(Schema):
    """应用标签 Schema"""
    tags = fields.List(fields.Nested(TagResp))
    total = fields.Integer()


class TagDimensionResp(Schema):
    """标签维度响应"""
    value = fields.String()
    label = fields.String()


class GetTagDimensionsResp(Schema):
    """获取标签维度响应"""
    dimensions = fields.List(fields.Nested(TagDimensionResp))


class HotTagResp(Schema):
    """热门标签响应"""
    id = fields.String()
    name = fields.String()
    dimension = fields.String()
    use_count = fields.Integer()


class GetHotTagsResp(Schema):
    """获取热门标签响应"""
    hot_tags = fields.Dict(
        keys=fields.String(),
        values=fields.List(fields.Nested(HotTagResp)),
    )
