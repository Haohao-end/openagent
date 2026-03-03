from flask import request
from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import StringField, BooleanField
from wtforms.validators import Optional, ValidationError, DataRequired
from internal.lib.helper import datetime_to_timestamp
from internal.model import Segment
from pkg.paginator import PaginatorReq
from .schema import ListField


def _get_keywords_from_json() -> list:
    """
    从 JSON 请求体中提取 keywords 原始值。

    说明：
    1. `ListField` 在 Flask-WTF 场景下会把字符串包装成单元素列表，
       这会导致 `"keywords": "x"` 被误识别为合法列表。
    2. 这里显式读取原始 JSON，保证仅接受真正的数组类型。
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return []
    return payload.get("keywords", [])

class GetSegmentsWithPageReq(PaginatorReq):
    """获取文档片段列表请求"""
    search_word = StringField("search_word", default="", validators=[
        Optional()
    ])

class GetSegmentsWithPageResp(Schema):
    """获取文档片段列表响应结构"""
    id = fields.UUID(dump_default="")
    document_id = fields.UUID(dump_default="")
    dataset_id = fields.UUID(dump_default="")
    position = fields.Integer(dump_default=0)
    content = fields.String(dump_default="")
    keywords = fields.List(fields.String, dump_default=[])
    character_count = fields.Integer(dump_default=0)
    token_count = fields.Integer(dump_default=0)
    hit_count = fields.Integer(dump_default=0)
    enabled = fields.Boolean(dump_default=False)
    disabled_at = fields.Integer(dump_default=0)
    status = fields.String(dump_default="")
    error = fields.String(dump_default="")
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Segment, **kwargs):
        return {
            "id": data.id,
            "document_id": data.document_id,
            "dataset_id": data.dataset_id,
            "position": data.position,
            "content": data.content,
            "keywords": data.keywords,
            "character_count": data.character_count,
            "token_count": data.token_count,
            "hit_count": data.hit_count,
            "enabled": data.enabled,
            "disabled_at": datetime_to_timestamp(data.disabled_at),
            "status": data.status,
            "error": data.error,
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }

class GetSegmentResp(Schema):
    """获取文档详情响应结构"""
    id = fields.UUID(dump_default="")
    document_id = fields.UUID(dump_default="")
    dataset_id = fields.UUID(dump_default="")
    position = fields.Integer(dump_default=0)
    content = fields.String(dump_default="")
    keywords = fields.List(fields.String, dump_default=[])
    character_count = fields.Integer(dump_default=0)
    token_count = fields.Integer(dump_default=0)
    hit_count = fields.Integer(dump_default=0)
    hash = fields.String(dump_default="")
    enabled = fields.Boolean(dump_default=False)
    disabled_at = fields.Integer(dump_default=0)
    status = fields.String(dump_default="")
    error = fields.String(dump_default="")
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Segment, **kwargs):
        return {
            "id": data.id,
            "document_id": data.document_id,
            "dataset_id": data.dataset_id,
            "position": data.position,
            "content": data.content,
            "keywords": data.keywords,
            "character_count": data.character_count,
            "token_count": data.token_count,
            "hit_count": data.hit_count,
            "hash": data.hash,
            "enabled": data.enabled,
            "disabled_at": datetime_to_timestamp(data.disabled_at),
            "status": data.status,
            "error": data.error,
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }

class UpdateSegmentEnabledReq(FlaskForm):
    """更新文档片段启用状态请求"""
    enabled = BooleanField("enabled")

    def validate_enabled(self, field: BooleanField) -> None:
        """校验文档启用状态enabled"""
        if not isinstance(field.data, bool):
            raise ValidationError("enabled状态不能为空且必须为布尔值")

class CreateSegmentReq(FlaskForm):
    """创建文档片段请求结构"""
    content = StringField("content", validators=[
        DataRequired("片段不能为空")
    ])
    keywords = ListField("keywords")

    def validate_keywords(self, field: ListField) -> None:
        """校验关键词列表 涵盖长度不能为空 默认值为空列表"""
        # 1.优先读取请求体原始值，避免字符串被 ListField 自动包装后绕过类型校验
        raw_keywords = _get_keywords_from_json()
        if raw_keywords is None:
            field.data = []
        else:
            field.data = raw_keywords

        # 2.校验数据类型 + 非空
        if not isinstance(field.data, list):
            raise ValidationError("关键词列表格式必须是数组")

        # 3.校验数据的长度 最长不能超过10个关键词
        if len(field.data) > 10:
            raise ValidationError("关键词长度范围数量在1~10")

        # 4.循环校验关键词信息 关键词必须是字符串
        for keyword in field.data:
            if not isinstance(keyword, str):
                raise ValidationError("关键词必须是字符串")

        # 5.删除重复的数据并更新
        field.data = list(dict.fromkeys(field.data))

class UpdateSegmentReq(FlaskForm):
    """更新文档片段请求"""
    content = StringField("content", validators=[
        DataRequired("片段内容不能为空")
    ])
    keywords = ListField("keywords")

    def validate_keywords(self, field: ListField) -> None:
        """校验关键词列表 涵盖长度不能为空 默认值为空列表"""
        # 1.优先读取请求体原始值，避免字符串被 ListField 自动包装后绕过类型校验
        raw_keywords = _get_keywords_from_json()
        if raw_keywords is None:
            field.data = []
        else:
            field.data = raw_keywords

        # 2.校验数据类型 + 非空
        if not isinstance(field.data, list):
            raise ValidationError("关键词列表格式必须是数组")

        # 3.校验数据的长度，最长不能超过10个关键词
        if len(field.data) > 10:
            raise ValidationError("关键词长度范围数量在1-10")

        # 4.循环校验关键词信息，关键词必须是字符串
        for keyword in field.data:
            if not isinstance(keyword, str):
                raise ValidationError("关键词必须是字符串")

        # 5.删除重复数据并更新
        field.data = list(dict.fromkeys(field.data))



