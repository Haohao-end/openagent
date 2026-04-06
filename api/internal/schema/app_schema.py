from uuid import UUID
from urllib.parse import urlparse
from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import StringField, IntegerField
from wtforms.validators import DataRequired, Length, URL, ValidationError, Optional, NumberRange

from internal.entity.app_entity import AppConfigType, AppStatus
from internal.lib.helper import datetime_to_timestamp
from internal.model import App, AppConfigVersion, Message
from pkg.paginator import PaginatorReq
from internal.schema import DictField, ListField


class CreateAppReq(FlaskForm):
    """创建Agent应用请求结构体"""
    name = StringField("name", validators=[
        DataRequired("应用名称不能为空"),
        Length(max=40, message="应用名称长度最大不能超过40个字符"),
    ])
    icon = StringField("icon", validators=[
        Optional(),
        URL(message="应用图标必须是图片URL链接"),
    ])
    description = StringField("description", validators=[
        Length(max=800, message="应用描述的长度不能超过800个字符")
    ])


class UpdateAppReq(FlaskForm):
    """更新Agent应用请求结构体"""
    name = StringField("name", validators=[
        DataRequired("应用名称不能为空"),
        Length(max=40, message="应用名称长度最大不能超过40个字符"),
    ])
    icon = StringField("icon", validators=[
        DataRequired("应用图标不能为空"),
        URL(message="应用图标必须是图片URL链接"),
    ])
    description = StringField("description", validators=[
        Length(max=800, message="应用描述的长度不能超过800个字符")
    ])


class GetAppsWithPageReq(PaginatorReq):
    """获取应用分页列表数据请求"""
    search_word = StringField("search_word", default="", validators=[Optional()])


class GetAppsWithPageResp(Schema):
    """获取应用分页列表数据响应结构"""
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    icon = fields.String(dump_default="")
    description = fields.String(dump_default="")
    preset_prompt = fields.String(dump_default="")
    model_config = fields.Dict(dump_default={})
    status = fields.String(dump_default="")
    creator_name = fields.String(dump_default="")
    creator_avatar = fields.String(dump_default="")
    draft_updated_at = fields.Integer(dump_default=0)
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: App, **kwargs):
        app_config = data.app_config if data.status == AppStatus.PUBLISHED.value else data.draft_app_config
        return {
            "id": data.id,
            "name": data.name,
            "icon": data.icon,
            "description": data.description,
            "preset_prompt": app_config.preset_prompt,
            "model_config": {
                "provider": app_config.model_config.get("provider", ""),
                "model": app_config.model_config.get("model", "")
            },
            "status": data.status,
            "creator_name": data.account.name if data.account else "",
            "creator_avatar": data.account.avatar if data.account else "",
            "draft_updated_at": datetime_to_timestamp(data.draft_app_config.updated_at),
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }


class GetAppResp(Schema):
    """获取应用基础信息响应结构"""
    id = fields.UUID(dump_default="")
    debug_conversation_id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    icon = fields.String(dump_default="")
    description = fields.String(dump_default="")
    status = fields.String(dump_default="")
    is_public = fields.Boolean(dump_default=False)
    category = fields.String(dump_default="general")
    draft_updated_at = fields.Integer(dump_default=0)
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: App, **kwargs):
        return {
            "id": data.id,
            "debug_conversation_id": data.debug_conversation_id if data.debug_conversation_id else "",
            "name": data.name,
            "icon": data.icon,
            "description": data.description,
            "status": data.status,
            "is_public": data.is_public,
            "category": "general",
            "draft_updated_at": datetime_to_timestamp(data.draft_app_config.updated_at),
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }


class GetPublishHistoriesWithPageReq(PaginatorReq):
    """获取应用发布历史配置分页列表请求"""
    ...


class GetPublishHistoriesWithPageResp(Schema):
    """获取应用发布历史配置列表分页数据"""
    id = fields.UUID(dump_default="")
    app_id = fields.UUID(dump_default="")
    version = fields.Integer(dump_default=0)
    config_type = fields.String(dump_default="")
    config = fields.Dict(dump_default={})
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)
    is_current_published = fields.Boolean(dump_default=False)
    label = fields.String(dump_default="")
    summary = fields.String(dump_default="")

    @pre_dump
    def process_data(self, data: AppConfigVersion, **kwargs):
        config_type = getattr(data, "config_type", "")
        is_current_published = bool(getattr(data, "is_current_published", False))
        display_config = getattr(data, "display_config", None) or {}
        label = "草稿" if config_type == AppConfigType.DRAFT.value else f"版本 #{str(data.version).zfill(3)}"
        if config_type == AppConfigType.DRAFT.value:
            summary = "当前草稿版本"
        elif is_current_published:
            summary = "当前线上版本"
        else:
            summary = "历史发布版本"
        return {
            "id": data.id,
            "app_id": data.app_id,
            "version": data.version,
            "config_type": config_type,
            "config": {
                "model_config": display_config.get("model_config", data.model_config),
                "dialog_round": display_config.get("dialog_round", data.dialog_round),
                "preset_prompt": display_config.get("preset_prompt", data.preset_prompt),
                "tools": display_config.get("tools", data.tools),
                "workflows": display_config.get("workflows", data.workflows),
                "datasets": display_config.get("datasets", data.datasets),
                "retrieval_config": display_config.get("retrieval_config", data.retrieval_config),
                "long_term_memory": display_config.get("long_term_memory", data.long_term_memory),
                "opening_statement": display_config.get("opening_statement", data.opening_statement),
                "opening_questions": display_config.get("opening_questions", data.opening_questions),
                "speech_to_text": display_config.get("speech_to_text", data.speech_to_text),
                "text_to_speech": display_config.get("text_to_speech", data.text_to_speech),
                "suggested_after_answer": display_config.get("suggested_after_answer", data.suggested_after_answer),
                "review_config": display_config.get("review_config", data.review_config),
            },
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
            "is_current_published": is_current_published,
            "label": label,
            "summary": summary,
        }


