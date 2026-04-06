from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, FieldList, FormField
from wtforms.validators import DataRequired, UUID, Length, Optional

class OptimizePromptReq(FlaskForm):
    """优化预设prompt请求结构体"""
    prompt = StringField("prompt", validators=[
        DataRequired("预设prompt不能为空"),
        Length(max=2000, message="预设prompt的长度不能超过2000个字符")
    ])

class GenerateSuggestedQuestionsReq(FlaskForm):
    """生成建议问题列表请求结构体"""
    message_id = StringField("message_id", validators=[
        DataRequired("消息id不能为空"),
        UUID(message="消息id格式必须为uuid")
    ])

class CodeAssistantChatReq(FlaskForm):
    """代码助手聊天请求结构体"""
    question = StringField("question", validators=[
        DataRequired("问题不能为空"),
        Length(max=500, message="问题长度不能超过500个字符")
    ])


class OpenAPISchemaAssistantChatReq(FlaskForm):
    """OpenAPI Schema 助手聊天请求结构体"""
    question = StringField("question", validators=[
        DataRequired("需求描述不能为空"),
        Length(max=2000, message="需求描述长度不能超过2000个字符")
    ])



