from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, Literal, Union, get_args, get_origin
from uuid import uuid4

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    create_model,
)


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_schema(schema: Any) -> dict[str, Any]:
    return schema if isinstance(schema, dict) else {}


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


def _safe_identifier(value: str) -> str:
    normalized = _normalize_text(value)
    if not normalized:
        return "Schema"
    candidate = []
    for char in normalized:
        if char.isalnum() or char == "_":
            candidate.append(char)
        else:
            candidate.append("_")
    result = "".join(candidate).strip("_")
    if not result:
        result = "Schema"
    if result[0].isdigit():
        result = f"_{result}"
    return result


def _dedupe_types(types: list[Any]) -> list[Any]:
    deduped: list[Any] = []
    seen: set[str] = set()
    for value in types:
        marker = repr(value)
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(value)
    return deduped


def _flatten_union_types(types: list[Any]) -> list[Any]:
    flattened: list[Any] = []
    for schema_type in types:
        origin = get_origin(schema_type)
        if origin is Union:
            flattened.extend(get_args(schema_type))
        else:
            flattened.append(schema_type)
    return _dedupe_types(flattened)


def _build_literal_type(values: list[Any]) -> Any:
    normalized_values = _dedupe_types(values)
    if not normalized_values:
        return Annotated[Any, Field(json_schema_extra={"enum": []}), AfterValidator(_reject_empty_enum)]
    if len(normalized_values) == 1:
        return Literal[normalized_values[0]]
    return Literal[tuple(normalized_values)]


def _reject_empty_enum(_value: Any) -> Any:
    raise ValueError("No values are allowed by an empty enum")


def _validate_enum(value: Any, enum_values: list[Any]) -> Any:
    if any(value == item and isinstance(value, bool) == isinstance(item, bool) for item in enum_values):
        return value
    raise ValueError(f"Value must be one of {enum_values}")


