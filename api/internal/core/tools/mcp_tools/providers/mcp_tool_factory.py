from __future__ import annotations

import json
import logging
import hashlib
import requests
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from langchain_core.tools import BaseTool, StructuredTool

from .mcp_schema_compiler import McpSchemaCompiler
from internal.exception import FailException
from internal.lib.safe_http_client import safe_request

DEFAULT_MCP_TOOL_TIMEOUT_SECONDS = 30
SUPPORTED_HTTP_TRANSPORTS = {"http", "sse", "streamable_http", "streamable-http"}
SUPPORTED_STDIO_TRANSPORTS = {"stdio"}


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_headers(raw_headers: Any) -> dict[str, str]:
    headers: dict[str, str] = {}
    if not isinstance(raw_headers, list):
        return headers

    for header in raw_headers:
        if not isinstance(header, dict):
            continue
        key = _normalize_text(header.get("key"))
        value = _normalize_text(header.get("value"))
        if key:
            headers[key] = value
    return headers


def _parse_json_payload(text: str, expected_id: str | None = None) -> dict[str, Any] | list[Any] | str | None:
    normalized = _normalize_text(text)
    if not normalized:
        return None

    try:
        payload = json.loads(normalized)
    except Exception:
        payload = None
    if isinstance(payload, dict) and (expected_id is None or payload.get("id") == expected_id):
        return payload
    if isinstance(payload, list):
        if expected_id is None:
            return payload
        matched = next(
            (item for item in payload if isinstance(item, dict) and item.get("id") == expected_id), None
        )
        if matched is not None:
            return matched

    data_blocks: list[str] = []
    current_data: list[str] = []
    for line in normalized.splitlines():
        if line.startswith("data:"):
            current_data.append(line[5:].strip())
        elif not line and current_data:
            data_blocks.append("\n".join(current_data))
            current_data = []

    if current_data:
        data_blocks.append("\n".join(current_data))

    last_payload = None
    for block in data_blocks:
        try:
            payload = json.loads(block)
        except Exception:
            continue
        if isinstance(payload, (dict, list)):
            last_payload = payload
            if isinstance(payload, dict) and payload.get("id") == expected_id:
                return payload
            if isinstance(payload, list):
                matched = next(
                    (item for item in payload if isinstance(item, dict) and item.get("id") == expected_id), None
                )
                if matched is not None:
                    return matched

    if expected_id is not None:
        raise FailException("未找到与请求ID匹配的MCP响应")
    if last_payload is not None:
        return last_payload

    return normalized


def _extract_text_from_mcp_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        fragments: list[str] = []
        for item in content:
            if isinstance(item, str):
                fragments.append(item)
                continue
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and item.get("text"):
                fragments.append(str(item.get("text", "")).strip())
                continue
            if item.get("text"):
                fragments.append(str(item.get("text", "")).strip())
                continue
            fragments.append(json.dumps(item, ensure_ascii=False))
        return "\n".join(fragment for fragment in fragments if fragment).strip()

    if isinstance(content, dict):
        if content.get("text"):
            return str(content.get("text", "")).strip()
        return json.dumps(content, ensure_ascii=False)

    return str(content).strip()


def _normalize_tool_arguments(arguments: Any) -> Any:
    if hasattr(arguments, "model_dump") and callable(getattr(arguments, "model_dump")):
        arguments = arguments.model_dump()

    if isinstance(arguments, dict):
        return {key: _normalize_tool_arguments(value) for key, value in arguments.items()}
    if isinstance(arguments, list):
        return [_normalize_tool_arguments(value) for value in arguments]
    if isinstance(arguments, tuple):
        return [_normalize_tool_arguments(value) for value in arguments]
    return arguments


def _utc_timestamp() -> int:
    return int(datetime.now(UTC).timestamp())


