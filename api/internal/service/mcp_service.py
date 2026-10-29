from __future__ import annotations

import base64
import logging
import math
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from injector import inject
from sqlalchemy import inspect, or_
from sqlalchemy.exc import ProgrammingError

from internal.core.tools.mcp_tools.entities import McpCatalogProvider
from internal.core.tools.mcp_tools.providers import McpProviderManager, McpToolFactory
from internal.entity.mcp_entity import (
    MCP_CATEGORY_OPTIONS,
    get_mcp_category_meta,
    normalize_mcp_category,
    normalize_mcp_transport,
)
from internal.exception import ForbiddenException, NotFoundException, ValidateErrorException
from internal.lib.helper import datetime_to_timestamp, sanitize_public_url, utc_now_naive
from internal.model import Account, McpProvider
from internal.schema.mcp_schema import CreateMcpProviderReq, GetMcpProvidersWithPageReq, UpdateMcpProviderReq
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy

from .base_service import BaseService
from .icon_generator_service import IconGeneratorService


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


@inject
@dataclass
class McpService(BaseService):
    """MCP 资源服务。"""

    db: SQLAlchemy
    mcp_provider_manager: McpProviderManager
    icon_generator_service: IconGeneratorService

    _tool_factory = McpToolFactory()

    @staticmethod
    def _encode_catalog_source_key(source_key: str) -> str:
        encoded = base64.urlsafe_b64encode(source_key.encode("utf-8")).decode("utf-8")
        return encoded.rstrip("=")

    @staticmethod
    def _decode_catalog_source_key(encoded_source_key: str) -> str:
        normalized = encoded_source_key.strip()
        padding = "=" * (-len(normalized) % 4)
        return base64.urlsafe_b64decode(f"{normalized}{padding}".encode("utf-8")).decode("utf-8")

    def _has_mcp_provider_table(self) -> bool:
        try:
            return inspect(self.db.engine).has_table(McpProvider.__tablename__)
        except Exception:
            return False

    @staticmethod
    def _is_missing_mcp_provider_table_error(error: Exception) -> bool:
        orig = getattr(error, "orig", None)
        if orig is not None:
            if getattr(orig, "pgcode", None) == "42P01":
                return True
            if orig.__class__.__name__ == "UndefinedTable":
                return True

        message = str(error).lower()
        return "mcp_provider" in message and "does not exist" in message

    def _ensure_mcp_provider_table(self) -> None:
        if not self._has_mcp_provider_table():
            raise ValidateErrorException("MCP 数据表尚未初始化，请先执行数据库迁移")

    def _provider_key_for_db(self, provider_id: UUID | str) -> str:
        return f"db::{provider_id}"

    def _provider_key_for_catalog(self, source_key: str) -> str:
        safe_source_key = self._encode_catalog_source_key(source_key)
        return f"catalog::{safe_source_key}"

    def _parse_provider_key(self, provider_key: str) -> tuple[str, str]:
        normalized = _normalize_text(provider_key)
        if normalized.startswith("db::"):
            return "db", normalized[4:]
        if normalized.startswith("catalog::"):
            try:
                source_key = self._decode_catalog_source_key(normalized[9:])
            except ValueError as exc:
                raise ValidateErrorException("MCP provider key 格式无效") from exc
            return "catalog", source_key
        try:
            UUID(normalized)
            return "db", normalized
        except Exception:
            return "catalog", normalized

    def _resolve_catalog_provider(self, source_key_or_name: str) -> McpCatalogProvider | None:
        normalized = _normalize_text(source_key_or_name)
        if not normalized:
            return None

        provider = self.mcp_provider_manager.get_provider(normalized)
        if provider:
            return provider

        for item in self.mcp_provider_manager.get_providers():
            provider_entity = item.provider_entity
            if provider_entity.source_key == normalized or provider_entity.name == normalized:
                return item
        return None

    def _normalize_binding(self, binding: dict[str, Any]) -> dict[str, Any]:
        transport = normalize_mcp_transport(binding.get("transport"))
        return {
            "name": _normalize_text(binding.get("name")),
            "description": _normalize_text(binding.get("description")),
            "transport": transport or "streamable_http",
            "url": _normalize_text(binding.get("url")),
            "command": _normalize_text(binding.get("command")),
            "enabled": bool(binding.get("enabled", True)),
            "headers": list(binding.get("headers") or []),
            "tool_names": list(binding.get("tool_names") or []),
            "timeout_seconds": int(binding.get("timeout_seconds") or 30),
            "args": list(binding.get("args") or []),
            "env": dict(binding.get("env") or {}),
            "provider_key": _normalize_text(binding.get("provider_key")),
            "source_type": _normalize_text(binding.get("source_type")),
            "source_key": _normalize_text(binding.get("source_key")),
            "source_url": _normalize_text(binding.get("source_url")),
            "label": _normalize_text(binding.get("label")),
            "icon": _normalize_text(binding.get("icon")),
            "category": _normalize_text(binding.get("category")),
        }

    def _is_binding_enabled(self, binding: dict[str, Any]) -> bool:
        if "enabled" in binding and not bool(binding.get("enabled")):
            return False

        transport = normalize_mcp_transport(binding.get("transport"))
        if transport == "stdio":
            return False

        if transport in {"http", "sse", "streamable_http"}:
            return bool(_normalize_text(binding.get("name"))) and bool(_normalize_text(binding.get("url")))

        return False

    def _binding_reason(self, binding: dict[str, Any]) -> str:
        transport = normalize_mcp_transport(binding.get("transport"))
        if transport == "stdio":
            return "当前环境未启用 MCP stdio 适配，无法直接绑定"
        if transport in {"http", "sse", "streamable_http"}:
            if not _normalize_text(binding.get("url")):
                return "HTTP/SSE 模式需要 url"
            return ""
        return "当前仅支持 http、sse、streamable_http 和 stdio"

    def _build_tool_inputs(self, input_schema: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not isinstance(input_schema, dict):
            return []

        properties = input_schema.get("properties") or {}
        required_fields = set(input_schema.get("required") or [])
        inputs: list[dict[str, Any]] = []
        if isinstance(properties, dict):
            for prop_name, prop_schema in properties.items():
                if not isinstance(prop_schema, dict):
                    prop_schema = {}
                schema_type = str(prop_schema.get("type") or "string")
                inputs.append({
                    "name": prop_name,
                    "type": schema_type,
                    "required": prop_name in required_fields,
                    "description": _normalize_text(prop_schema.get("description")),
                })
        return inputs

    def _build_tool_list(self, provider_dict: dict[str, Any]) -> list[dict[str, Any]]:
        tool_definitions = self._tool_factory.list_remote_tool_definitions(provider_dict)
        tools: list[dict[str, Any]] = []
        for tool_definition in tool_definitions:
            tool_name = _normalize_text(tool_definition.get("name"))
            if not tool_name:
                continue
            tools.append({
                "name": tool_name,
                "label": _normalize_text(tool_definition.get("title")) or tool_name,
                "description": _normalize_text(tool_definition.get("description")),
                "inputs": self._build_tool_inputs(
                    tool_definition.get("inputSchema") or tool_definition.get("input_schema"),
                ),
            })
        return tools

    def _build_binding_payload(self, provider_dict: dict[str, Any], provider_key: str) -> dict[str, Any]:
        binding = {
            "name": provider_dict["name"],
            "description": provider_dict["description"],
            "transport": provider_dict["transport"],
            "url": provider_dict.get("url", ""),
            "command": provider_dict.get("command", ""),
            "enabled": True,
            "headers": provider_dict.get("headers", []),
            "tool_names": provider_dict.get("tool_names", []),
            "timeout_seconds": provider_dict.get("timeout_seconds", 30),
            "args": provider_dict.get("args", []),
            "env": provider_dict.get("env", {}),
            "provider_key": provider_key,
            "source_type": provider_dict.get("source_type", ""),
            "source_key": provider_dict.get("source_key", ""),
            "source_url": provider_dict.get("source_url", ""),
            "label": provider_dict.get("label", ""),
            "icon": provider_dict.get("icon", ""),
            "category": provider_dict.get("category", ""),
        }
        return binding

    def _build_provider_payload(
        self,
        *,
        provider_key: str,
        provider_id: str,
        name: str,
        label: str,
        icon: str,
        description: str,
        category: str,
        transport: str,
        url: str,
        command: str,
        headers: list[dict[str, str]],
        tool_names: list[str],
        args: list[str],
        env: dict[str, str],
        timeout_seconds: int,
        source_type: str,
        source_key: str,
        source_url: str,
        creator_name: str = "",
        creator_avatar: str = "",
        is_public: bool = False,
        published_at=None,
        created_at=None,
        updated_at=None,
        include_tools: bool = False,
    ) -> dict[str, Any]:
        if is_public:
            url = sanitize_public_url(url)
            source_url = sanitize_public_url(source_url)
            command = ""
            args = []
        headers = [] if is_public else headers
        env = {} if is_public else env
        normalized_category = normalize_mcp_category(category, name=name, description=description)
        category_meta = get_mcp_category_meta(normalized_category)
        binding = self._normalize_binding({
            "name": name,
            "description": description,
            "transport": transport,
            "url": url,
            "command": command,
            "enabled": True,
            "headers": headers,
            "tool_names": tool_names,
            "timeout_seconds": timeout_seconds,
            "args": args,
            "env": env,
            "provider_key": provider_key,
            "source_type": source_type,
            "source_key": source_key,
            "source_url": source_url,
            "label": label,
            "icon": icon,
            "category": normalized_category,
        })
        is_bindable = self._is_binding_enabled(binding)
        bind_reason = self._binding_reason(binding) if not is_bindable else ""

        provider_dict = {
            "id": provider_id,
            "provider_key": provider_key,
            "name": name,
            "label": label or name,
            "icon": icon,
            "background": category_meta["background"],
            "description": description,
            "category": normalized_category,
            "transport": normalize_mcp_transport(transport) or "streamable_http",
            "url": url,
            "command": command,
            "headers": headers or [],
            "tool_names": tool_names or [],
            "args": args or [],
            "env": env or {},
            "timeout_seconds": int(timeout_seconds or 30),
            "source_type": source_type,
            "source_key": source_key,
            "source_url": source_url,
            "creator_name": creator_name,
            "creator_avatar": creator_avatar,
            "is_public": bool(is_public),
            "is_bindable": is_bindable,
            "bind_reason": bind_reason,
            "published_at": datetime_to_timestamp(published_at),
            "created_at": datetime_to_timestamp(created_at),
            "updated_at": datetime_to_timestamp(updated_at),
            "tool_count": 0,
            "tools": [],
            "binding": binding,
        }

        if include_tools:
            tools = self._build_tool_list(binding) if is_bindable else []
            provider_dict["tools"] = tools
            provider_dict["tool_count"] = len(tools)
        return provider_dict

    def _build_private_provider_payload(self, provider: McpProvider, *, include_tools: bool = False) -> dict[str, Any]:
        creator_name = provider.account.name if provider.account else ""
        creator_avatar = provider.account.avatar if provider.account else ""
        provider_key = self._provider_key_for_db(provider.id)
        return self._build_provider_payload(
            provider_key=provider_key,
            provider_id=str(provider.id),
            name=provider.name,
            label=provider.label,
            icon=provider.icon,
            description=provider.description,
            category=provider.category,
            transport=provider.transport,
            url=provider.url,
            command=provider.command,
            headers=list(provider.headers or []),
            tool_names=list(provider.tool_names or []),
            args=list(provider.args or []),
            env=dict(provider.env or {}),
            timeout_seconds=provider.timeout_seconds or 30,
            source_type=provider.source_type or "custom",
            source_key=provider.source_key or "",
            source_url=provider.source_url or "",
            creator_name=creator_name,
            creator_avatar=creator_avatar,
            is_public=provider.is_public,
            published_at=provider.published_at,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
            include_tools=include_tools,
        )

    def _build_catalog_provider_payload(self, catalog_provider: McpCatalogProvider, *, include_tools: bool = False) -> dict[str, Any]:
        provider_entity = catalog_provider.provider_entity
        provider_key = self._provider_key_for_catalog(provider_entity.source_key or provider_entity.name)
        return self._build_provider_payload(
            provider_key=provider_key,
            provider_id=provider_key,
            name=provider_entity.name,
            label=provider_entity.label,
            icon=provider_entity.icon,
            description=provider_entity.description,
            category=provider_entity.category,
            transport=provider_entity.transport,
            url=provider_entity.url,
            command=provider_entity.command,
            headers=list(provider_entity.headers or []),
            tool_names=list(provider_entity.tool_names or []),
            args=list(provider_entity.args or []),
            env=dict(provider_entity.env or {}),
            timeout_seconds=provider_entity.timeout_seconds or 30,
            source_type=provider_entity.source_type or "catalog",
            source_key=provider_entity.source_key or provider_entity.name,
            source_url=provider_entity.source_url or "",
            creator_name="公开目录",
            creator_avatar="",
            is_public=bool(provider_entity.is_public),
            published_at=provider_entity.created_at,
            created_at=provider_entity.created_at,
            updated_at=provider_entity.created_at,
            include_tools=include_tools,
        )

    def _resolve_private_provider(self, provider_id: UUID | str, account: Account) -> McpProvider:
        self._ensure_mcp_provider_table()
        provider = self.db.session.query(McpProvider).filter(McpProvider.id == provider_id).one_or_none()
        if not provider:
            raise NotFoundException("MCP 不存在")
        if provider.account_id != account.id:
            raise ForbiddenException("无权限操作该 MCP")
        return provider

    def _get_public_candidates(self) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for catalog_provider in self.mcp_provider_manager.get_providers():
            payload = self._build_catalog_provider_payload(catalog_provider, include_tools=False)
            candidates.append(payload)

        if self._has_mcp_provider_table():
            try:
                public_rows = (
                    self.db.session.query(McpProvider)
                    .filter(McpProvider.is_public == True)
                    .order_by(McpProvider.published_at.desc().nullslast(), McpProvider.created_at.desc())
                    .all()
                )
            except ProgrammingError as exc:
                if not self._is_missing_mcp_provider_table_error(exc):
                    raise
                public_rows = []

            for provider in public_rows:
                candidates.append(self._build_private_provider_payload(provider, include_tools=False))

        # 先按 provider_key 去重，再按发布时间倒序排序。
        deduped: dict[str, dict[str, Any]] = {}
        for item in candidates:
            deduped[item["provider_key"]] = item

        return sorted(
            deduped.values(),
            key=lambda item: (
                int(item.get("published_at") or 0),
                int(item.get("created_at") or 0),
            ),
            reverse=True,
        )

    def get_mcp_categories(self) -> list[dict[str, Any]]:
        return MCP_CATEGORY_OPTIONS

    def get_mcp_providers_with_page(
        self,
        req: GetMcpProvidersWithPageReq,
        account: Account,
    ) -> tuple[list[dict[str, Any]], Paginator]:
        """获取个人 MCP 列表。"""
        paginator = Paginator(db=self.db, req=req)
        if not self._has_mcp_provider_table():
            paginator.total_record = 0
            paginator.total_page = 0
            return [], paginator

        query = self.db.session.query(McpProvider).filter(McpProvider.account_id == account.id)

        if req.search_word.data:
            search_word = f"%{req.search_word.data.strip()}%"
            query = query.filter(
                or_(
                    McpProvider.name.ilike(search_word),
                    McpProvider.label.ilike(search_word),
                    McpProvider.description.ilike(search_word),
                    McpProvider.source_key.ilike(search_word),
                    McpProvider.source_url.ilike(search_word),
                )
            )

        if req.category.data:
            category = normalize_mcp_category(req.category.data)
            query = query.filter(McpProvider.category == category)

        query = query.order_by(McpProvider.updated_at.desc(), McpProvider.created_at.desc())
        try:
            providers = paginator.paginate(query)
        except ProgrammingError as exc:
            if not self._is_missing_mcp_provider_table_error(exc):
                raise
            paginator.total_record = 0
            paginator.total_page = 0
            return [], paginator
        return [self._build_private_provider_payload(provider, include_tools=False) for provider in providers], paginator

    def get_public_mcp_providers_with_page(
        self,
        req: GetMcpProvidersWithPageReq,
        account: Account | None = None,
    ) -> tuple[list[dict[str, Any]], Paginator]:
        """获取公共 MCP 广场列表。"""
        del account
        paginator = Paginator(db=self.db, req=req)
        candidates = self._get_public_candidates()

        search_word = _normalize_text(req.search_word.data).lower()
        category = normalize_mcp_category(req.category.data) if req.category.data else ""

        filtered: list[dict[str, Any]] = []
        for item in candidates:
            if category and item["category"] != category:
                continue
            if search_word:
                search_scope = " ".join([
                    item.get("name", ""),
                    item.get("label", ""),
                    item.get("description", ""),
                    item.get("source_key", ""),
                    item.get("source_url", ""),
                ]).lower()
                if search_word not in search_scope:
                    continue
            filtered.append(item)

        total = len(filtered)
        paginator.total_record = total
        paginator.total_page = math.ceil(total / paginator.page_size) if paginator.page_size else 0
        paginator.current_page = req.current_page.data
        paginator.page_size = req.page_size.data

        start = max((req.current_page.data - 1) * req.page_size.data, 0)
        end = start + req.page_size.data
        return filtered[start:end], paginator

    def get_mcp_provider(self, provider_id: UUID, account: Account) -> dict[str, Any]:
        provider = self._resolve_private_provider(provider_id, account)
        return self._build_private_provider_payload(provider, include_tools=True)

    def get_public_mcp_provider(self, provider_key: str, account: Account | None = None) -> dict[str, Any]:
        del account
        provider_type, raw_key = self._parse_provider_key(provider_key)
        if provider_type == "db":
            if not self._has_mcp_provider_table():
                raise NotFoundException("MCP 不存在或未公开")
            try:
                provider_uuid = UUID(raw_key)
            except Exception as exc:
                raise NotFoundException("MCP 不存在") from exc

            try:
                provider = self.db.session.query(McpProvider).filter(
                    McpProvider.id == provider_uuid,
                    McpProvider.is_public == True,
                ).one_or_none()
            except ProgrammingError as exc:
                if not self._is_missing_mcp_provider_table_error(exc):
                    raise
                raise NotFoundException("MCP 不存在或未公开") from exc
            if not provider:
                raise NotFoundException("MCP 不存在或未公开")
            return self._build_private_provider_payload(provider, include_tools=True)

        catalog_provider = self._resolve_catalog_provider(raw_key)
        if not catalog_provider:
            raise NotFoundException("MCP 不存在")
        return self._build_catalog_provider_payload(catalog_provider, include_tools=True)

    def create_mcp_provider(self, req: CreateMcpProviderReq, account: Account) -> McpProvider:
        self._ensure_mcp_provider_table()
        label = _normalize_text(req.label.data) or _normalize_text(req.name.data)
        category = normalize_mcp_category(req.category.data, name=req.name.data, description=req.description.data)
        provider = McpProvider(
            account_id=account.id,
            name=req.name.data.strip(),
            label=label,
            icon=_normalize_text(req.icon.data),
            description=req.description.data.strip(),
            category=category,
            transport=normalize_mcp_transport(req.transport.data) or "streamable_http",
            url=_normalize_text(req.url.data),
            command=_normalize_text(req.command.data),
            headers=req.headers.data or [],
            tool_names=req.tool_names.data or [],
            args=req.args.data or [],
            env=req.env.data or {},
            timeout_seconds=int(req.timeout_seconds.data or 30),
            is_public=False,
            source_type="custom",
            source_key="",
            source_url="",
        )
        with self.db.auto_commit():
            self.db.session.add(provider)
        return provider

    def update_mcp_provider(self, provider_id: UUID, req: UpdateMcpProviderReq, account: Account) -> McpProvider:
        provider = self._resolve_private_provider(provider_id, account)
        label = _normalize_text(req.label.data) or _normalize_text(req.name.data)
        category = normalize_mcp_category(req.category.data, name=req.name.data, description=req.description.data)
        self.update(
            provider,
            name=req.name.data.strip(),
            label=label,
            icon=_normalize_text(req.icon.data),
            description=req.description.data.strip(),
            category=category,
            transport=normalize_mcp_transport(req.transport.data) or "streamable_http",
            url=_normalize_text(req.url.data),
            command=_normalize_text(req.command.data),
            headers=req.headers.data or [],
            tool_names=req.tool_names.data or [],
            args=req.args.data or [],
            env=req.env.data or {},
            timeout_seconds=int(req.timeout_seconds.data or 30),
        )
        return provider

    def delete_mcp_provider(self, provider_id: UUID, account: Account) -> McpProvider:
        provider = self._resolve_private_provider(provider_id, account)
        self.delete(provider)
        return provider

    def publish_mcp_provider(self, provider_id: UUID, account: Account) -> McpProvider:
        provider = self._resolve_private_provider(provider_id, account)
        if not _normalize_text(provider.name) or not _normalize_text(provider.description):
            raise ValidateErrorException("请先补全 MCP 名称和描述")

        self.update(
            provider,
            is_public=True,
            published_at=utc_now_naive(),
        )
        return provider

    def unpublish_mcp_provider(self, provider_id: UUID, account: Account) -> McpProvider:
        provider = self._resolve_private_provider(provider_id, account)
        self.update(
            provider,
            is_public=False,
            published_at=None,
        )
        return provider

    def regenerate_icon(self, provider_id: UUID, account: Account) -> str:
        provider = self._resolve_private_provider(provider_id, account)
        icon = self.icon_generator_service.generate_icon(provider.name, provider.description)
        self.update(provider, icon=icon)
        return icon

    def generate_icon_preview(self, name: str, description: str) -> str:
        return self.icon_generator_service.generate_icon(name, description)