@dataclass(slots=True)
class McpSchemaCompiler:
    """把 MCP tools/list 返回的 JSON Schema 编译成更适合模型消费的结构。"""

    model_prefix: str = "McpToolArgs"
    summary_depth_limit: int = 2
    summary_field_limit: int = 6

    def build_args_schema(self, input_schema: Any, *, tool_name: str = "") -> type[BaseModel]:
        """将 MCP inputSchema 编译成 Pydantic args_schema。"""
        normalized_schema = _normalize_schema(input_schema)
        compiled = self._compile_schema(
            normalized_schema,
            model_name_hint=_safe_identifier(tool_name or self.model_prefix),
            depth=0,
        )

        if isinstance(compiled, type) and issubclass(compiled, BaseModel):
            return compiled

        model_name = f"{self.model_prefix}_{uuid4().hex}"
        field_description = self.build_schema_summary(normalized_schema)
        field_annotation = compiled if compiled is not Any else Any
        return create_model(
            model_name,
            value=(
                field_annotation,
                Field(
                    default=...,
                    description=field_description,
                ),
            ),
            __config__=ConfigDict(extra="allow"),
        )

    def build_schema_summary(self, schema: Any) -> str:
        """把 schema 压缩成短说明，供工具 description / metadata 使用。"""
        normalized_schema = _normalize_schema(schema)
        if not normalized_schema:
            return ""

        description = _normalize_text(normalized_schema.get("description"))
        title = _normalize_text(normalized_schema.get("title"))
        parts: list[str] = []
        if title and title != description:
            parts.append(title)
        if description:
            parts.append(description)

        structured = self._describe_schema(normalized_schema, depth=0)
        if structured:
            parts.append(structured)
        return "；".join(part for part in parts if part)

    def build_annotations_summary(self, annotations: Any) -> str:
        if not isinstance(annotations, dict):
            return ""

        labels: list[str] = []
        if annotations.get("readOnlyHint") is True:
            labels.append("只读")
        if annotations.get("idempotentHint") is True:
            labels.append("幂等")
        if annotations.get("destructiveHint") is True:
            labels.append("可能有副作用")
        if annotations.get("openWorldHint") is True:
            labels.append("开放世界")
        return "，".join(labels)

    def build_description(
        self,
        *,
        base_description: str,
        input_schema: Any,
        annotations: Any = None,
    ) -> str:
        """把基础描述、schema 摘要和 annotations 摘要合并成适合模型消费的工具说明。"""
        parts = [_normalize_text(base_description)]
        annotations_summary = self.build_annotations_summary(annotations)
        if annotations_summary:
            parts.append(f"行为: {annotations_summary}")

        schema_summary = self.build_schema_summary(input_schema)
        if schema_summary:
            parts.append(f"输入: {schema_summary}")

        return "\n".join(part for part in parts if part)

    def _compile_schema(self, schema: dict[str, Any], *, model_name_hint: str, depth: int) -> Any:
        schema = _normalize_schema(schema)
        if not schema:
            return self._build_object_model(schema, model_name_hint, depth)

        has_const = "const" in schema
        enum_values = [schema["const"]] if has_const else schema.get("enum")
        normalized_type = _normalize_text(schema.get("type")).lower()
        if isinstance(enum_values, list):
            if normalized_type in {"integer", "number"}:
                numeric_type = StrictInt if normalized_type == "integer" else StrictInt | StrictFloat
                json_schema_extra = {"const": enum_values[0]} if has_const else {"enum": enum_values}
                return Annotated[
                    numeric_type,
                    Field(**_numeric_constraints(schema), json_schema_extra=json_schema_extra),
                    AfterValidator(lambda value: _validate_enum(value, enum_values)),
                ]
            return _build_literal_type(enum_values)

        schema_type = schema.get("type")
        if isinstance(schema_type, list):
            compiled_types = []
            include_null = False
            for value in schema_type:
                normalized_value = _normalize_text(value).lower()
                if normalized_value == "null":
                    include_null = True
                    continue
                sub_schema = dict(schema)
                sub_schema["type"] = normalized_value
                compiled_types.append(self._compile_schema(sub_schema, model_name_hint=model_name_hint, depth=depth))
            if include_null:
                compiled_types.append(type(None))
            return self._build_union_type(compiled_types)

        if "oneOf" in schema:
            compiled_types = [
                self._compile_schema(sub_schema, model_name_hint=f"{model_name_hint}OneOf", depth=depth + 1)
                for sub_schema in schema.get("oneOf") or []
                if isinstance(sub_schema, dict)
            ]
            return self._build_union_type(compiled_types)

        if "anyOf" in schema:
            compiled_types = [
                self._compile_schema(sub_schema, model_name_hint=f"{model_name_hint}AnyOf", depth=depth + 1)
                for sub_schema in schema.get("anyOf") or []
                if isinstance(sub_schema, dict)
            ]
            return self._build_union_type(compiled_types)

        if "allOf" in schema:
            merged_schema = self._merge_all_of_schema(schema.get("allOf") or [])
            if merged_schema is not None:
                return self._compile_schema(merged_schema, model_name_hint=model_name_hint, depth=depth)
            compiled_types = [
                self._compile_schema(sub_schema, model_name_hint=f"{model_name_hint}AllOf", depth=depth + 1)
                for sub_schema in schema.get("allOf") or []
                if isinstance(sub_schema, dict)
            ]
            return self._build_union_type(compiled_types)

        if self._is_object_like(schema):
            return self._build_object_model(schema, model_name_hint, depth)

        if _normalize_text(schema_type).lower() == "array":
            if schema.get("items") is False:
                return Annotated[list[Any], Field(max_length=0)]
            if "items" not in schema or schema["items"] is True or schema["items"] == {}:
                return list[Any]
            item_schema = schema.get("items") or {}
            item_type = self._compile_schema(
                _normalize_schema(item_schema),
                model_name_hint=f"{model_name_hint}Item",
                depth=depth + 1,
            )
            return list[item_type if item_type is not Any else Any]

        if _normalize_text(schema_type).lower() == "string":
            return str
        if _normalize_text(schema_type).lower() in {"integer", "number"}:
            numeric_type = StrictInt if _normalize_text(schema_type).lower() == "integer" else StrictFloat
            constraints = _numeric_constraints(schema)
            return Annotated[numeric_type, Field(**constraints)] if constraints else numeric_type
        if _normalize_text(schema_type).lower() == "boolean":
            return StrictBool
        if _normalize_text(schema_type).lower() == "null":
            return type(None)
        if _normalize_text(schema_type).lower() == "object":
            return self._build_object_model(schema, model_name_hint, depth)

        return Any

    def _build_object_model(self, schema: dict[str, Any], model_name_hint: str, depth: int) -> type[BaseModel]:
        properties = schema.get("properties") or {}
        required_fields = {str(field_name) for field_name in (schema.get("required") or []) if _normalize_text(field_name)}
        additional_properties = schema.get("additionalProperties", True)
        allow_extra = additional_properties is not False

        fields: dict[str, tuple[Any, Any]] = {}
        if isinstance(properties, dict):
            for index, (prop_name, prop_schema) in enumerate(properties.items()):
                if index >= 100:
                    break
                prop_name = _normalize_text(prop_name)
                if not prop_name:
                    continue
                prop_schema = _normalize_schema(prop_schema)
                annotation = self._compile_schema(
                    prop_schema,
                    model_name_hint=f"{model_name_hint}_{_safe_identifier(prop_name)}",
                    depth=depth + 1,
                )

                is_required = prop_name in required_fields
                default_value = ... if is_required else prop_schema.get("default", ...)
                if not is_required and default_value is ...:
                    default_value = None

                fields[prop_name] = (
                    annotation,
                    Field(
                        default=default_value,
                        description=self._describe_schema(prop_schema, depth=depth + 1),
                        **self._build_field_constraints(prop_schema),
                    ),
                )

        model_name = f"{model_name_hint}_{uuid4().hex}"
        model_config = ConfigDict(extra="allow" if allow_extra else "forbid")
        if isinstance(additional_properties, dict):
            extra_type = (
                self._compile_schema(additional_properties, model_name_hint=f"{model_name_hint}Extra", depth=depth + 1)
                if additional_properties
                else Any
            )
            model_base = type(
                f"{model_name}Base",
                (BaseModel,),
                {
                    "__annotations__": {"__pydantic_extra__": dict[str, extra_type]},
                    "__pydantic_extra__": Field(init=False),
                    "model_config": ConfigDict(extra="allow"),
                },
            )
            return create_model(model_name, __base__=model_base, **fields)
        if not fields:
            return create_model(model_name, __config__=model_config)
        return create_model(model_name, __config__=model_config, **fields)

    def _build_field_constraints(self, schema: dict[str, Any]) -> dict[str, Any]:
        constraints: dict[str, Any] = {}
        schema_type = _normalize_text(schema.get("type")).lower()

        if schema_type == "string":
            if "minLength" in schema:
                constraints["min_length"] = schema["minLength"]
            if "maxLength" in schema:
                constraints["max_length"] = schema["maxLength"]
            if "pattern" in schema:
                constraints["pattern"] = schema["pattern"]
        elif schema_type == "array":
            if "minItems" in schema:
                constraints["min_length"] = schema["minItems"]
            if "maxItems" in schema:
                constraints["max_length"] = schema["maxItems"]

        return constraints

    def _build_union_type(self, types: list[Any]) -> Any:
        flattened = _flatten_union_types([value for value in types if value is not None])
        flattened = [value for value in flattened if value is not Any]
        if not flattened:
            return Any
        if len(flattened) == 1:
            return flattened[0]
        return Union[tuple(flattened)]

    def _merge_all_of_schema(self, schemas: list[Any]) -> dict[str, Any] | None:
        merged_properties: dict[str, Any] = {}
        merged_required: set[str] = set()
        descriptions: list[str] = []
        titles: list[str] = []
        additional_properties: Any = True

        for schema in schemas:
            if not isinstance(schema, dict):
                return None

            schema_type = _normalize_text(schema.get("type")).lower()
            if schema_type and schema_type != "object" and not schema.get("properties"):
                return None

            properties = schema.get("properties") or {}
            if isinstance(properties, dict):
                merged_properties.update(properties)

            required = schema.get("required") or []
            if isinstance(required, list):
                merged_required.update(
                    _normalize_text(field_name)
                    for field_name in required
                    if _normalize_text(field_name)
                )

            description = _normalize_text(schema.get("description"))
            if description:
                descriptions.append(description)

            title = _normalize_text(schema.get("title"))
            if title:
                titles.append(title)

            current_additional = schema.get("additionalProperties", True)
            if current_additional is False:
                additional_properties = False
            elif additional_properties is not False:
                additional_properties = current_additional

        merged_schema: dict[str, Any] = {
            "type": "object",
            "properties": merged_properties,
        }
        if merged_required:
            merged_schema["required"] = sorted(merged_required)
        if descriptions:
            merged_schema["description"] = "；".join(dict.fromkeys(descriptions))
        if titles:
            merged_schema["title"] = " / ".join(dict.fromkeys(titles))
        if additional_properties is not True:
            merged_schema["additionalProperties"] = additional_properties
        return merged_schema

    def _describe_schema(self, schema: dict[str, Any], depth: int) -> str:
        schema = _normalize_schema(schema)
        if not schema:
            return ""

        if depth > self.summary_depth_limit:
            return self._describe_compact_schema(schema)

        parts: list[str] = []
        title = _normalize_text(schema.get("title"))
        description = _normalize_text(schema.get("description"))
        if title and title != description:
            parts.append(title)
        if description:
            parts.append(description)

        schema_type = schema.get("type")
        if isinstance(schema_type, list):
            type_labels = [
                self._describe_schema({**schema, "type": item}, depth=depth + 1)
                for item in schema_type
            ]
            compact = " / ".join(part for part in type_labels if part)
            if compact:
                parts.append(compact)
            return "；".join(parts)

        if "oneOf" in schema:
            union_labels = [
                self._describe_schema(sub_schema, depth=depth + 1)
                for sub_schema in schema.get("oneOf") or []
                if isinstance(sub_schema, dict)
            ]
            compact = " 或 ".join(part for part in union_labels if part)
            if compact:
                parts.append(compact)
            return "；".join(parts)

        if "anyOf" in schema:
            union_labels = [
                self._describe_schema(sub_schema, depth=depth + 1)
                for sub_schema in schema.get("anyOf") or []
                if isinstance(sub_schema, dict)
            ]
            compact = " 或 ".join(part for part in union_labels if part)
            if compact:
                parts.append(compact)
            return "；".join(parts)

        if "allOf" in schema:
            merged_schema = self._merge_all_of_schema(schema.get("allOf") or [])
            if merged_schema is not None:
                merged_desc = self._describe_schema(merged_schema, depth=depth + 1)
                if merged_desc:
                    parts.append(merged_desc)
                    return "；".join(parts)
            merged_labels = [
                self._describe_schema(sub_schema, depth=depth + 1)
                for sub_schema in schema.get("allOf") or []
                if isinstance(sub_schema, dict)
            ]
            compact = " 且 ".join(part for part in merged_labels if part)
            if compact:
                parts.append(compact)
            return "；".join(parts)

        if self._is_object_like(schema) or _normalize_text(schema_type).lower() == "object":
            object_label = self._describe_object_schema(schema, depth=depth)
            if object_label:
                parts.append(object_label)
            return "；".join(parts)

        if _normalize_text(schema_type).lower() == "array":
            item_schema = _normalize_schema(schema.get("items") or {})
            item_label = self._describe_schema(item_schema, depth=depth + 1)
            array_label = f"数组<{item_label or '任意'}>"
            if schema.get("minItems") is not None or schema.get("maxItems") is not None:
                bounds: list[str] = []
                if schema.get("minItems") is not None:
                    bounds.append(f"最少 {schema['minItems']} 项")
                if schema.get("maxItems") is not None:
                    bounds.append(f"最多 {schema['maxItems']} 项")
                if bounds:
                    array_label += f"（{'，'.join(bounds)}）"
            parts.append(array_label)
            return "；".join(parts)

        scalar_label = self._describe_scalar_schema(schema)
        if scalar_label:
            parts.append(scalar_label)
        return "；".join(parts)

    def _describe_object_schema(self, schema: dict[str, Any], depth: int) -> str:
        properties = schema.get("properties") or {}
        required_fields = {str(field_name) for field_name in (schema.get("required") or []) if _normalize_text(field_name)}
        property_labels: list[str] = []
        if isinstance(properties, dict):
            for index, (prop_name, prop_schema) in enumerate(properties.items()):
                if index >= self.summary_field_limit:
                    break
                prop_name = _normalize_text(prop_name)
                if not prop_name:
                    continue
                prop_schema = _normalize_schema(prop_schema)
                label = self._describe_property(prop_name, prop_schema, depth=depth + 1)
                if prop_name in required_fields and "必填" not in label:
                    label = f"{label}（必填）"
                property_labels.append(label)

        if not property_labels:
            label = "对象参数"
        else:
            label = "对象参数: " + ", ".join(property_labels)

        additional_properties = schema.get("additionalProperties", True)
        if additional_properties is False:
            label += "；不允许额外字段"
        elif additional_properties is True:
            label += "；允许额外字段"
        elif isinstance(additional_properties, dict):
            extra_label = self._describe_schema(_normalize_schema(additional_properties), depth=depth + 1)
            if extra_label:
                label += f"；额外字段类型: {extra_label}"
            else:
                label += "；允许额外字段"

        return label

    def _describe_property(self, prop_name: str, prop_schema: dict[str, Any], depth: int) -> str:
        type_label = self._describe_type_label(prop_schema, depth=depth)
        label = f"{prop_name}:{type_label}" if type_label else prop_name
        parts: list[str] = [label]

        description = _normalize_text(prop_schema.get("description"))
        if description:
            parts.append(description)

        if "default" in prop_schema:
            parts.append(f"默认 {prop_schema['default']}")

        if len(parts) == 1:
            return label
        return f"{label}（{'；'.join(parts[1:])}）"

    def _describe_scalar_schema(self, schema: dict[str, Any]) -> str:
        type_label = self._describe_type_label(schema, depth=0)
        if not type_label:
            return ""

        parts: list[str] = [type_label]
        if "default" in schema:
            parts.append(f"默认 {schema['default']}")
        if len(parts) == 1:
            return type_label
        return f"{type_label}（{'；'.join(parts[1:])}）"

    def _describe_type_label(self, schema: dict[str, Any], depth: int) -> str:
        schema_type = schema.get("type")
        if isinstance(schema_type, list):
            labels = [
                self._describe_type_label({**schema, "type": item}, depth=depth + 1)
                for item in schema_type
            ]
            return " / ".join(part for part in labels if part)

        normalized_type = _normalize_text(schema_type).lower()
        if "oneOf" in schema:
            labels = [
                self._describe_schema(sub_schema, depth=depth + 1)
                for sub_schema in schema.get("oneOf") or []
                if isinstance(sub_schema, dict)
            ]
            return " 或 ".join(part for part in labels if part)
        if "anyOf" in schema:
            labels = [
                self._describe_schema(sub_schema, depth=depth + 1)
                for sub_schema in schema.get("anyOf") or []
                if isinstance(sub_schema, dict)
            ]
            return " 或 ".join(part for part in labels if part)
        if "allOf" in schema:
            merged_schema = self._merge_all_of_schema(schema.get("allOf") or [])
            if merged_schema is not None:
                return self._describe_schema(merged_schema, depth=depth + 1)
            labels = [
                self._describe_schema(sub_schema, depth=depth + 1)
                for sub_schema in schema.get("allOf") or []
                if isinstance(sub_schema, dict)
            ]
            return " 且 ".join(part for part in labels if part)
        if normalized_type == "string":
            label = "string"
            if schema.get("format"):
                label += f"[format={_normalize_text(schema.get('format'))}]"
            if schema.get("pattern"):
                label += f"[pattern={_normalize_text(schema.get('pattern'))}]"
            if schema.get("enum"):
                enum_values = schema.get("enum") or []
                label += f"[enum={', '.join(map(str, enum_values[:5]))}]"
            return label
        if normalized_type == "integer":
            return "integer"
        if normalized_type == "number":
            return "number"
        if normalized_type == "boolean":
            return "boolean"
        if normalized_type == "null":
            return "null"
        if normalized_type == "array":
            item_schema = _normalize_schema(schema.get("items") or {})
            item_label = self._describe_schema(item_schema, depth=depth + 1)
            return f"array<{item_label or 'any'}>"
        if normalized_type == "object" or self._is_object_like(schema):
            return self._describe_object_schema(schema, depth=depth)
        if "enum" in schema:
            enum_values = schema.get("enum") or []
            if isinstance(enum_values, list) and enum_values:
                return f"enum[{', '.join(map(str, enum_values[:5]))}]"
        if "const" in schema:
            return f"const[{schema.get('const')}]"
        return ""

    def _describe_compact_schema(self, schema: dict[str, Any]) -> str:
        schema_type = _normalize_text(schema.get("type")).lower()
        if schema_type:
            if schema_type == "array":
                return "数组"
            if schema_type == "object":
                return "对象"
            return schema_type
        if schema.get("enum"):
            return "枚举"
        if schema.get("const") is not None:
            return "常量"
        return ""

    @staticmethod
    def _is_object_like(schema: dict[str, Any]) -> bool:
        if not isinstance(schema, dict):
            return False
        schema_type = _normalize_text(schema.get("type")).lower()
        return schema_type == "object" or "properties" in schema or "additionalProperties" in schema or not schema
