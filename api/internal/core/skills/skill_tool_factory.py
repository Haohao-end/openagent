from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import monotonic
from typing import Annotated, Any, Literal
from uuid import uuid4

import regex
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    create_model,
    model_validator,
)

from .skill_executor import SkillSandboxExecutor, SkillScfClient

logger = logging.getLogger(__name__)
SKILL_PATTERN_TIMEOUT_SECONDS = 0.05
_PATTERN_VALIDATION_DEADLINE: ContextVar[float | None] = ContextVar("skill_pattern_validation_deadline", default=None)
_ECMASCRIPT_WHITESPACE = r"\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _reject_empty_enum(_value: Any) -> Any:
    raise ValueError("No values are allowed by an empty enum")


def _compile_json_schema_pattern(pattern: str) -> regex.Pattern[str]:
    translated: list[str] = []
    in_character_class = False
    class_first = False
    escaped = False
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if escaped:
            if char in "sS":
                whitespace = f"[{_ECMASCRIPT_WHITESPACE}]"
                if char == "S":
                    whitespace = f"[^{_ECMASCRIPT_WHITESPACE}]"
                translated.append(whitespace if not in_character_class else f"[{whitespace}]")
            elif char in "bB" and not in_character_class:
                translated.append(f"(?a:\\{char})")
            elif char == "b" and in_character_class:
                translated.append(r"\x08")
            else:
                translated.extend(("\\", char))
            escaped = False
            if in_character_class:
                class_first = False
        elif in_character_class and char in "&~|-" and pattern[index : index + 2] == char * 2:
            translated.extend((f"\\{char}", f"\\{char}"))
            class_first = False
            index += 1
        elif char == "\\":
            escaped = True
        elif char == "[" and not in_character_class:
            in_character_class = True
            class_first = True
            translated.append(char)
        elif char == "]" and in_character_class and not class_first:
            in_character_class = False
            translated.append(char)
        elif char == "." and not in_character_class:
            translated.append(r"[^\n\r\u2028\u2029]")
        elif char == "$" and not in_character_class:
            translated.append(r"\Z")
        else:
            translated.append(char)
            if in_character_class and not (class_first and char == "^"):
                class_first = False
        index += 1

    if escaped:
        translated.append("\\")
    return regex.compile("".join(translated), regex.ASCII | regex.VERSION1)


def _validate_string_pattern(value: Any, pattern: regex.Pattern[str]) -> str:
    if not isinstance(value, str):
        raise ValueError("Value does not match the pattern")  # noqa: TRY004
    deadline = _PATTERN_VALIDATION_DEADLINE.get() or monotonic() + SKILL_PATTERN_TIMEOUT_SECONDS
    timeout = deadline - monotonic()
    if timeout <= 0:
        raise ValueError("Pattern validation timed out")
    try:
        match = pattern.search(value, timeout=timeout)
    except TimeoutError as exc:
        raise ValueError("Pattern validation timed out") from exc
    if match is None:
        raise ValueError("Value does not match the pattern")
    return value


class _SkillToolArgsBase(BaseModel):
    @model_validator(mode="wrap")
    @classmethod
    def _bound_pattern_validation(cls, value: Any, handler: Any) -> Any:
        token = _PATTERN_VALIDATION_DEADLINE.set(monotonic() + SKILL_PATTERN_TIMEOUT_SECONDS)
        try:
            return handler(value)
        finally:
            _PATTERN_VALIDATION_DEADLINE.reset(token)


class _ClosedSkillToolArgsBase(_SkillToolArgsBase):
    model_config = ConfigDict(extra="forbid")


def _validate_enum(value: Any, enum_values: list[Any]) -> Any:
    if any(value == item and isinstance(value, bool) == isinstance(item, bool) for item in enum_values):
        return value
    raise ValueError("Value is not allowed by the enum")


def _numeric_constraints(schema: dict[str, Any]) -> dict[str, int | float]:
    return {
        name: value
        for name, value in (
            ("ge", schema.get("minimum")),
            ("le", schema.get("maximum")),
            ("gt", schema.get("exclusiveMinimum")),
            ("lt", schema.get("exclusiveMaximum")),
            ("multiple_of", schema.get("multipleOf")),
        )
        if type(value) in (int, float)
    }


def _json_schema_type_to_python(schema: dict[str, Any]) -> Any:
    schema_type = str(schema.get("type") or "string").strip().lower()
    enum_values = schema.get("enum")
    if isinstance(enum_values, list):
        if not enum_values:
            json_schema_extra = {"enum": []}
            if schema_type == "string" and isinstance(schema.get("pattern"), str):
                json_schema_extra["pattern"] = schema["pattern"]
            return Annotated[Any, Field(json_schema_extra=json_schema_extra), AfterValidator(_reject_empty_enum)]
        if schema_type in {"integer", "number"}:
            numeric_type = StrictInt if schema_type == "integer" else StrictFloat
            constraints = _numeric_constraints(schema)
            annotation = Annotated[
                numeric_type,
                Field(**constraints, json_schema_extra={"enum": enum_values}),
            ]
            return Annotated[annotation, AfterValidator(lambda value: _validate_enum(value, enum_values))]
        if schema_type == "string" and isinstance(schema.get("pattern"), str):
            pattern = schema["pattern"]
            compiled_pattern = _compile_json_schema_pattern(pattern)
            return Annotated[
                Literal[tuple(enum_values)],
                Field(json_schema_extra={"pattern": pattern}),
                AfterValidator(lambda value: _validate_string_pattern(value, compiled_pattern)),
            ]
        return Literal[tuple(enum_values)]
    if schema_type == "string":
        constraints = {
            name: value
            for name, value in (
                ("min_length", schema.get("minLength")),
                ("max_length", schema.get("maxLength")),
            )
            if type(value) is int and value >= 0
        }
        pattern = schema.get("pattern")
        if isinstance(pattern, str):
            compiled_pattern = _compile_json_schema_pattern(pattern)
            return Annotated[
                str,
                Field(**constraints, json_schema_extra={"pattern": pattern}),
                AfterValidator(lambda value: _validate_string_pattern(value, compiled_pattern)),
            ]
        return Annotated[str, Field(**constraints)] if constraints else str
    if schema_type in {"integer", "number"}:
        numeric_type = StrictInt if schema_type == "integer" else StrictFloat
        constraints = _numeric_constraints(schema)
        return Annotated[numeric_type, Field(**constraints)] if constraints else numeric_type
    if schema_type == "boolean":
        return StrictBool
    if schema_type == "array":
        items = schema.get("items")
        if items is False:
            return Annotated[list[Any], Field(max_length=0)]
        item_type = _json_schema_type_to_python(items) if isinstance(items, dict) else Any
        constraints = {
            name: value
            for name, value in (("min_length", schema.get("minItems")), ("max_length", schema.get("maxItems")))
            if type(value) is int and value >= 0
        }
        array_type = list[item_type]
        return Annotated[array_type, Field(**constraints)] if constraints else array_type
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
                        python_type,
                        Field(default=None, description=description),
                    )
                else:
                    fields[prop_name] = (
                        python_type,
                        Field(default=... if prop_name in required_fields else default, description=description),
                    )

        model_base = (
            _ClosedSkillToolArgsBase
            if input_schema.get("additionalProperties") is False
            else _SkillToolArgsBase
        )
        if not fields:
            return create_model(f"SkillToolArgs_{uuid4().hex}", __base__=model_base)

        return create_model(f"SkillToolArgs_{uuid4().hex}", __base__=model_base, **fields)
