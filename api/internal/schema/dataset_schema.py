from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import StringField, IntegerField, FloatField
from wtforms.validators import (
    DataRequired,
    Length,
    URL,
    Optional,
    AnyOf,
    NumberRange
)
from internal.model import Dataset, DatasetQuery
from pkg.paginator import PaginatorReq
from internal.entity.dataset_entity import RetrievalStrategy
from internal.lib.helper import datetime_to_timestamp


class CreateDatasetReq(FlaskForm):
    """创建知识库请求"""
    name = StringField("name", validators=[
        DataRequired("知识库名称不能为空"),
        Length(max=100, message="知识库名称长度不能超过100字符"),
    ])
    icon = StringField("icon", validators=[
        DataRequired("知识库图标不能为空"),
        URL("知识库图标必须是图片URL地址"),
    ])
    description = StringField("description", default="", validators=[
        Optional(),
        Length(max=2000, message="知识库描述长度不能超过2000字符")
    ])

class UpdateDatasetReq(FlaskForm):
    """更新知识库请求"""
    name = StringField("name", validators=[
        DataRequired("知识库名称不能为空"),
        Length(max=100, message="知识库名称长度不能超过100字符"),
    ])
    icon = StringField("icon", validators=[
        DataRequired("知识库图标不能为空"),
        URL("知识库图标必须是图片URL地址"),
    ])
    description = StringField("description", default="", validators=[
        Optional(),
        Length(max=2000, message="知识库描述长度不能超过2000字符")
    ])

class GetDatasetResp(Schema):
    """获取知识库详情响应结构"""
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    icon = fields.String(dump_default="")
    description = fields.String(dump_default="")
    document_count = fields.Integer(dump_default=0)
    hit_count = fields.Integer(dump_default=0)
    related_app_count = fields.Integer(dump_default=0)
    character_count = fields.Integer(dump_default=0)
    upload_at = fields.Integer(dump_default=0)
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Dataset, **kwargs):
        return {
            "id": data.id,
            "name": data.name,
            "icon": data.icon,
            "description": data.description,
            "document_count": data.document_count,
            "hit_count": data.hit_count,
            "related_app_count": data.related_app_count,
            "character_count": data.character_count,
            "upload_at": datetime_to_timestamp(data.updated_at),
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }

class GetDatasetsWithPageReq(PaginatorReq):
    """获取知识库分页列表请求数据"""
    search_word = StringField("search_word", default="", validators=[
        Optional()
    ])

class GetDatasetsWithPageResp(Schema):
    """获取知识库分页列表响应数据"""
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    icon = fields.String(dump_default="")
    description = fields.String(dump_default="")
    document_count = fields.Integer(dump_default=0)
    related_app_count = fields.Integer(dump_default=0)
    character_count = fields.Integer(dump_default=0)
    creator_name = fields.String(dump_default="")
    creator_avatar = fields.String(dump_default="")
    upload_at = fields.Integer(dump_default=0)
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Dataset, **kwargs):
        return {
            "id": data.id,
            "name": data.name,
            "icon": data.icon,
            "description": data.description,
            "document_count": data.document_count,
            "related_app_count": data.related_app_count,
            "character_count": data.character_count,
            "creator_name": data.account.name if data.account else "",
            "creator_avatar": data.account.avatar if data.account else "",
            "upload_at": datetime_to_timestamp(data.updated_at),
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }

class HitReq(FlaskForm):
    """知识库召回测试请求"""
    query = StringField("query", validators=[
        DataRequired("查询语句不能为空"),
        Length(max=200, message="查询语句的最大长度不能超过200")
    ])
    retrieval_strategy = StringField("retrieval_strategy", validators=[
        DataRequired("检索策略不能为空"),
        AnyOf([item.value for item in RetrievalStrategy], message="检索策略格式错误")
    ])
    k = IntegerField("k", validators=[
        DataRequired("最大召回数量不能为空"),
        NumberRange(min=1, max=10, message="最大召回数量的范围在1~10")
    ])
    score = FloatField("score", validators=[
        NumberRange(min=0, max=0.99, message="最小匹配度范围在0~0.99")
    ])


class GetDatasetQueriesResp(Schema):
    """获取知识库最近查询响应结构"""
    id = fields.UUID(dump_default="")
    dataset_id = fields.UUID(dump_default="")
    query = fields.String(dump_default="")
    source = fields.String(dump_default="")
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: DatasetQuery, **kwargs):
        return {
            "id": data.id,
            "dataset_id": data.dataset_id,
            "query": data.query,
            "source": data.source,
            "created_at": datetime_to_timestamp(data.created_at),
        }






















