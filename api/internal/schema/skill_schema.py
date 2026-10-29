from __future__ import annotations

from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import BooleanField, IntegerField, StringField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError

from internal.lib.helper import datetime_to_timestamp
from internal.schema import DictField, ListField
from pkg.paginator import PaginatorReq


class GetSkillsWithPageReq(PaginatorReq):
    """获取技能包分页列表请求。"""

    search_word = StringField("search_word", default="", validators=[Optional()])
    category = StringField("category", default="", validators=[Optional(), Length(max=64)])


class RollbackSkillPackageReq(FlaskForm):
    """技能包回滚请求。"""

    version = IntegerField(
        "version",
        validators=[
            DataRequired("技能版本不能为空"),
            NumberRange(min=1, message="技能版本必须大于0"),
        ],
    )

    def validate_version(self, field: IntegerField) -> None:
        if field.raw_data and isinstance(field.raw_data[0], bool):
            raise ValidationError("技能版本必须是整数")


class SkillToolInputResp(Schema):
    name = fields.String()
    type = fields.String()
    required = fields.Boolean()
    description = fields.String()


class SkillToolResp(Schema):
    name = fields.String()
    label = fields.String()
    description = fields.String()
    entrypoint = fields.String()
    inputs = fields.List(fields.Nested(SkillToolInputResp), dump_default=[])


class SkillVersionResp(Schema):
    id = fields.UUID(dump_default="")
    skill_package_id = fields.UUID(dump_default="")
    version = fields.Integer(dump_default=0)
    checksum = fields.String(dump_default="")
    sync_status = fields.String(dump_default="")
    sync_error = fields.String(dump_default="")
    is_current_version = fields.Boolean(dump_default=False)
    summary = fields.String(dump_default="")
    tool_count = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)
    updated_at = fields.Integer(dump_default=0)


class SkillPackageResp(Schema):
    id = fields.UUID(dump_default="")
    source_key = fields.String(dump_default="")
    name = fields.String(dump_default="")
    label = fields.String(dump_default="")
    icon = fields.String(dump_default="")
    description = fields.String(dump_default="")
    readme = fields.String(dump_default="")
    category = fields.String(dump_default="")
    tags = fields.List(fields.String(), dump_default=[])
    capabilities = fields.Dict(dump_default={})
    executor_type = fields.String(dump_default="scf")
    tool_count = fields.Integer(dump_default=0)
    tools = fields.List(fields.Nested(SkillToolResp), dump_default=[])
    created_at = fields.Integer(dump_default=0)
    updated_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data, **kwargs):
        if isinstance(data, dict):
            return data
        return {
            "id": data.id,
            "source_key": data.source_key,
            "name": data.name,
            "label": data.label,
            "icon": data.icon,
            "description": data.description,
            "readme": getattr(data, "readme", ""),
            "category": data.category,
            "tags": data.tags or [],
            "capabilities": data.capabilities or {},
            "executor_type": data.executor_type,
            "tool_count": getattr(data, "tool_count", 0),
            "tools": getattr(data, "tools", []),
            "created_at": datetime_to_timestamp(data.created_at),
            "updated_at": datetime_to_timestamp(data.updated_at),
        }


class GetSkillsCategoriesResp(Schema):
    categories = fields.List(fields.Dict())

    class Meta:
        strict = True

    def dump(self, obj, **kwargs):
        return {"categories": obj.get("categories", []) if isinstance(obj, dict) else []}
