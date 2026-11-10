from __future__ import annotations

import logging

import pytest
from internal.core.skills.skill_tool_factory import SkillToolFactory
from internal.exception import FailException
from pydantic import ValidationError


def test_skill_tool_factory_should_fallback_to_sandbox_when_scf_fails():
    scf_calls = []
    sandbox_calls = []

    class _ScfClient:
        def execute_skill(self, payload):
            scf_calls.append(payload)
            raise FailException("SCF failed")

    class _SandboxExecutor:
        def execute_skill(self, payload):
            sandbox_calls.append(payload)
            return {"status": "sandbox", "echo": payload["input"]}

    factory = SkillToolFactory(scf_client=_ScfClient(), sandbox_executor=_SandboxExecutor())
    tools = factory.build_tools(
        package_payload={
            "skill_id": "skill-1",
            "source_key": "demo_skill",
            "name": "演示技能",
            "label": "演示技能",
            "executor_type": "scf",
            "bundle": {"skill.py": "def demo(params):\n    return params\n"},
        },
        tool_definitions=[
            {
                "name": "demo",
                "label": "演示",
                "description": "演示工具",
                "entrypoint": "demo",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                        }
                    },
                    "required": ["query"],
                },
            }
        ],
        runtime_context={"app_id": "app-1"},
    )

    result = tools[0].invoke({"query": "hello"})

    assert scf_calls and sandbox_calls
    assert scf_calls[0]["tool_name"] == "demo"
    assert sandbox_calls[0]["bundle"]["skill.py"].startswith("def demo")
    assert sandbox_calls[0]["runtime_context"]["app_id"] == "app-1"
    assert "sandbox" in result


def test_skill_tool_factory_should_redact_scf_and_sandbox_errors(caplog):
    secret = "SYNTHETIC_SKILL_PROVIDER_SECRET"

    class _FailingExecutor:
        def execute_skill(self, _payload):
            raise RuntimeError(secret)

    executor = _FailingExecutor()
    factory = SkillToolFactory(executor, executor)
    tools = factory.build_tools(
        package_payload={
            "skill_id": "skill-1",
            "source_key": "demo_skill",
            "name": "演示技能",
            "label": "演示技能",
            "executor_type": "scf",
        },
        tool_definitions=[{"name": "demo", "input_schema": {"type": "object", "properties": {}}}],
    )

    with caplog.at_level(logging.WARNING, logger="internal.core.skills.skill_tool_factory"):
        result = tools[0].invoke({})

    assert secret not in caplog.text + result
    assert result == "技能执行失败" and "type=RuntimeError" in caplog.text


def test_skill_tool_factory_should_skip_prompt_only_packages():
    factory = SkillToolFactory(
        scf_client=type("_ScfClient", (), {"execute_skill": lambda self, payload: payload})(),
    )

    tools = factory.build_tools(
        package_payload={
            "skill_id": "skill-1",
            "source_key": "demo_skill",
            "name": "演示技能",
            "label": "演示技能",
            "executor_type": "prompt",
            "bundle": {"skill.py": "def demo(params):\n    return params\n"},
        },
        tool_definitions=[
            {
                "name": "demo",
                "label": "演示",
                "description": "演示工具",
                "entrypoint": "demo",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            }
        ],
        runtime_context={"app_id": "app-1"},
    )

    assert tools == []


def test_skill_tool_factory_should_not_require_version_in_package_payload():
    scf_calls = []

    class _ScfClient:
        def execute_skill(self, payload):
            scf_calls.append(payload)
            return {"status": "ok"}

    factory = SkillToolFactory(scf_client=_ScfClient())
    tools = factory.build_tools(
        package_payload={
            "skill_id": "skill-1",
            "source_key": "demo_skill",
            "name": "演示技能",
            "label": "演示技能",
            "executor_type": "scf",
            "bundle": {"skill.py": "def demo(params):\n    return params\n"},
        },
        tool_definitions=[
            {
                "name": "demo",
                "label": "演示",
                "description": "演示工具",
                "entrypoint": "demo",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            }
        ],
        runtime_context={"app_id": "app-1"},
    )

    assert tools
    assert tools[0].invoke({})
    assert "version" not in scf_calls[0]


def test_skill_tool_factory_should_keep_required_fields_required_when_default_declared():
    schema = SkillToolFactory(scf_client=None)._build_args_schema(
        {
            "properties": {"query": {"type": "string", "default": "fallback"}},
            "required": ["query"],
        }
    )

    with pytest.raises(ValidationError):
        schema.model_validate({})


def test_skill_tool_factory_should_reject_null_for_optional_non_nullable_fields():
    schema = SkillToolFactory(scf_client=None)._build_args_schema(
        {"properties": {"value": {"type": "string"}}}
    )

    assert schema.model_validate({}).value is None
    with pytest.raises(ValidationError):
        schema.model_validate({"value": None})


