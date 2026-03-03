from uuid import UUID
from flask import request
from injector import inject
from flask_login import login_required, current_user
from dataclasses import dataclass
from internal.schema.api_tool_schema import (
    ValidateOpenAPISchemaReq,
    CreateApiToolReq,
    GetApiToolProviderResp,
    GetApiToolResp,
    GetApiToolProvidersWithPageReq,
    GetApiToolProvidersWithPageResp,
    UpdateApiToolProviderReq
)
from pkg.response import validate_error_json,success_message, success_json
from internal.service import ApiToolService
from pkg.paginator import PageModel

@inject
@dataclass
class ApiToolHandler:
    """自定义API插件处理器"""
    api_tool_service: ApiToolService
    @login_required
    def update_api_tool_provider(self,provider_id:UUID):
        """更新自定义API工具提供者信息"""
        req = UpdateApiToolProviderReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.api_tool_service.update_api_tool_provider(provider_id, req, current_user)

        return success_message("更新自定义API插件成功")

    @login_required
    def get_api_tool_providers_with_page(self):
        """获取API工具提供者列表信息 该接口支持分页"""
        req = GetApiToolProvidersWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        api_tool_providers, paginator = self.api_tool_service.get_api_tool_providers_wiith_page(
            req,
            current_user
        )
        resp = GetApiToolProvidersWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(api_tool_providers),paginator=paginator))

    @login_required
    def get_api_tool(self, provider_id: UUID, tool_name: str):
        """根据传递的provider_id+tool_name获取工具的详细信息"""
        api_tool = self.api_tool_service.get_api_tool(provider_id, tool_name, current_user)

        resp = GetApiToolResp()

        return success_json(resp.dump(api_tool))

    @login_required
    def create_api_tool_provider(self):
        """创建自定义API工具"""
        # 1.提取请求的数据并校验
        req = CreateApiToolReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务创建API工具
        self.api_tool_service.create_api_tool(req, current_user)
        return success_message("创建自定义API插件成功")

    @login_required
    def get_api_tool_provider(self, provider_id: UUID):
        """根据传递的provider_id获取工具提供者的原始信息"""
        api_tool_provider = self.api_tool_service.get_api_tool_provider(provider_id, current_user)

        resp = GetApiToolProviderResp()

        return success_json(resp.dump(api_tool_provider))

    @login_required
    def delete_api_tool_provider(self,provider_id:UUID):
        """根据传递的provider_id删除对应工具提供者信息"""
        self.api_tool_service.delete_api_tool_provider(provider_id, current_user)

        return success_message("删除自定义API插件成功")

    @login_required
    def validate_openapi_schema(self):
        """校验传递的openapi_schema字符串是否正确"""
        # 1.提取前端的数据并进行校验
        req = ValidateOpenAPISchemaReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务并解析传递的数据
        self.api_tool_service.parse_openapi_schema(req.openapi_schema.data)

        return success_message("数据校验成功")

    @login_required
    def regenerate_icon(self, provider_id: UUID):
        """根据传递的provider_id重新生成插件图标"""
        icon_url = self.api_tool_service.regenerate_icon(provider_id, current_user)
        return success_json({"icon": icon_url})

    @login_required
    def generate_icon_preview(self):
        """根据传递的名称和描述生成图标预览（不保存到插件）"""
        # 1.获取请求数据
        data = request.get_json(force=True, silent=True) or {}
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()

        # 2.校验名称不能为空
        if not name:
            return validate_error_json({'name': ['插件名称不能为空']})

        # 3.调用服务生成图标
        icon_url = self.api_tool_service.generate_icon_preview(name, description)

        return success_json({"icon": icon_url})