@dataclass
class McpToolFactory:
    """将 MCP Server 绑定动态展开为 LangChain 工具。"""

    timeout_seconds: int = DEFAULT_MCP_TOOL_TIMEOUT_SECONDS
    schema_compiler: McpSchemaCompiler = field(default_factory=McpSchemaCompiler)

    @staticmethod
    def build_binding_identity(binding: dict[str, Any] | None) -> str:
        """构建 MCP 绑定的稳定标识，用于快照匹配。"""
        if not isinstance(binding, dict):
            return ""

        provider_key = _normalize_text(binding.get("provider_key"))
        if provider_key:
            return provider_key

        transport = _normalize_text(binding.get("transport")).lower() or "streamable_http"
        endpoint = _normalize_text(binding.get("url") or binding.get("command"))
        name = _normalize_text(binding.get("name"))
        if not endpoint and not name:
            return ""
        return f"{transport}:{endpoint}:{name}"

    @staticmethod
    def _normalize_snapshot_identity(snapshot: dict[str, Any] | None) -> str:
        if not isinstance(snapshot, dict):
            return ""
        identity = _normalize_text(snapshot.get("binding_identity"))
        if identity:
            return identity
        binding = snapshot.get("binding")
        if isinstance(binding, dict):
            return McpToolFactory.build_binding_identity(binding)
        return ""

    @staticmethod
    def _binding_hash(binding: dict[str, Any]) -> str:
        try:
            payload = json.dumps(binding or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        except Exception:
            payload = json.dumps({}, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _snapshot_tool_names(tool_definitions: list[dict[str, Any]] | None) -> list[str]:
        tool_names: list[str] = []
        for tool_definition in tool_definitions or []:
            if not isinstance(tool_definition, dict):
                continue
            tool_name = _normalize_text(tool_definition.get("name"))
            if tool_name:
                tool_names.append(tool_name)
        return tool_names

    @staticmethod
    def _snapshot_schema_hash(tool_definitions: list[dict[str, Any]] | None) -> str:
        try:
            payload = json.dumps(tool_definitions or [], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        except Exception:
            payload = json.dumps([], ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _build_snapshot_payload(
        self,
        *,
        binding: dict[str, Any],
        status: str,
        tool_definitions: list[dict[str, Any]] | None,
        existing_snapshot: dict[str, Any] | None = None,
        last_error: str = "",
        retryable: bool = False,
        retry_count: int | None = None,
        last_success_at: int | None = None,
        last_attempt_at: int | None = None,
    ) -> dict[str, Any]:
        normalized_binding = dict(binding)
        binding_identity = self.build_binding_identity(normalized_binding)
        existing_snapshot = existing_snapshot if isinstance(existing_snapshot, dict) else {}
        normalized_tool_definitions = [tool for tool in (tool_definitions or []) if isinstance(tool, dict)]
        tool_names = self._snapshot_tool_names(normalized_tool_definitions)
        binding_hash = self._binding_hash(normalized_binding)
        existing_tool_definitions = existing_snapshot.get("tool_definitions")
        if isinstance(existing_tool_definitions, list):
            existing_tool_definitions = [tool for tool in existing_tool_definitions if isinstance(tool, dict)]
        else:
            existing_tool_definitions = []

        if status == "warming" and not normalized_tool_definitions and existing_tool_definitions:
            normalized_tool_definitions = existing_tool_definitions
            tool_names = self._snapshot_tool_names(normalized_tool_definitions)

        if status in {"stale", "ready"} and not normalized_tool_definitions and existing_tool_definitions:
            normalized_tool_definitions = existing_tool_definitions
            tool_names = self._snapshot_tool_names(normalized_tool_definitions)

        if last_success_at is None:
            existing_last_success_at = existing_snapshot.get("last_success_at")
            if isinstance(existing_last_success_at, int):
                last_success_at = existing_last_success_at

        if last_attempt_at is None:
            last_attempt_at = _utc_timestamp()

        if not last_error:
            existing_last_error = existing_snapshot.get("last_error")
            if isinstance(existing_last_error, str):
                last_error = existing_last_error

        snapshot = {
            "binding_identity": binding_identity,
            "binding_hash": binding_hash,
            "binding": normalized_binding,
            "status": status,
            "tool_definitions": normalized_tool_definitions,
            "tool_names": tool_names,
            "tool_count": len(normalized_tool_definitions),
            "schema_hash": self._snapshot_schema_hash(normalized_tool_definitions),
            "last_attempt_at": last_attempt_at,
            "last_success_at": last_success_at,
            "last_error": last_error,
            "retry_count": int(existing_snapshot.get("retry_count") or 0) if retry_count is None else int(retry_count),
            "retryable": retryable,
        }
        return snapshot

    def prepare_binding_snapshots(
        self,
        mcp_bindings: list[dict[str, Any]] | None,
        existing_snapshots: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """根据当前绑定列表准备预热中的 MCP 快照，不做远端发现。"""
        if not isinstance(mcp_bindings, list):
            return []

        snapshot_map = {
            self._normalize_snapshot_identity(snapshot): snapshot
            for snapshot in existing_snapshots or []
            if isinstance(snapshot, dict)
        }
        snapshots: list[dict[str, Any]] = []
        for binding in mcp_bindings:
            if not isinstance(binding, dict):
                continue

            binding_identity = self.build_binding_identity(binding)
            existing_snapshot = snapshot_map.get(binding_identity, {})
            status = "warming"
            retryable = True
            if not self._is_binding_enabled(binding):
                status = "disabled"
                retryable = False
            elif isinstance(existing_snapshot, dict):
                existing_status = _normalize_text(existing_snapshot.get("status")).lower()
                existing_tool_definitions = existing_snapshot.get("tool_definitions")
                has_existing_tools = isinstance(existing_tool_definitions, list) and bool(existing_tool_definitions)
                if existing_status == "ready" and has_existing_tools:
                    status = "ready"
                    retryable = False
                elif existing_status == "stale" and has_existing_tools:
                    status = "stale"
                elif existing_status == "failed" and has_existing_tools:
                    status = "stale"

            snapshots.append(
                self._build_snapshot_payload(
                    binding=binding,
                    status=status,
                    tool_definitions=(existing_snapshot.get("tool_definitions") if isinstance(existing_snapshot, dict) else []),
                    existing_snapshot=existing_snapshot,
                    retryable=retryable,
                )
            )

        return snapshots

    def refresh_binding_snapshots(
        self,
        mcp_bindings: list[dict[str, Any]] | None,
        existing_snapshots: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """根据当前绑定列表远端刷新 MCP 快照。"""
        if not isinstance(mcp_bindings, list):
            return []

        snapshot_map = {
            self._normalize_snapshot_identity(snapshot): snapshot
            for snapshot in existing_snapshots or []
            if isinstance(snapshot, dict)
        }
        snapshots: list[dict[str, Any]] = []
        for binding in mcp_bindings:
            if not isinstance(binding, dict):
                continue

            binding_identity = self.build_binding_identity(binding)
            existing_snapshot = snapshot_map.get(binding_identity, {})
            if not self._is_binding_enabled(binding):
                snapshots.append(
                    self._build_snapshot_payload(
                        binding=binding,
                        status="disabled",
                        tool_definitions=existing_snapshot.get("tool_definitions") if isinstance(existing_snapshot, dict) else [],
                        existing_snapshot=existing_snapshot,
                        retry_count=int(existing_snapshot.get("retry_count") or 0) if isinstance(existing_snapshot, dict) else 0,
                        retryable=False,
                    )
                )
                continue

            transport = self._normalize_transport(binding.get("transport"))
            if transport in SUPPORTED_STDIO_TRANSPORTS:
                snapshots.append(
                    self._build_snapshot_payload(
                        binding=binding,
                        status="unsupported",
                        tool_definitions=existing_snapshot.get("tool_definitions") if isinstance(existing_snapshot, dict) else [],
                        existing_snapshot=existing_snapshot,
                        last_error="当前环境未启用 MCP stdio 适配",
                        retry_count=int(existing_snapshot.get("retry_count") or 0) if isinstance(existing_snapshot, dict) else 0,
                        retryable=False,
                    )
                )
                continue
            if transport not in SUPPORTED_HTTP_TRANSPORTS:
                snapshots.append(
                    self._build_snapshot_payload(
                        binding=binding,
                        status="unsupported",
                        tool_definitions=existing_snapshot.get("tool_definitions") if isinstance(existing_snapshot, dict) else [],
                        existing_snapshot=existing_snapshot,
                        last_error="不支持的 MCP transport",
                        retry_count=int(existing_snapshot.get("retry_count") or 0) if isinstance(existing_snapshot, dict) else 0,
                        retryable=False,
                    )
                )
                continue

            existing_binding_hash = _normalize_text(existing_snapshot.get("binding_hash")) if isinstance(existing_snapshot, dict) else ""
            current_binding_hash = self._binding_hash(binding)
            existing_status = _normalize_text(existing_snapshot.get("status")).lower() if isinstance(existing_snapshot, dict) else ""
            existing_tool_definitions = existing_snapshot.get("tool_definitions") if isinstance(existing_snapshot, dict) else []
            if (
                existing_snapshot
                and existing_binding_hash == current_binding_hash
                and existing_status == "ready"
                and isinstance(existing_tool_definitions, list)
                and existing_tool_definitions
            ):
                snapshots.append(
                    self._build_snapshot_payload(
                        binding=binding,
                        status="ready",
                        tool_definitions=existing_tool_definitions,
                        existing_snapshot=existing_snapshot,
                        retry_count=0,
                        retryable=False,
                    )
                )
                continue

            try:
                tool_definitions = self._list_remote_tools(binding)
                allow_tool_names = {
                    _normalize_text(tool_name)
                    for tool_name in (binding.get("tool_names") or [])
                    if _normalize_text(tool_name)
                }
                if allow_tool_names:
                    tool_definitions = [
                        tool_definition
                        for tool_definition in tool_definitions
                        if _normalize_text(tool_definition.get("name")) in allow_tool_names
                    ]
                status = "ready" if tool_definitions else "empty"
                snapshots.append(
                    self._build_snapshot_payload(
                        binding=binding,
                        status=status,
                        tool_definitions=tool_definitions,
                        existing_snapshot=existing_snapshot,
                        last_success_at=_utc_timestamp(),
                        retry_count=0,
                        retryable=False,
                    )
                )
            except Exception as exc:
                logging.exception("读取 MCP 工具列表失败，已记录为快照状态: %s", exc)
                existing_tool_definitions = existing_snapshot.get("tool_definitions") if isinstance(existing_snapshot, dict) else []
                has_existing_tools = isinstance(existing_tool_definitions, list) and bool(existing_tool_definitions)
                retry_count = int(existing_snapshot.get("retry_count") or 0) + 1 if isinstance(existing_snapshot, dict) else 1
                snapshots.append(
                    self._build_snapshot_payload(
                        binding=binding,
                        status="stale" if has_existing_tools else "failed",
                        tool_definitions=existing_tool_definitions if has_existing_tools else [],
                        existing_snapshot=existing_snapshot,
                        last_error=str(exc),
                        retry_count=retry_count,
                        retryable=True,
                    )
                )

        return snapshots

    def get_tools(self, mcp_bindings: list[dict[str, Any]] | None, mcp_tool_snapshots: list[dict[str, Any]] | None = None) -> list[BaseTool]:
        """根据 MCP 绑定列表构建 LangChain 工具列表。"""
        if mcp_tool_snapshots is not None:
            return self._get_tools_from_snapshots(mcp_bindings, mcp_tool_snapshots)

        tools: list[BaseTool] = []
        for binding in mcp_bindings or []:
            if not isinstance(binding, dict):
                continue

            if not self._is_binding_enabled(binding):
                continue

            transport = self._normalize_transport(binding.get("transport"))
            if transport in SUPPORTED_STDIO_TRANSPORTS:
                logging.warning("当前环境未启用 MCP stdio 适配，跳过该绑定: %s", _normalize_text(binding.get("name")))
                continue

            if transport not in SUPPORTED_HTTP_TRANSPORTS:
                logging.warning("不支持的 MCP transport，已跳过: %s", transport)
                continue

            try:
                tool_definitions = self._list_remote_tools(binding)
            except Exception as exc:
                logging.exception("读取 MCP 工具列表失败，已跳过该绑定: %s", exc)
                continue

            allow_tool_names = {
                _normalize_text(tool_name)
                for tool_name in (binding.get("tool_names") or [])
                if _normalize_text(tool_name)
            }

            for tool_definition in tool_definitions:
                tool_name = _normalize_text(tool_definition.get("name"))
                if not tool_name:
                    continue
                if allow_tool_names and tool_name not in allow_tool_names:
                    continue

                try:
                    tools.append(self._build_langchain_tool(binding, tool_definition))
                except Exception as exc:
                    logging.exception("构建 MCP 工具失败，已跳过: %s", exc)

        return tools

    def _get_tools_from_snapshots(
        self,
        mcp_bindings: list[dict[str, Any]] | None,
        mcp_tool_snapshots: list[dict[str, Any]] | None,
    ) -> list[BaseTool]:
        tools: list[BaseTool] = []
        if not isinstance(mcp_bindings, list) or not isinstance(mcp_tool_snapshots, list):
            return tools

        snapshot_map = {
            self._normalize_snapshot_identity(snapshot): snapshot
            for snapshot in mcp_tool_snapshots
            if isinstance(snapshot, dict)
        }

        for binding in mcp_bindings:
            if not isinstance(binding, dict):
                continue
            if not self._is_binding_enabled(binding):
                continue

            transport = self._normalize_transport(binding.get("transport"))
            if transport in SUPPORTED_STDIO_TRANSPORTS or transport not in SUPPORTED_HTTP_TRANSPORTS:
                continue

            snapshot = snapshot_map.get(self.build_binding_identity(binding))
            if not isinstance(snapshot, dict):
                continue

            tool_definitions = snapshot.get("tool_definitions")
            if not isinstance(tool_definitions, list) or not tool_definitions:
                continue

            allow_tool_names = {
                _normalize_text(tool_name)
                for tool_name in (binding.get("tool_names") or [])
                if _normalize_text(tool_name)
            }
            for tool_definition in tool_definitions:
                if not isinstance(tool_definition, dict):
                    continue
                tool_name = _normalize_text(tool_definition.get("name"))
                if not tool_name:
                    continue
                if allow_tool_names and tool_name not in allow_tool_names:
                    continue

                try:
                    tools.append(self._build_langchain_tool(binding, tool_definition))
                except Exception as exc:
                    logging.exception("构建 MCP 快照工具失败，已跳过: %s", exc)

        return tools

    def list_remote_tool_definitions(self, binding: dict[str, Any]) -> list[dict[str, Any]]:
        """读取远程 MCP 的工具定义，用于广场详情和绑定选择。"""
        if not isinstance(binding, dict):
            return []

        if not self._is_binding_enabled(binding):
            return []

        transport = self._normalize_transport(binding.get("transport"))
        if transport in SUPPORTED_STDIO_TRANSPORTS:
            logging.warning("当前环境未启用 MCP stdio 适配，跳过该绑定: %s", _normalize_text(binding.get("name")))
            return []
        if transport not in SUPPORTED_HTTP_TRANSPORTS:
            logging.warning("不支持的 MCP transport，已跳过: %s", transport)
            return []

        try:
            tool_definitions = self._list_remote_tools(binding)
        except Exception as exc:
            logging.exception("读取 MCP 工具列表失败，已跳过该绑定: %s", exc)
            return []

        allow_tool_names = {
            _normalize_text(tool_name)
            for tool_name in (binding.get("tool_names") or [])
            if _normalize_text(tool_name)
        }

        if allow_tool_names:
            tool_definitions = [
                tool_definition
                for tool_definition in tool_definitions
                if _normalize_text(tool_definition.get("name")) in allow_tool_names
            ]

        return tool_definitions

    def _is_binding_enabled(self, binding: dict[str, Any]) -> bool:
        if "enabled" in binding and not bool(binding.get("enabled")):
            return False
        name = bool(_normalize_text(binding.get("name")))
        transport = self._normalize_transport(binding.get("transport"))
        if transport in SUPPORTED_STDIO_TRANSPORTS:
            return name and bool(_normalize_text(binding.get("command")))
        return name and bool(_normalize_text(binding.get("url")))

    def _normalize_transport(self, transport: Any) -> str:
        normalized = _normalize_text(transport).lower()
        if normalized in {"streamable-http", "streamable_http"}:
            return "streamable_http"
        return normalized or "streamable_http"

    def _build_langchain_tool(self, binding: dict[str, Any], tool_definition: dict[str, Any]) -> BaseTool:
        """将单个 MCP 工具定义封装为 LangChain 工具。"""
        binding_name = _normalize_text(binding.get("name")) or "mcp"
        binding_label = _normalize_text(binding.get("label"))
        binding_description = _normalize_text(binding.get("description"))
        raw_tool_name = _normalize_text(tool_definition.get("name"))
        tool_title = _normalize_text(tool_definition.get("title")) or raw_tool_name
        input_schema = tool_definition.get("inputSchema") or tool_definition.get("input_schema") or {}
        output_schema = tool_definition.get("outputSchema") or tool_definition.get("output_schema") or {}
        annotations = tool_definition.get("annotations") or {}
        raw_description = _normalize_text(tool_definition.get("description"))
        args_schema = self.schema_compiler.build_args_schema(input_schema, tool_name=raw_tool_name)
        namespaced_tool_name = f"mcp__{binding_name}__{raw_tool_name}"
        base_description = raw_description or binding_description or f"MCP 工具 {tool_title}"
        tool_description = self.schema_compiler.build_description(
            base_description=base_description,
            input_schema=input_schema,
            annotations=annotations,
        )
        if not tool_description:
            tool_description = base_description
        metadata = {
            "binding_name": binding_name,
            "binding_label": binding_label,
            "binding_description": binding_description,
            "source_key": _normalize_text(binding.get("source_key")),
            "source_type": _normalize_text(binding.get("source_type")),
            "tool_name": raw_tool_name,
            "tool_title": tool_title,
            "tool_description": raw_description,
            "input_schema": input_schema if isinstance(input_schema, dict) else {},
            "output_schema": output_schema if isinstance(output_schema, dict) else {},
            "annotations": annotations if isinstance(annotations, dict) else {},
            "schema_summary": self.schema_compiler.build_schema_summary(input_schema),
            "input_schema_summary": self.schema_compiler.build_schema_summary(input_schema),
            "output_schema_summary": self.schema_compiler.build_schema_summary(output_schema),
            "annotations_summary": self.schema_compiler.build_annotations_summary(annotations),
            "aliases": [
                binding_name,
                binding_label,
                binding_description,
                raw_tool_name,
                tool_title,
                raw_description,
            ],
        }
        tags = [
            tag
            for tag in (
                binding_name,
                binding_label,
                binding_description,
                raw_tool_name,
                tool_title,
                _normalize_text(binding.get("source_key")),
                _normalize_text(annotations.get("readOnlyHint")) if isinstance(annotations, dict) else "",
            )
            if tag
        ]

        def tool_func(**kwargs: Any) -> str:
            try:
                normalized_kwargs = _normalize_tool_arguments(kwargs)
                result = self._call_remote_tool(binding, raw_tool_name, normalized_kwargs)
            except Exception as exc:
                logging.exception("MCP 工具调用失败: %s", exc)
                return f"MCP 工具调用失败: {exc}"
            return result

        return StructuredTool.from_function(
            func=tool_func,
            name=namespaced_tool_name,
            description=tool_description,
            args_schema=args_schema,
            metadata=metadata,
            tags=tags,
        )

    def _list_remote_tools(self, binding: dict[str, Any]) -> list[dict[str, Any]]:
        payload = self._jsonrpc_request(binding, "tools/list", params={})
        if isinstance(payload, dict):
            tools = payload.get("tools")
            if isinstance(tools, list):
                return [tool for tool in tools if isinstance(tool, dict)]
        if isinstance(payload, list):
            return [tool for tool in payload if isinstance(tool, dict)]
        return []

    def _call_remote_tool(self, binding: dict[str, Any], tool_name: str, arguments: dict[str, Any]) -> str:
        payload = self._jsonrpc_request(
            binding,
            "tools/call",
            params={
                "name": tool_name,
                "arguments": arguments,
            },
        )
        if isinstance(payload, dict):
            if payload.get("isError") is True:
                return _extract_text_from_mcp_content(payload.get("content")) or json.dumps(payload, ensure_ascii=False)

            structured_content = payload.get("structuredContent")
            if structured_content is not None:
                text = _extract_text_from_mcp_content(structured_content)
                if text:
                    return text

            content = payload.get("content")
            text = _extract_text_from_mcp_content(content)
            if text:
                return text

            if payload:
                return json.dumps(payload, ensure_ascii=False)

        if isinstance(payload, list):
            text = _extract_text_from_mcp_content(payload)
            if text:
                return text
            return json.dumps(payload, ensure_ascii=False)

        if payload is None:
            return ""
        return str(payload)

    def _jsonrpc_request(
        self,
        binding: dict[str, Any],
        method: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        headers.update(_normalize_headers(binding.get("headers")))

        url = _normalize_text(binding.get("url"))
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": str(uuid4()),
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        response = safe_request(
            "POST",
            url,
            json=payload,
            headers=headers,
            timeout=int(binding.get("timeout_seconds") or self.timeout_seconds),
        )
        try:
            response.raise_for_status()
        except requests.HTTPError:
            raise RuntimeError(f"MCP 服务返回 HTTP {response.status_code}") from None

        decoded = _parse_json_payload(response.text, expected_id=payload["id"])
        if isinstance(decoded, dict):
            if "error" in decoded and decoded["error"]:
                error = decoded["error"]
                message = ""
                if isinstance(error, dict):
                    message = _normalize_text(error.get("message"))
                if not message:
                    message = "MCP 请求失败"
                raise RuntimeError(message)
            if "result" in decoded:
                return decoded["result"]
            return decoded
        return decoded
