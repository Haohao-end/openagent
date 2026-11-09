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
