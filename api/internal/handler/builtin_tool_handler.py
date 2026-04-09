import io
from dataclasses import dataclass
from injector import inject
from internal.service import BuiltinToolService
from pkg.response import success_json
from flask import redirect, send_file

@inject
@dataclass
class BuiltinToolHandler:
    """内置工具处理器"""
    builtin_tool_service:BuiltinToolService
    def get_builtin_tools(self):
        """获取 OpenAgent 所有内置工具信息和提供商信息"""
        builtin_tools = self.builtin_tool_service.get_builtin_tools()
        return success_json(builtin_tools)

    def get_provider_tool(self,provider_name:str,tool_name:str):
        """根据传递的提供商名字+工具名字获取指定工具的信息"""
        builtin_tool = self.builtin_tool_service.get_provider_tool(provider_name,tool_name)
        return success_json(builtin_tool)

    def get_provider_icon(self,provider_name:str):
        """根据传递的提供商获取icon图标流信息"""
        icon, mimetype, icon_url = self.builtin_tool_service.get_provider_icon(provider_name)
        if icon_url:
            return redirect(icon_url)

        if icon is None:
            icon = b""

        return send_file(io.BytesIO(icon),mimetype)

    def get_categories(self):
        """获取所有内置提供商的分类信息"""
        categories = self.builtin_tool_service.get_categories()
        return success_json(categories)
