from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import IntegerField, StringField, BooleanField, Field
from wtforms.validators import Optional, NumberRange, DataRequired, Length, UUID, ValidationError
from internal.lib.helper import datetime_to_timestamp
from internal.lib.helper import build_input_parts, build_output_payload
from internal.model import Message
from pkg.paginator import PaginatorReq


class GetConversationMessagesWithPageReq(PaginatorReq):
    """获取指定会话消息列表分页数据请求结构"""
    created_at = IntegerField("created_at", default=0, validators=[
        Optional(),
        NumberRange(min=0, message="created_at游标最小值为0")
    ])


class GetConversationMessagesWithPageResp(Schema):
    """获取指定会话消息列表分页数据响应结构"""
    id = fields.UUID(dump_default="")
    conversation_id = fields.UUID(dump_default="")
    query = fields.String(dump_default="")
    image_urls = fields.List(fields.String, dump_default=[])
    input_parts = fields.List(fields.Dict, dump_default=[])
    answer = fields.String(dump_default="")
    answer_parts = fields.List(fields.Dict, dump_default=[])
    artifacts = fields.List(fields.Dict, dump_default=[])
    total_token_count = fields.Integer(dump_default=0)
    latency = fields.Float(dump_default=0)
    agent_thoughts = fields.List(fields.Dict, dump_default=[])
    suggested_questions = fields.List(fields.String, dump_default=[])
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Message, **kwargs):
        output_payload = build_output_payload(data.answer, getattr(data, "agent_thoughts", []) or [])
        return {
            "id": data.id,
            "conversation_id": data.conversation_id,
            "query": data.query,
            "image_urls": data.image_urls,
            "input_parts": build_input_parts(data.query, data.image_urls),
            "answer": data.answer,
            "answer_parts": output_payload["answer_parts"],
            "artifacts": output_payload["artifacts"],
            "total_token_count": data.total_token_count,
            "latency": data.latency,
            "agent_thoughts": [{
                "id": agent_thought.id,
                "position": agent_thought.position,
                "event": agent_thought.event,
                "thought": agent_thought.thought,
                "observation": agent_thought.observation,
                "tool": agent_thought.tool,
                "tool_input": agent_thought.tool_input,
                "latency": agent_thought.latency,
                "created_at": datetime_to_timestamp(agent_thought.created_at),
            } for agent_thought in data.agent_thoughts],
            "suggested_questions": data.suggested_questions if data.suggested_questions else [],
            "created_at": datetime_to_timestamp(data.created_at),
        }


class UpdateConversationNameReq(FlaskForm):
    """更新会话名字请求结构体"""
    name = StringField("name", validators=[
        DataRequired(message="会话名字不能为空"),
        Length(max=100, message="会话名字长度不能超过100个字符")
    ])


class UpdateConversationIsPinnedReq(FlaskForm):
    """更新会话置顶选项请求请求结构体"""
    is_pinned = BooleanField("is_pinned", default=False)


class GetRecentConversationsReq(FlaskForm):
    """获取最近会话列表请求结构体"""
    limit = IntegerField("limit", default=20, validators=[
        Optional(),
        NumberRange(min=1, max=1000, message="limit范围必须在1~1000之间"),
    ])


class GetRecentConversationsResp(Schema):
    """获取最近会话列表响应结构体"""
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    source_type = fields.String(dump_default="")
    app_id = fields.UUID(dump_default="")
    app_name = fields.String(dump_default="")
    message_id = fields.UUID(dump_default="")
    is_active = fields.Boolean(dump_default=False)
    latest_message_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)
    human_message = fields.String(dump_default="")
    ai_message = fields.String(dump_default="")


class SearchConversationsReq(FlaskForm):
    """搜索会话请求结构体"""
    query = StringField("query", default="", validators=[
        Optional(),
        Length(max=500, message="搜索词长度不能超过500个字符")
    ])
    limit = IntegerField("limit", default=50, validators=[
        Optional(),
        NumberRange(min=1, max=100, message="limit范围必须在1~100之间"),
    ])


class SearchConversationsResp(Schema):
    """搜索会话响应结构体"""
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    source_type = fields.String(dump_default="")
    app_id = fields.UUID(dump_default="")
    app_name = fields.String(dump_default="")
    agent_name = fields.String(dump_default="")
    message_id = fields.UUID(dump_default="")
    is_active = fields.Boolean(dump_default=False)
    latest_message_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)
    human_message = fields.String(dump_default="")
    ai_message = fields.String(dump_default="")
    matched_fields = fields.List(fields.String(), dump_default=[])


class CompareMessagesReq(FlaskForm):
    """比较两次运行消息差异请求结构体"""
    target_message_id = StringField("target_message_id", validators=[
        DataRequired(message="目标消息ID不能为空"),
        UUID(message="目标消息ID格式必须为UUID"),
    ])
    base_message_id = StringField("base_message_id", validators=[
        DataRequired(message="基准消息ID不能为空"),
        UUID(message="基准消息ID格式必须为UUID"),
    ])


class ReplayMessageReq(FlaskForm):
    """回放消息运行请求结构体"""
    patch = Field("patch")

    def validate_patch(self, field):
        if field.data is not None and not isinstance(field.data, dict):
            raise ValidationError("patch必须为字典格式")
