from flask_wtf import FlaskForm
from wtforms import StringField, ValidationError
from wtforms.validators import DataRequired,Length,URL, Optional
from .schema import ListField
from marshmallow import Schema,fields,pre_dump
from internal.model import ApiToolProvider,ApiTool
from internal.lib.helper import datetime_to_timestamp
from pkg.paginator import PaginatorReq

class ValidateOpenAPISchemaReq(FlaskForm):
    """校验OpenAPI规范字符串请求"""
    openapi_schema = StringField("openapi_schema",validators=[
        DataRequired(message="openapi_schema字符串不能为空")
    ])

class GetApiToolProvidersWithPageReq(PaginatorReq):
    """获取API工具提供者分页列表请求"""
    search_word = StringField("search_word",validators=[
        Optional()
    ])
class CreateApiToolReq(FlaskForm):
    """创建自定义API工具请求"""
    name = StringField(
        "name",validators=[
            DataRequired(message="工具提供者的名字不能为空"),
            Length(min=1,max=30,message="工具提供者的名字长度为1~30之间")
        ]
    )
    icon = StringField("icon",validators=[
        DataRequired(message="工具提供者的图标不能为空"),
        URL(message="工具提供者的图标必须是URL链接")
    ])
    openapi_schema = StringField("opennapi_schema",validators=[
        DataRequired(message="openapi_schema字符串不能为空")
    ])
    headers = ListField("headers",default=[])

    @classmethod
    def validate_headers(cls,form,field):
        """校验headers请求的数据是否正确 涵盖列表校验 列表元素校验"""
        for header in field.data:
            if not isinstance(header,dict):
                raise ValidationError("headers里的每一格元素都必须是字典")
            if set(header.keys()) != {"key", "value"}:
                # header = {"key": "Content-Type", "value": "application/json"}
                raise ValidationError("headers里的每一格元素都必须包含key和value两个属性 不允许有其他属性")

class UpdateApiToolProviderReq(FlaskForm):
    """更新API工具提供者请求"""
    name = StringField(
        "name", validators=[
            DataRequired(message="工具提供者的名字不能为空"),
            Length(min=1, max=30, message="工具提供者的名字长度为1~30之间")
        ]
    )
    icon = StringField("icon", validators=[
        DataRequired(message="工具提供者的图标不能为空"),
        URL(message="工具提供者的图标必须是URL链接")
    ])
    openapi_schema = StringField("opennapi_schema", validators=[
        DataRequired(message="openapi_schema字符串不能为空")
    ])
    headers = ListField("headers",default=[])

    @classmethod
    def validate_headers(cls, form, field):
        """校验headers请求的数据是否正确 涵盖列表校验 列表元素校验"""
        for header in field.data:
            if not isinstance(header, dict):
                raise ValidationError("headers里的每一格元素都必须是字典")
            if set(header.keys()) != {"key", "value"}:
                # header = {"key": "Content-Type", "value": "application/json"}
                raise ValidationError("headers里的每一格元素都必须包含key和value两个属性 不允许有其他属性")
class GetApiToolProviderResp(Schema):
    """获取API工具提供者响应信息"""
    id = fields.UUID()
    name = fields.String()
    icon = fields.String()
    openapi_schema = fields.String()
    headers = fields.List(fields.Dict,dump_default=[])
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self,data:ApiToolProvider,**kwargs):
        return {
            "id":data.id,
            "name":data.name,
            "icon":data.icon,
            "openapi_schema":data.openapi_schema,
            "headers":data.headers,
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at)
        }

class GetApiToolResp(Schema):
    """获取API工具参数详情响应"""
    id = fields.UUID()
    name = fields.String()
    description = fields.String()
    inputs = fields.List(fields.Dict, dump_default=[])
    provider = fields.Dict()

    @pre_dump
    def process_data(self,data:ApiTool,**kwargs):
        provider = data.provider
        return {
            "id":data.id,
            "name":data.name,
            "description":data.description,
            "inputs":[{k: v for k, v in parameter.items() if k != "in"} for parameter in data.parameters],
            "provider": {
                "id": provider.id,
                "name": provider.name,
                "icon": provider.icon,
                "description": provider.description,
                "headers": provider.headers
            }
        }

class GetApiToolProvidersWithPageResp(Schema):
    """获取API工具提供者分页列表数据响应"""
    id = fields.UUID()
    name = fields.String()
    icon = fields.String()
    description = fields.String()
    headers = fields.List(fields.Dict,dump_default=[])
    tools = fields.List(fields.Dict,dump_default=[])
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self,data:ApiToolProvider,**kwargs):
        tools = data.tools
        return {
            "id": data.id,
            "name": data.name,
            "icon": data.icon,
            "description": data.description,
            "headers": data.headers,
            "tools": [{
                "id": tool.id,
                "description": tool.description,
                "name": tool.name,
                "inputs": [{k: v for k,  v in parameter.items() if k != "in"} for parameter in tool.parameters]
            } for tool in tools],
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at)
        }