def test_skill_tool_factory_should_reject_values_for_empty_enum():
    schema = SkillToolFactory(scf_client=None)._build_args_schema(
        {"properties": {"value": {"type": "string", "enum": []}}, "required": ["value"]}
    )

    with pytest.raises(ValidationError):
        schema.model_validate({"value": "any string"})
    assert schema.model_json_schema()["properties"]["value"]["enum"] == []


def test_skill_tool_factory_should_validate_array_item_types():
    schema = SkillToolFactory(scf_client=None)._build_args_schema(
        {"properties": {"values": {"type": "array", "items": {"type": "integer"}}}}
    )

    with pytest.raises(ValidationError):
        schema.model_validate({"values": ["not an integer"]})


def test_skill_tool_factory_should_reject_items_when_item_schema_is_false():
    schema = SkillToolFactory(scf_client=None)._build_args_schema(
        {"properties": {"values": {"type": "array", "items": False}}, "required": ["values"]}
    )

    assert schema.model_validate({"values": []}).values == []
    with pytest.raises(ValidationError):
        schema.model_validate({"values": [1]})


@pytest.mark.parametrize(
    ("schema_type", "is_array"),
    [("integer", False), ("number", False), ("integer", True), ("number", True)],
)
def test_skill_tool_factory_should_reject_booleans_for_numeric_schemas(schema_type, is_array):
    field = {"type": "array", "items": {"type": schema_type}} if is_array else {"type": schema_type}
    schema = SkillToolFactory(scf_client=None)._build_args_schema(
        {"properties": {"value": field}, "required": ["value"]}
    )

    with pytest.raises(ValidationError):
        schema.model_validate({"value": [True] if is_array else True})


@pytest.mark.parametrize(
    ("field", "valid_value", "invalid_value"),
    [
        ({"type": "string", "enum": ["safe", "fast"]}, "safe", "other"),
        ({"type": "array", "items": {"type": "string", "enum": ["safe", "fast"]}}, ["safe"], ["other"]),
    ],
)
def test_skill_tool_factory_should_validate_enum_values(field, valid_value, invalid_value):
    schema = SkillToolFactory(scf_client=None)._build_args_schema(
        {"properties": {"mode": field}, "required": ["mode"]}
    )
    assert schema.model_validate({"mode": valid_value}).mode == valid_value

    with pytest.raises(ValidationError):
        schema.model_validate({"mode": invalid_value})


def test_skill_tool_factory_should_reject_additional_properties_when_disabled():
    schema = SkillToolFactory(scf_client=None)._build_args_schema(
        {"properties": {"query": {"type": "string"}}, "additionalProperties": False}
    )

    with pytest.raises(ValidationError):
        schema.model_validate({"query": "hello", "unexpected": "value"})


def test_skill_tool_factory_should_reject_additional_properties_for_empty_closed_schema():
    schema = SkillToolFactory(scf_client=None)._build_args_schema(
        {"properties": {}, "additionalProperties": False}
    )

    with pytest.raises(ValidationError):
        schema.model_validate({"unexpected": "value"})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ({"type": "boolean"}, "false"),
        ({"type": "boolean"}, 1),
        ({"type": "array", "items": {"type": "boolean"}}, ["false"]),
        ({"type": "array", "items": {"type": "boolean"}}, [1]),
    ],
)
def test_skill_tool_factory_should_reject_non_boolean_values(field, value):
    schema = SkillToolFactory(scf_client=None)._build_args_schema(
        {"properties": {"value": field}, "required": ["value"]}
    )

    with pytest.raises(ValidationError):
        schema.model_validate({"value": value})


@pytest.mark.parametrize(
    ("field", "valid_value", "invalid_value"),
    [
        ({"type": "string", "minLength": 3}, "abc", "ab"),
        ({"type": "string", "maxLength": 3}, "abc", "abcd"),
        ({"type": "array", "items": {"type": "string", "minLength": 3}}, ["abc"], ["ab"]),
        ({"type": "array", "items": {"type": "string", "maxLength": 3}}, ["abc"], ["abcd"]),
    ],
)
def test_skill_tool_factory_should_validate_string_length_constraints(field, valid_value, invalid_value):
    schema = SkillToolFactory(scf_client=None)._build_args_schema(
        {"properties": {"value": field}, "required": ["value"]}
    )
    assert schema.model_validate({"value": valid_value}).value == valid_value

    with pytest.raises(ValidationError):
        schema.model_validate({"value": invalid_value})


