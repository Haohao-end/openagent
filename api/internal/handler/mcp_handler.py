from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import current_user, login_required
from injector import inject

from internal.schema.mcp_schema import (
    CreateMcpProviderReq,
    GetMcpCategoriesResp,
    GetMcpProvidersWithPageReq,
    McpProviderResp,
    UpdateMcpProviderReq,
)
from internal.service.mcp_service import McpService
from pkg.paginator import PageModel
from pkg.response import compact_generate_response, success_json, success_message, validate_error_json


@inject
@dataclass
class McpHandler:
    """MCP 处理器。"""

    mcp_service: McpService

    def get_mcp_categories(self):
        """获取 MCP 分类列表。"""
        resp = GetMcpCategoriesResp()
        return success_json(resp.dump({}))

    def get_public_mcp_providers_with_page(self):
        """获取公共 MCP 广场列表。"""
        req = GetMcpProvidersWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        try:
            account = current_user if current_user.is_authenticated else None
        except Exception:
            account = None

        providers, paginator = self.mcp_service.get_public_mcp_providers_with_page(req, account)
        resp = McpProviderResp(many=True)
        return success_json(PageModel(list=resp.dump(providers), paginator=paginator))

    def get_public_mcp_provider(self, provider_key: str):
        """获取公共 MCP 详情。"""
        try:
            account = current_user if current_user.is_authenticated else None
        except Exception:
            account = None

        provider = self.mcp_service.get_public_mcp_provider(provider_key, account)
        resp = McpProviderResp()
        return success_json(resp.dump(provider))

    @login_required
    def get_mcp_categories_for_space(self):
        """获取个人空间 MCP 分类列表。"""
        return self.get_mcp_categories()

    @login_required
    def get_mcp_providers_with_page(self):
        """获取个人 MCP 列表。"""
        req = GetMcpProvidersWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        providers, paginator = self.mcp_service.get_mcp_providers_with_page(req, current_user)
        resp = McpProviderResp(many=True)
        return success_json(PageModel(list=resp.dump(providers), paginator=paginator))

    @login_required
    def get_mcp_provider(self, provider_id: UUID):
        """获取个人 MCP 详情。"""
        provider = self.mcp_service.get_mcp_provider(provider_id, current_user)
        resp = McpProviderResp()
        return success_json(resp.dump(provider))

    @login_required
    def create_mcp_provider(self):
        """创建 MCP。"""
        req = CreateMcpProviderReq()
        if not req.validate():
            return validate_error_json(req.errors)

        provider = self.mcp_service.create_mcp_provider(req, current_user)
        return success_json({"id": str(provider.id)})

    @login_required
    def update_mcp_provider(self, provider_id: UUID):
        """更新 MCP。"""
        req = UpdateMcpProviderReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.mcp_service.update_mcp_provider(provider_id, req, current_user)
        return success_message("更新 MCP 成功")

    @login_required
    def delete_mcp_provider(self, provider_id: UUID):
        """删除 MCP。"""
        self.mcp_service.delete_mcp_provider(provider_id, current_user)
        return success_message("删除 MCP 成功")

    @login_required
    def publish_mcp_provider(self, provider_id: UUID):
        """发布 MCP 到广场。"""
        self.mcp_service.publish_mcp_provider(provider_id, current_user)
        return success_message("MCP 已发布到广场")

    @login_required
    def unpublish_mcp_provider(self, provider_id: UUID):
        """取消 MCP 发布。"""
        self.mcp_service.unpublish_mcp_provider(provider_id, current_user)
        return success_message("MCP 已取消发布")

    @login_required
    def regenerate_icon(self, provider_id: UUID):
        """重新生成 MCP 图标。"""
        icon = self.mcp_service.regenerate_icon(provider_id, current_user)
        return success_json({"icon": icon})

    @login_required
    def generate_icon_preview(self):
        """生成 MCP 图标预览。"""
        data = request.get_json(force=True, silent=True) or {}
        raw_name = data.get("name")
        raw_description = data.get("description")
        name = raw_name.strip() if isinstance(raw_name, str) else ""
        description = raw_description.strip() if isinstance(raw_description, str) else ""
        if not name:
            return validate_error_json({"name": ["MCP 名称不能为空"]})

        icon = self.mcp_service.generate_icon_preview(name, description)
        return success_json({"icon": icon})

