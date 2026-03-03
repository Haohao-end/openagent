from dataclasses import dataclass
from flask_login import login_required, current_user
from injector import inject
from internal.schema.ai_schema import (
    CodeAssistantChatReq,
    GenerateSuggestedQuestionsReq,
    OpenAPISchemaAssistantChatReq,
    OptimizePromptReq,
)
from internal.service import AIService
from pkg.response import validate_error_json, compact_generate_response, success_json


@inject
@dataclass
class AIHandler:
    """AI辅助模块处理器"""
    ai_service: AIService

    @login_required
    def optimize_prompt(self):
        """根据传递的预设prompt进行优化"""
        # 1.提取请求并校验
        req = OptimizePromptReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务优化prompt
        resp = self.ai_service.optimize_prompt(req.prompt.data)

        return compact_generate_response(resp)

    @login_required
    def generate_suggested_questions(self):
        """根据传递的消息id生成建议问题列表"""
        # 1.提取请求并校验
        req = GenerateSuggestedQuestionsReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务生成建议问题列表
        suggested_questions = self.ai_service.generate_suggested_questions_from_message_id(
            req.message_id.data,
            current_user,
        )

        return success_json(suggested_questions)

    @login_required
    def code_assistant_chat(self):
        """代码助手聊天 - 流式输出"""
        # 1.提取请求并校验
        req = CodeAssistantChatReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务处理聊天 - 流式返回
        return compact_generate_response(
            self.ai_service.code_assistant_chat(req.question.data)
        )

    @login_required
    def openapi_schema_assistant_chat(self):
        """OpenAPI Schema 助手聊天 - 流式输出"""
        # 1.提取请求并校验
        req = OpenAPISchemaAssistantChatReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务处理聊天 - 流式返回
        return compact_generate_response(
            self.ai_service.openapi_schema_assistant_chat(req.question.data)
        )
