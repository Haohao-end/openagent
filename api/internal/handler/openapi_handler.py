from dataclasses import dataclass
from injector import inject
from flask_login import login_required, current_user
from internal.schema.openapi_schema import OpenAPIChatReq
from pkg.response import validate_error_json, compact_generate_response
from internal.service.openapi_service import OpenAPIService

@inject
@dataclass
class OpenAPIHandler:
    """开放API处理器"""
    openapi_service: OpenAPIService

    @login_required
    def chat(self):
        """开放Chat对话接口"""
        # 1.提取请求并校验数据
        req = OpenAPIChatReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务创建会话
        resp = self.openapi_service.chat(req, current_user)

        return compact_generate_response(resp)
