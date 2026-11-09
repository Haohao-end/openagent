from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import Field, create_model

from .skill_executor import SkillSandboxExecutor, SkillScfClient

logger = logging.getLogger(__name__)


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _json_schema_type_to_python(schema: dict[str, Any]) -> Any:
    schema_type = str(schema.get("type") or "string").strip().lower()
    if schema_type == "string":
        return str
    if schema_type == "integer":
        return int
    if schema_type == "number":
        return float
    if schema_type == "boolean":
        return bool
    if schema_type == "array":
        items = schema.get("items")
        return list[_json_schema_type_to_python(items)] if isinstance(items, dict) else list[Any]
    if schema_type == "object":
        return dict[str, Any]
    return Any


@dataclass(slots=True)
class SkillToolFactory:
    """将技能包工具定义展开为 LangChain 工具。"""

    scf_client: SkillScfClient
    sandbox_executor: SkillSandboxExecutor = field(default_factory=SkillSandboxExecutor)
    timeout_seconds: int = 60

    def build_tools(
        self,
        package_payload: dict[str, Any],
        tool_definitions: list[dict[str, Any]] | None,
        runtime_context: dict[str, Any] | None = None,
    ) -> list[BaseTool]:
        if _normalize_text(package_payload.get("executor_type")).lower() != "scf":
            return []
        if not isinstance(tool_definitions, list) or not tool_definitions:
            return []

        tools: list[BaseTool] = []
        for tool_definition in tool_definitions:
            if not isinstance(tool_definition, dict):
                continue

            tool_name = _normalize_text(tool_definition.get("name"))
            if not tool_name:
                continue

            try:
                tools.append(
                    self._build_single_tool(
                        package_payload=package_payload,
                        tool_definition=tool_definition,
                        runtime_context=runtime_context or {},
                    )
                )
            except Exception as exc:
                logger.exception("构建技能工具失败，已跳过: %s", exc)

        return tools

    def _build_single_tool(
        self,
        *,
        package_payload: dict[str, Any],
        tool_definition: dict[str, Any],
        runtime_context: dict[str, Any],
    ) -> BaseTool:
        tool_name = _normalize_text(tool_definition.get("name"))
        tool_label = _normalize_text(tool_definition.get("label") or tool_definition.get("title") or tool_name)
        tool_description = _normalize_text(tool_definition.get("description"))
        entrypoint = _normalize_text(tool_definition.get("entrypoint") or tool_name) or tool_name
        input_schema = tool_definition.get("input_schema") or tool_definition.get("inputSchema") or {}
        if not isinstance(input_schema, dict):
            input_schema = {}

        args_schema = self._build_args_schema(input_schema)
        namespaced_tool_name = f"skill__{package_payload['source_key']}__{tool_name}"
        description = tool_description or f"{package_payload['label']} · {tool_label}"

        def tool_func(**kwargs: Any) -> str:
            execution_id = str(uuid4())
            execution_payload = {
                "execution_id": execution_id,
                "skill_id": package_payload["skill_id"],
                "source_key": package_payload["source_key"],
                "package_name": package_payload["name"],
                "package_label": package_payload["label"],
                "tool_name": tool_name,
                "entrypoint": entrypoint,
                "input": kwargs,
                "runtime_context": runtime_context,
                "tool_definition": {
                    "name": tool_name,
                    "label": tool_label,
                    "description": tool_description,
                    "entrypoint": entrypoint,
                },
                "bundle": package_payload.get("bundle") or {},
            }
            try:
                logger.info(
                    "技能工具开始执行: execution_id=%s skill_id=%s source_key=%s tool_name=%s entrypoint=%s",
                    execution_id,
                    package_payload["skill_id"],
                    package_payload["source_key"],
                    tool_name,
                    entrypoint,
                )
                result = self.scf_client.execute_skill(execution_payload)
            except Exception as exc:
                logger.warning("技能工具 SCF 失败: id=%s type=%s", execution_id, type(exc).__name__)
                try:
                    result = self.sandbox_executor.execute_skill(execution_payload)
                except Exception as fallback_exc:
                    logger.error("技能工具沙箱回退失败: id=%s type=%s", execution_id, type(fallback_exc).__name__)
                    return "技能执行失败"

            if isinstance(result, (dict, list)):
                return json.dumps(result, ensure_ascii=False, default=str)
            return str(result)

        return StructuredTool.from_function(
            func=tool_func,
            name=namespaced_tool_name,
            description=description,
            args_schema=args_schema,
        )

    def _build_args_schema(self, input_schema: dict[str, Any]) -> type:
        properties = input_schema.get("properties") or {}
        required_fields = set(input_schema.get("required") or [])
        fields: dict[str, tuple[Any, Field]] = {}

        if isinstance(properties, dict):
            for prop_name, prop_schema in properties.items():
                if not isinstance(prop_schema, dict):
                    prop_schema = {}
                python_type = _json_schema_type_to_python(prop_schema)
                description = _normalize_text(prop_schema.get("description"))
                default = prop_schema.get("default", ...)
                if prop_name not in required_fields and default is ...:
                    fields[prop_name] = (
                        python_type | None,
                        Field(default=None, description=description),
                    )
                else:
                    fields[prop_name] = (
                        python_type,
                        Field(default=... if prop_name in required_fields else default, description=description),
                    )

        if not fields:
            return create_model(f"SkillToolArgs_{uuid4().hex}")

        return create_model(f"SkillToolArgs_{uuid4().hex}", **fields)