@pytest.mark.parametrize(
    ("field", "valid_value", "invalid_value"),
    [
        ({"type": "string", "pattern": "^[A-Z]{2}$"}, "AB", "a1"),
        ({"type": "array", "items": {"type": "string", "pattern": "^[A-Z]{2}$"}}, ["AB"], ["a1"]),
        ({"type": "string", "enum": ["AA", "bb"], "pattern": "^[A-Z]+$"}, "AA", "bb"),
        ({"type": "array", "items": {"type": "string", "enum": ["AA", "bb"], "pattern": "^[A-Z]+$"}}, ["AA"], ["bb"]),
        ({"type": "string", "pattern": "^(?=.{8,}$).*$"}, "OpenAgent", "short"),
        ({"type": "string", "pattern": r"^\d+$"}, "42", "١٢"),
        ({"type": "string", "pattern": r"^\w+$"}, "word_1", "café"),
        ({"type": "string", "pattern": r"\bcat\b"}, "écaté", "scatter"),
        ({"type": "string", "pattern": r"^.$"}, "x", "\u2028"),
        ({"type": "string", "pattern": "^x$"}, "x", "x\u2028"),
        ({"type": "string", "pattern": "^x$"}, "x", "x\n"),
        ({"type": "string", "pattern": "^x$"}, "x", "x\r\n"),
        ({"type": "string", "pattern": r"^[&&]+$"}, "&", "x"),
        ({"type": "string", "pattern": r"^\s+$"}, "\u00a0", "\u001c"),
        ({"type": "string", "pattern": r"^\S+$"}, "\u001c", "\u00a0"),
        ({"type": "string", "pattern": r"^[\S]+$"}, "word", "\u00a0"),
        ({"type": "string", "pattern": r"^[\s]+$"}, "\u00a0", "word"),
    ],
)
def test_skill_tool_factory_should_validate_string_patterns(field, valid_value, invalid_value):
    schema = SkillToolFactory(scf_client=None)._build_args_schema(
        {"properties": {"value": field}, "required": ["value"]}
    )
    assert schema.model_validate({"value": valid_value}).value == valid_value
    value_schema = schema.model_json_schema()["properties"]["value"]
    if field["type"] == "array":
        value_schema = value_schema["items"]
    assert value_schema["pattern"] == (field.get("items") or field)["pattern"]

    with pytest.raises(ValidationError):
        schema.model_validate({"value": invalid_value})


def test_skill_tool_factory_should_bound_string_pattern_validation_time():
    schema = SkillToolFactory(scf_client=None)._build_args_schema(
        {"properties": {"value": {"type": "string", "pattern": "(a+)+$"}}, "required": ["value"]}
    )

    with pytest.raises(ValidationError, match="Pattern validation timed out"):
        schema.model_validate({"value": "a" * 1000 + "!"})


def test_skill_tool_factory_should_share_pattern_timeout_across_array_items(monkeypatch):
    schema = SkillToolFactory(scf_client=None)._build_args_schema(
        {"properties": {"values": {"type": "array", "items": {"type": "string", "pattern": "^a$"}}}}
    )
    elapsed = iter((0.0, 0.01, 0.03, 0.06))
    monkeypatch.setattr("internal.core.skills.skill_tool_factory.monotonic", lambda: next(elapsed))

    with pytest.raises(ValidationError, match="Pattern validation timed out"):
        schema.model_validate({"values": ["a"] * 3})


@pytest.mark.parametrize(
    ("field", "valid_value", "invalid_value"),
    [
        ({"type": "integer", "minimum": 2}, 2, 1),
        ({"type": "integer", "maximum": 4}, 4, 5),
        ({"type": "number", "exclusiveMinimum": 1.5}, 2.0, 1.5),
        ({"type": "number", "exclusiveMaximum": 3.5}, 3.0, 3.5),
        ({"type": "integer", "multipleOf": 3}, 6, 7),
        ({"type": "integer", "enum": [1, 2], "minimum": 2}, 2, 1),
        ({"type": "integer", "enum": [1, "x"], "minimum": 0}, 1, "x"),
        ({"type": "integer", "enum": [True, 1], "minimum": 0}, 1, True),
        ({"type": "integer", "enum": [True, 2], "minimum": 0}, 2, 1),
    ],
)
def test_skill_tool_factory_should_validate_numeric_constraints(field, valid_value, invalid_value):
    schema = SkillToolFactory(scf_client=None)._build_args_schema(
        {"properties": {"value": field}, "required": ["value"]}
    )
    assert schema.model_validate({"value": valid_value}).value == valid_value
    if "enum" in field:
        generated = schema.model_json_schema()["properties"]["value"]
        assert (generated["type"], generated["enum"], generated["minimum"]) == (
            field["type"], field["enum"], field["minimum"]
        )

    with pytest.raises(ValidationError):
        schema.model_validate({"value": invalid_value})


@pytest.mark.parametrize(
    ("field", "valid_value", "invalid_value"),
    [
        ({"type": "array", "items": {"type": "integer"}, "minItems": 1}, [1], []),
        ({"type": "array", "items": {"type": "integer"}, "maxItems": 1}, [1], [1, 2]),
    ],
)
def test_skill_tool_factory_should_validate_array_length_constraints(field, valid_value, invalid_value):
    schema = SkillToolFactory(scf_client=None)._build_args_schema(
        {"properties": {"value": field}, "required": ["value"]}
    )
    assert schema.model_validate({"value": valid_value}).value == valid_value

    with pytest.raises(ValidationError):
        schema.model_validate({"value": invalid_value})