class FallbackHistoryToDraftReq(FlaskForm):
    """回退历史版本到草稿请求结构体"""
    app_config_version_id = StringField("app_config_version_id", validators=[
        DataRequired("回退配置版本id不能为空")
    ])

    def validate_app_config_version_id(self, field: StringField) -> None:
        """校验回退配置版本id"""
        try:
            UUID(field.data)
        except Exception as e:
            raise ValidationError("回退配置版本id必须为UUID")


class UpdateDebugConversationSummaryReq(FlaskForm):
    """更新应用调试会话长期记忆请求体"""
    summary = StringField("summary", default="")


class DebugChatReq(FlaskForm):
    """应用调试会话请求结构体"""
    image_urls = ListField("image_urls", default=[])
    conversation_id = StringField("conversation_id", default="", validators=[Optional()])
    query = StringField("query", validators=[
        DataRequired("用户提问query不能为空"),
    ])

    def validate_conversation_id(self, field: StringField) -> None:
        """校验传递的会话id是否是UUID"""
        if not field.data:
            return
        try:
            UUID(field.data)
        except Exception:
            raise ValidationError("会话id格式必须为UUID")

    def validate_image_urls(self, field: ListField) -> None:
        """校验传递的图片URL链接列表"""
        # 1.校验数据类型如果为None则设置默认值空列表
        if not isinstance(field.data, list):
            return []

        # 2.校验数据的长度，最多不能超过5条URL记录
        if len(field.data) > 5:
            raise ValidationError("上传的图片数量不能超过5，请核实后重试")

        # 3.循环校验image_url是否为URL
        for image_url in field.data:
            result = urlparse(image_url)
            if not all([result.scheme, result.netloc]):
                raise ValidationError("上传的图片URL地址格式错误，请核实后重试")


class PromptCompareChatReq(FlaskForm):
    """提示词对比调试请求结构体"""
    lane_id = StringField("lane_id", default="", validators=[Optional(), Length(max=64)])
    query = StringField("query", validators=[
        DataRequired("用户提问query不能为空"),
        Length(max=4000, message="用户提问长度不能超过4000个字符"),
    ])
    preset_prompt = StringField("preset_prompt", validators=[
        DataRequired("提示词不能为空"),
        Length(max=5000, message="提示词长度不能超过5000个字符"),
    ])
    model_config = DictField("model_config")
    history = ListField("history", default=[])

    def validate_model_config(self, field: DictField) -> None:
        """校验传递的模型配置是否为字典"""
        if not isinstance(field.data, dict):
            raise ValidationError("模型配置格式错误 请核实后重试")

    def validate_history(self, field: ListField) -> None:
        """校验对比调试历史记录"""
        if field.data is None:
            field.data = []
            return

        if not isinstance(field.data, list):
            raise ValidationError("历史记录格式错误，请核实后重试")

        if len(field.data) > 20:
            raise ValidationError("历史记录条数不能超过20条，请核实后重试")

        normalized_history = []
        for item in field.data:
            if not isinstance(item, dict):
                raise ValidationError("历史记录格式错误，请核实后重试")

            if set(item.keys()) - {"query", "answer"}:
                raise ValidationError("历史记录字段出错，请核实后重试")

            query = item.get("query", "")
            answer = item.get("answer", "")
            if not isinstance(query, str) or not isinstance(answer, str):
                raise ValidationError("历史记录内容必须为字符串")

            if len(query) > 4000 or len(answer) > 20000:
                raise ValidationError("历史记录内容长度超出限制，请核实后重试")

            normalized_history.append({
                "query": query,
                "answer": answer,
            })

        field.data = normalized_history


class GetDebugConversationMessagesWithPageReq(PaginatorReq):
    """获取调试会话消息列表分页请求结构体"""
    created_at = IntegerField("created_at", default=0, validators=[
        Optional(),
        NumberRange(min=0, message="created_at游标最小值为0")
    ])
    conversation_id = StringField("conversation_id", default="", validators=[Optional()])

    def validate_conversation_id(self, field: StringField) -> None:
        """校验传递的会话id是否是UUID"""
        if not field.data:
            return
        try:
            UUID(field.data)
        except Exception:
            raise ValidationError("会话id格式必须为UUID")


class GetDebugConversationMessagesWithPageResp(Schema):
    """获取调试会话消息列表分页响应结构体"""
    id = fields.UUID(dump_default="")
    conversation_id = fields.UUID(dump_default="")
    query = fields.String(dump_default="")
    image_urls = fields.List(fields.String, dump_default=[])
    answer = fields.String(dump_default="")
    total_token_count = fields.Integer(dump_default=0)
    latency = fields.Float(dump_default=0)
    agent_thoughts = fields.List(fields.Dict, dump_default=[])
    suggested_questions = fields.List(fields.String, dump_default=[])
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Message, **kwargs):
        return {
            "id": data.id,
            "conversation_id": data.conversation_id,
            "query": data.query,
            "image_urls": data.image_urls,
            "answer": data.answer,
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
