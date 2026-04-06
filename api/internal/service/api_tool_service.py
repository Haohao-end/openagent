import json
import logging
from typing import Any
from uuid import UUID
from pydantic import ValidationError
from internal.exception import ValidateErrorException, NotFoundException, FailException
from injector import inject
from dataclasses import dataclass
from internal.core.tools.api_tools.entities import OpenAPISchema
from internal.schema.api_tool_schema import (
    CreateApiToolReq,
    GetApiToolProvidersWithPageReq,
    UpdateApiToolProviderReq
)
from pkg.sqlalchemy import SQLAlchemy
from internal.model import ApiToolProvider, ApiTool, Account
from pkg.paginator import Paginator
from sqlalchemy import desc
from .base_service import BaseService
from internal.core.tools.api_tools.providers import ApiProviderManager
from .icon_generator_service import IconGeneratorService

@inject
@dataclass
class ApiToolService(BaseService):
    """自定义API插件服务"""
    db: SQLAlchemy
    api_provider_manager: ApiProviderManager
    icon_generator_service: IconGeneratorService
    def update_api_tool_provider(
            self,
            provider_id:UUID,
            req:UpdateApiToolProviderReq,
            account: Account
    ):
        """根据传递的provider_id+req更新对应的API工具提供者信息"""
        # 1.根据传递的provider_id查找API工具提供者信息并校验
        api_tool_provider = self.get(ApiToolProvider,provider_id)
        if api_tool_provider is None or api_tool_provider.account_id != account.id:
            raise ValidateErrorException("该工具提供者不存在")

        # 2.校验openapi_schema数据
        openapi_schema = self.parse_openapi_schema(req.openapi_schema.data)

        # 3.检测当前账号是否已经创建了除了此id以外同名的工具提供者 如果是则抛出错误
        check_api_tool_provider = self.db.session.query(ApiToolProvider).filter(
            ApiToolProvider.account_id == account.id,
            ApiToolProvider.name == req.name.data,
            ApiToolProvider.id != api_tool_provider.id,
        ).one_or_none()
        if check_api_tool_provider:
            raise ValidateErrorException(f"该工具提供者名字{req.name.data}已经存在")

        # 4.开启数据库的自动提交
        with self.db.auto_commit():
            # 5.先删除该工具提供者下的所有工具
            self.db.session.query(ApiTool).filter(
                ApiTool.provider_id == api_tool_provider.id,
                ApiTool.account_id == account.id,
            ).delete()

        # 6.修改工具提供者信息
        self.update(
            api_tool_provider,
            name=req.name.data,
            icon=req.icon.data,
            headers=req.headers.data,
            description=openapi_schema.description,
            openapi_schema=req.openapi_schema.data,
        )

        # 7.新增工具信息从而完成覆盖更新
        for path, path_item in openapi_schema.paths.items():
            for method, method_item in path_item.items():
                self.create(
                    ApiTool,
                    account_id=account.id,
                    provider_id=api_tool_provider.id,
                    name=method_item.get("operationId"),
                    description=method_item.get("description"),
                    url=f"{openapi_schema.server}{path}",
                    method=method,
                    parameters=method_item.get("parameters", []),
                )

    def get_api_tool_providers_wiith_page(
            self,
            req: GetApiToolProvidersWithPageReq,
            account: Account
    ) -> tuple[list[Any],Paginator]:
        """获取自定义API工具服务提供者分页列表数据"""
        # 1.构建分页查询器
        paginator = Paginator(db=self.db, req=req)

        # 2.构建筛选器
        filters = [ApiToolProvider.account_id == account.id]
        if req.search_word.data:
            filters.append(ApiToolProvider.name.ilike(f"%{req.search_word.data}%"))

        # 3.执行分页并获取数据
        api_tool_providers = paginator.paginate(
            self.db.session.query(ApiToolProvider).filter(*filters).order_by(desc("created_at"))
        )
        return api_tool_providers,paginator

    def get_api_tool(
            self,
            provider_id: UUID,
            tool_name: str,
            account: Account
    ) -> ApiTool:
        """根据传递的provider_id + tool_name获取对应的参数详情信息"""
        api_tool = self.db.session.query(ApiTool).filter_by(
            provider_id=provider_id,
            name=tool_name
        ).one_or_none()

        if api_tool is None or str(api_tool.account_id) != str(account.id):
            raise NotFoundException("该工具不存在")
        return api_tool

    def get_api_tool_provider(
            self,
            provider_id: UUID,
            account: Account
    ):
        """根据传递的provider_id获取API工具提供者信息"""
        # 1.查询数据库获取对应的数据
        api_tool_provider = self.get(ApiToolProvider,provider_id)

        # 2.检验数据是否为空 并且判断该数据是否属于当前帐号
        if api_tool_provider is None or str(api_tool_provider.account_id) != str(account.id):
            raise NotFoundException("该工具提供者不存在")
        return api_tool_provider

    def create_api_tool(
            self,
            req: CreateApiToolReq,
            account: Account
    ) -> None:
        """根据传递的请求创建自定义API工具"""
        # 1.检验并提取吧openapi_schema对应的数据
        openapi_schema = self.parse_openapi_schema(req.openapi_schema.data)

        # 2.查询当前登陆的账号是否已经创建了同名的工具提供者 如果是则抛出错误
        api_tool_provider = self.db.session.query(ApiToolProvider).filter_by(
            account_id=account.id,
            name=req.name.data
        ).one_or_none()
        if api_tool_provider:
            raise ValidateErrorException(f"该工具提供者名字{req.name.data}已存在")


        # 3.首先创建工具提供者 并获取工具提供者的id信息 然后创建工具信息
        api_tool_provider = self.create(
            ApiToolProvider,
            account_id=account.id,
            name=req.name.data,
            icon=req.icon.data,
            description=openapi_schema.description,
            openapi_schema=req.openapi_schema.data,
            headers=req.headers.data
        )

        # 4.创建api工具并关联api_tool_provider
        for path, path_item in openapi_schema.paths.items():
            for method,method_item in path_item.items():
                self.create(
                    ApiTool,
                    account_id=account.id,
                    provider_id=api_tool_provider.id,
                    name=method_item.get("operationId"),
                    description=method_item.get("description"),
                    url=f"{openapi_schema.server}{path}",
                    method=method,
                    parameters=method_item.get("parameters", []),
                )

    def delete_api_tool_provider(
            self,
            provider_id: UUID,
            account: Account
    ):
        """根据传递的provider_id删除对应工具提供商+工具的所有信息"""
        # 1.先查找数据 检测下provider_id对应的数据是否存在 权限是否正确
        api_tool_provider = self.get(ApiToolProvider, provider_id)
        if api_tool_provider is None or str(api_tool_provider.account_id) != str(account.id):
            raise NotFoundException("该工具提供者不存在")

        # 2.开启数据库的自动提交
        with self.db.auto_commit():
            # 3.先删除提供者对应的工具信息
            self.db.session.query(ApiTool).filter(
                ApiTool.provider_id == provider_id,
                ApiTool.account_id == account.id,
            ).delete()

            # 4.删除服务提供者
            self.db.session.delete(api_tool_provider)

    def regenerate_icon(self, provider_id: UUID, account: Account) -> str:
        """根据传递的provider_id重新生成插件图标"""
        # 1.获取插件提供者信息并校验权限
        api_tool_provider = self.get(ApiToolProvider, provider_id)
        if api_tool_provider is None or str(api_tool_provider.account_id) != str(account.id):
            raise NotFoundException("该工具提供者不存在")

        # 2.使用图标生成服务生成新图标
        try:
            logging.info(f"重新生成插件图标: provider_id={provider_id}, name={api_tool_provider.name}")
            icon_url = self.icon_generator_service.generate_icon(
                name=api_tool_provider.name,
                description=api_tool_provider.description or ""
            )
            logging.info(f"重新生成图标成功: {icon_url}")
        except Exception as e:
            logging.exception("重新生成图标失败: provider_id=%s", provider_id, exc_info=e)
            raise FailException("重新生成图标失败，请稍后重试")

        # 3.更新插件提供者图标
        self.update(api_tool_provider, icon=icon_url)

        return icon_url

    def generate_icon_preview(self, name: str, description: str) -> str:
        """生成图标预览（不保存到插件）"""
        try:
            logging.info(f"生成插件图标预览: name={name}")
            icon_url = self.icon_generator_service.generate_icon(
                name=name,
                description=description or ""
            )
            logging.info(f"生成图标预览成功: {icon_url}")
            return icon_url
        except Exception as e:
            logging.exception("生成图标预览失败: name=%s", name, exc_info=e)
            raise FailException("生成图标预览失败，请稍后重试")

    @classmethod
    def parse_openapi_schema(cls, openapi_schema_str: str) -> OpenAPISchema:
        """解析传递的openapi_schema字符串 如果出错则抛出错误"""
        try:
            data = json.loads((openapi_schema_str or "").strip())
        except json.JSONDecodeError as error:
            logging.debug("OpenAPI schema JSON解析失败: %s", error)
            raise ValidateErrorException("传递的数据必须符合OpenAPI规范的JSON字符串")

        if not isinstance(data, dict):
            logging.debug("OpenAPI schema JSON根节点必须是对象，当前类型: %s", type(data).__name__)
            raise ValidateErrorException("传递的数据必须符合OpenAPI规范的JSON字符串")

        try:
            return OpenAPISchema(**data)
        except ValidateErrorException as error:
            logging.debug("OpenAPI schema字段校验失败: %s", error)
            raise
        except ValidationError as error:
            first_error = error.errors()[0] if error.errors() else {}
            location = ".".join(str(item) for item in first_error.get("loc", []))
            message = first_error.get("msg", "字段校验失败")
            error_summary = f"{location}: {message}" if location else message
            logging.debug("OpenAPI schema结构校验失败: %s", error_summary)
            raise ValidateErrorException(f"OpenAPI schema格式错误: {error_summary}")
