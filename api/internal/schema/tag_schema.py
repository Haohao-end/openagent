"""
标签 Schema 模块

定义标签相关的请求和响应数据结构。
"""

from uuid import UUID
from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import StringField
from wtforms.validators import DataRequired, Length, Optional

from internal.entity.tag_entity import TagStatus, TagType
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
    items = fields.List(fields.Nested(TagResp))
    total = fields.Integer()
    page = fields.Integer()
    page_size = fields.Integer()


class GetMyTagsReq(PaginatorReq):
    """获取我的标签请求"""
    pass


class AppTagsSchema(Schema):
    """应用标签 Schema"""
    tags = fields.List(fields.Nested(TagResp))
    total = fields.Integer()
