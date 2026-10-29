"""DeepThinkingAgent 和 BaiduCfcSandboxBackend 的完整测试套件。

测试分层：
    Unit Tests  — 不需要网络，Mock 所有外部依赖
    Integration — 需要真实的百度 CFC 沙箱（标记 @pytest.mark.integration）

运行方式：
    # 只跑单元测试（快，无网络）
    pytest test/internal/core/agent/test_deep_thinking_agent.py -v -k "not integration"

    # 跑集成测试（需要 .env 中配置 E2B_API_KEY / E2B_DOMAIN）
    pytest test/internal/core/agent/test_deep_thinking_agent.py -v -m integration
"""
from __future__ import annotations

import os
import sys
import uuid
from contextlib import nullcontext
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch, PropertyMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool

from internal.core.agent.agents.deep_thinking_agent import (
    DeepRouteDecision,
    DeepThinkingAgent,
    StructuredDocumentOutlinePlan,
    StructuredDocumentSectionPlan,
)
from internal.core.agent.agents.a2a_deep_thinking_agent import A2ADeepThinkingAgent
from internal.core.agent.backends.baidu_cfc_sandbox_backend import BaiduCfcSandboxBackend
from internal.core.agent.entities.artifact_policy_entity import ArtifactPolicy
from internal.core.agent.entities.agent_entity import AgentConfig, DEEP_THINKING_SYSTEM_PROMPT
from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.core.agent.middleware import DeepTimelineMiddleware
from internal.core.language_model.entities.model_entity import BaseLanguageModel, ModelFeature
from internal.core.language_model.providers.openai.chat import Chat as OpenAIChat
from internal.entity.conversation_entity import InvokeFrom
from internal.service.language_model_service import RuntimeFallbackLanguageModelProxy


@pytest.fixture(autouse=True)
def _stub_deepagents_when_dependency_is_missing(monkeypatch):
    """本地单测不要求安装 deepagents；生产依赖由 requirements.txt 保证。"""
    try:
        __import__("deepagents")
        return
    except ModuleNotFoundError:
        pass

    class StateBackend:
        pass

    fake_deepagents = ModuleType("deepagents")
    fake_deepagents.create_deep_agent = MagicMock()
    fake_backends = ModuleType("deepagents.backends")
    fake_backends.StateBackend = StateBackend
    monkeypatch.setitem(sys.modules, "deepagents", fake_deepagents)
    monkeypatch.setitem(sys.modules, "deepagents.backends", fake_backends)


# ============================================================
#  通用 Mock 工具
# ============================================================

def _make_chunk(content="", tool_calls=None):
    """构造 Mock LLM chunk。"""
    chunk = MagicMock()
    chunk.content = content
    chunk.tool_calls = tool_calls or []
    chunk.__add__ = lambda self, other: _make_chunk(
        self.content + (other.content or ""), self.tool_calls or other.tool_calls
    )
    return chunk


def _make_llm(features=None, stream_chunks=None):
    """构造 Mock BaseLanguageModel。"""
    if features is None:
        features = [ModelFeature.TOOL_CALL.value]
    if stream_chunks is None:
        stream_chunks = [_make_chunk("这是深度思考后的答案")]

    llm = MagicMock(spec=BaseLanguageModel)
    llm.features = features
    llm.stream.return_value = iter(stream_chunks)
    llm.get_pricing.return_value = (0.001, 0.002, 1000.0)
    llm.convert_to_human_message.side_effect = lambda q, imgs=None: HumanMessage(content=q)
    return llm


def _make_agent_config(enable_deep_thinking=True, **kwargs):
    """构造 AgentConfig。"""
    return AgentConfig(
        user_id=uuid4(),
        invoke_from=InvokeFrom.DEBUGGER.value,
        preset_prompt="你是测试助手",
        enable_deep_thinking=enable_deep_thinking,
        **kwargs,
    )


# ============================================================
#  Unit Tests: BaiduCfcSandboxBackend
# ============================================================

class TestBaiduCfcSandboxBackend:
    """百度 CFC 沙箱后端单元测试（全部 Mock，无需网络）。"""

    def test_init_requires_api_key(self):
        """缺少 API Key 时应抛出 ValueError。"""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("E2B_API_KEY", None)
            os.environ.pop("E2B_DOMAIN", None)
            with pytest.raises(ValueError, match="E2B_API_KEY"):
                BaiduCfcSandboxBackend(domain="test.example.com")

    def test_init_requires_domain(self):
        """缺少 Domain 时应抛出 ValueError。"""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("E2B_DOMAIN", None)
            with pytest.raises(ValueError, match="E2B_DOMAIN"):
                BaiduCfcSandboxBackend(api_key="test-key")

    def test_init_reads_env_vars(self):
        """应从环境变量读取配置。"""
        with patch.dict(os.environ, {
            "E2B_API_KEY": "env-key-123",
            "E2B_DOMAIN":  "env-domain.example.com",
        }):
            backend = BaiduCfcSandboxBackend()
            assert backend._api_key == "env-key-123"
            assert backend._domain  == "env-domain.example.com"

    def test_init_reads_template_env_vars(self):
        """应从环境变量读取模板名和 fallback 模板名。"""
        with patch.dict(os.environ, {
            "E2B_API_KEY": "env-key-123",
            "E2B_DOMAIN":  "env-domain.example.com",
            "SANDBOX_TEMPLATE_ALIAS": "lite-template",
            "SANDBOX_FALLBACK_TEMPLATE_ALIAS": "fallback-template",
        }):
            backend = BaiduCfcSandboxBackend()
            assert backend._template_alias == "lite-template"
            assert backend._fallback_template_alias == "fallback-template"

    def test_id_property(self):
        """id 属性应返回非空字符串。"""
        backend = BaiduCfcSandboxBackend(api_key="k", domain="d")
        assert isinstance(backend.id, str)
        assert len(backend.id) > 0

    def test_execute_success(self):
        """execute() 成功时应返回正确的 ExecuteResponse。"""
        backend = BaiduCfcSandboxBackend(api_key="k", domain="d")

        # Mock e2b Sandbox
        mock_result = MagicMock()
        mock_result.stdout   = "hello world\n"
        mock_result.stderr   = ""
        mock_result.exit_code = 0

        mock_sbx = MagicMock()
        mock_sbx.commands.run.return_value = mock_result
        mock_sbx.sandbox_id = "test-sandbox-id"
        backend._sbx = mock_sbx

        result = backend.execute("echo hello world")

        assert result.exit_code == 0
        assert "hello world" in result.output
        assert result.truncated is False
        mock_sbx.commands.run.assert_called_once_with("echo hello world", timeout=600)

    def test_execute_with_stderr(self):
        """execute() 有 stderr 输出时应加 [stderr] 前缀。"""
        backend = BaiduCfcSandboxBackend(api_key="k", domain="d")

        mock_result = MagicMock()
        mock_result.stdout    = "ok\n"
        mock_result.stderr    = "warning: something\n"
        mock_result.exit_code = 0

        mock_sbx = MagicMock()
        mock_sbx.commands.run.return_value = mock_result
        backend._sbx = mock_sbx

        result = backend.execute("python3 script.py")

        assert "[stderr]" in result.output
        assert "warning: something" in result.output

    def test_execute_truncates_large_output(self):
        """超过 100000 字节的输出应被截断。"""
        backend = BaiduCfcSandboxBackend(api_key="k", domain="d")

        mock_result = MagicMock()
        mock_result.stdout    = "x" * 200_000   # 200KB 输出
        mock_result.stderr    = ""
        mock_result.exit_code = 0

        mock_sbx = MagicMock()
        mock_sbx.commands.run.return_value = mock_result
        backend._sbx = mock_sbx

        result = backend.execute("cat huge_file")

        assert result.truncated is True
        assert len(result.output) < 110_000  # 截断后不超过阈值 + 提示文字

    def test_execute_handles_exception(self):
        """execute() 遇到异常时应返回 exit_code=1 而非抛出。"""
        backend = BaiduCfcSandboxBackend(api_key="k", domain="d")

        mock_sbx = MagicMock()
        mock_sbx.commands.run.side_effect = RuntimeError("连接超时")
        backend._sbx = mock_sbx

        result = backend.execute("ls /")

        assert result.exit_code == 1
        assert "RuntimeError" in result.output or "连接超时" in result.output

    def test_execute_custom_timeout(self):
        """execute() 应使用自定义 timeout 参数。"""
        backend = BaiduCfcSandboxBackend(api_key="k", domain="d", timeout=30)

        mock_result = MagicMock()
        mock_result.stdout    = "ok"
        mock_result.stderr    = ""
        mock_result.exit_code = 0

        mock_sbx = MagicMock()
        mock_sbx.commands.run.return_value = mock_result
        backend._sbx = mock_sbx

        backend.execute("long_cmd", timeout=120)

        mock_sbx.commands.run.assert_called_once_with("long_cmd", timeout=120)

    def test_create_sandbox_uses_template_fallback(self):
        """当主模板创建失败时，应自动尝试 fallback 模板。"""
        backend = BaiduCfcSandboxBackend(
            api_key="k",
            domain="d",
            timeout=30,
            sandbox_timeout=90,
            template_alias="lite-template",
            fallback_template_alias="fallback-template",
        )

        mock_result = MagicMock()
        mock_result.stdout = "ok\n"
        mock_result.stderr = ""
        mock_result.exit_code = 0

        mock_sbx = MagicMock()
        create_mock = MagicMock(side_effect=[RuntimeError("template missing"), mock_sbx])
        fake_e2b_module = SimpleNamespace(
            Sandbox=SimpleNamespace(create=create_mock),
        )
        mock_sbx.commands.run.return_value = mock_result
        with patch.dict("sys.modules", {"e2b_code_interpreter": fake_e2b_module}):
            result = backend.execute("echo ok")

        assert result.exit_code == 0
        assert "ok" in result.output
        assert create_mock.call_count == 2
        assert create_mock.call_args_list[0].kwargs["template"] == "lite-template"
        assert create_mock.call_args_list[1].kwargs["template"] == "fallback-template"
        assert create_mock.call_args_list[0].kwargs["timeout"] == 90
        assert create_mock.call_args_list[1].kwargs["timeout"] == 90
        assert backend._active_template_alias == "fallback-template"

    def test_create_sandbox_without_template_keeps_legacy_behavior(self):
        """未配置模板时，应保持旧的 Sandbox.create(timeout=...) 行为。"""
        backend = BaiduCfcSandboxBackend(api_key="k", domain="d", sandbox_timeout=42)

        mock_sbx = MagicMock()
        create_mock = MagicMock(return_value=mock_sbx)
        fake_e2b_module = SimpleNamespace(
            Sandbox=SimpleNamespace(create=create_mock),
        )
        with patch.dict("sys.modules", {"e2b_code_interpreter": fake_e2b_module}):
            sandbox = backend._get_sandbox()

        assert sandbox is mock_sbx
        assert create_mock.call_count == 1
        assert create_mock.call_args.kwargs == {"timeout": 42}
        assert backend._active_template_alias is None

    def test_create_sandbox_bypasses_upstream_validation_for_baidu_cfc(self):
        """百度 CFC 的 bce-v3 凭证应绕过 upstream E2B 的本地 key 校验。"""
        backend = BaiduCfcSandboxBackend(
            api_key="bce-v3/ALTAK-test-key",
            domain="sandbox-execute.bj.baidubce.com",
            sandbox_timeout=42,
        )

        mock_sbx = MagicMock()
        mock_sbx.sandbox_id = "sandbox-bce-v3"
        original_validate_api_key = MagicMock(name="validate_api_key")
        fake_e2b_api = ModuleType("e2b.api")
        fake_e2b_api.validate_api_key = original_validate_api_key
        fake_e2b_pkg = ModuleType("e2b")
        fake_e2b_pkg.api = fake_e2b_api
        observed_validate_api_keys = []

        def create_mock(*, timeout, template=None):
            observed_validate_api_keys.append(fake_e2b_api.validate_api_key)
            assert timeout == 42
            assert template is None
            return mock_sbx

        fake_e2b_module = SimpleNamespace(
            Sandbox=SimpleNamespace(create=MagicMock(side_effect=create_mock)),
        )

        with patch.dict(
            "sys.modules",
            {
                "e2b": fake_e2b_pkg,
                "e2b.api": fake_e2b_api,
                "e2b_code_interpreter": fake_e2b_module,
            },
        ):
            sandbox = backend._get_sandbox()

        assert sandbox is mock_sbx
        assert fake_e2b_module.Sandbox.create.call_count == 1
        assert observed_validate_api_keys and observed_validate_api_keys[0] is not original_validate_api_key
        assert fake_e2b_api.validate_api_key is original_validate_api_key

    def test_create_sandbox_keeps_upstream_validation_for_e2b_keys(self):
        """真正的 e2b_ 凭证不应被绕过本地校验逻辑污染。"""
        backend = BaiduCfcSandboxBackend(
            api_key="e2b_0000000000000000000000000000000000000000",
            domain="sandbox.example.com",
            sandbox_timeout=42,
        )

        mock_sbx = MagicMock()
        mock_sbx.sandbox_id = "sandbox-e2b"
        original_validate_api_key = MagicMock(name="validate_api_key")
        fake_e2b_api = ModuleType("e2b.api")
        fake_e2b_api.validate_api_key = original_validate_api_key
        fake_e2b_pkg = ModuleType("e2b")
        fake_e2b_pkg.api = fake_e2b_api
        observed_validate_api_keys = []

        def create_mock(*, timeout, template=None):
            observed_validate_api_keys.append(fake_e2b_api.validate_api_key)
            assert timeout == 42
            assert template is None
            return mock_sbx

        fake_e2b_module = SimpleNamespace(
            Sandbox=SimpleNamespace(create=MagicMock(side_effect=create_mock)),
        )

        with patch.dict(
            "sys.modules",
            {
                "e2b": fake_e2b_pkg,
                "e2b.api": fake_e2b_api,
                "e2b_code_interpreter": fake_e2b_module,
            },
        ):
            sandbox = backend._get_sandbox()

        assert sandbox is mock_sbx
        assert fake_e2b_module.Sandbox.create.call_count == 1
        assert observed_validate_api_keys and observed_validate_api_keys[0] is original_validate_api_key
        assert fake_e2b_api.validate_api_key is original_validate_api_key

    def test_upload_files_success(self):
        """upload_files() 成功时应返回无错误的响应列表。"""
        backend = BaiduCfcSandboxBackend(api_key="k", domain="d")

        mock_sbx = MagicMock()
        mock_sbx.files.write.return_value = None
        backend._sbx = mock_sbx

        responses = backend.upload_files([
            ("/workspace/hello.py", b"print('hello')"),
            ("/workspace/data.txt", b"some data"),
        ])

        assert len(responses) == 2
        assert all(r.error is None for r in responses)
        assert mock_sbx.files.write.call_count == 2

    def test_upload_files_partial_failure(self):
        """upload_files() 部分失败时应单独标记错误，不影响其他文件。"""
        backend = BaiduCfcSandboxBackend(api_key="k", domain="d")

        mock_sbx = MagicMock()
        mock_sbx.files.write.side_effect = [
            None,                            # 第一个文件成功
            IOError("磁盘空间不足"),          # 第二个文件失败
        ]
        backend._sbx = mock_sbx

        responses = backend.upload_files([
            ("/ok.py", b"content"),
            ("/fail.py", b"content"),
        ])

        assert responses[0].error is None
        assert responses[1].error is not None
        assert "磁盘空间不足" in responses[1].error

    def test_download_files_success(self):
        """download_files() 成功时应返回正确的字节内容。"""
        backend = BaiduCfcSandboxBackend(api_key="k", domain="d")

        mock_sbx = MagicMock()
        mock_sbx.files.read.return_value = b"file content here"
        backend._sbx = mock_sbx

        responses = backend.download_files(["/workspace/result.txt"])

        assert len(responses) == 1
        assert responses[0].content == b"file content here"
        assert responses[0].error is None

    def test_close_kills_sandbox(self):
        """close() 应调用 sandbox.kill() 并清空 _sbx。"""
        backend = BaiduCfcSandboxBackend(api_key="k", domain="d")

        mock_sbx = MagicMock()
        backend._sbx = mock_sbx

        backend.close()

        mock_sbx.kill.assert_called_once()
        assert backend._sbx is None

    def test_context_manager(self):
        """作为上下文管理器时，__exit__ 应自动关闭沙箱。"""
        backend = BaiduCfcSandboxBackend(api_key="k", domain="d")
        mock_sbx = MagicMock()
        backend._sbx = mock_sbx

        with backend:
            pass  # 进入上下文

        mock_sbx.kill.assert_called_once()


# ============================================================
#  Unit Tests: AgentConfig
# ============================================================

class TestAgentConfig:
    """AgentConfig 扩展字段测试。"""

    def test_enable_deep_thinking_default_false(self):
        """enable_deep_thinking 默认应为 False。"""
        config = AgentConfig(user_id=uuid4(), invoke_from=InvokeFrom.DEBUGGER.value)
        assert config.enable_deep_thinking is False

    def test_enable_deep_thinking_can_be_set(self):
        """enable_deep_thinking 应可设置为 True。"""
        config = AgentConfig(
            user_id=uuid4(),
            invoke_from=InvokeFrom.DEBUGGER.value,
            enable_deep_thinking=True,
        )
        assert config.enable_deep_thinking is True

    def test_deep_thinking_prompt_has_required_placeholders(self):
        """DEEP_THINKING_SYSTEM_PROMPT 应包含 {preset_prompt} 和 {long_term_memory} 占位符。"""
        assert "{preset_prompt}" in DEEP_THINKING_SYSTEM_PROMPT
        assert "{long_term_memory}" in DEEP_THINKING_SYSTEM_PROMPT

    def test_deep_thinking_prompt_format(self):
        """DEEP_THINKING_SYSTEM_PROMPT.format() 应正常工作。"""
        filled = DEEP_THINKING_SYSTEM_PROMPT.format(
            preset_prompt="你是助手",
            long_term_memory="用户喜欢简洁",
        )
        assert "你是助手" in filled
        assert "用户喜欢简洁" in filled


# ============================================================
#  Unit Tests: QueueEvent
# ============================================================

class TestQueueEvent:
    """QueueEvent 枚举测试。"""

    def test_deep_thinking_event_exists(self):
        """DEEP_THINKING 枚举值应存在且值为 'deep_thinking'。"""
        assert QueueEvent.DEEP_THINKING == "deep_thinking"
        assert QueueEvent.DEEP_THINKING.value == "deep_thinking"
        assert QueueEvent.DEEP_STEP == "deep_step"
        assert QueueEvent.DEEP_COMPLETE == "deep_complete"
        assert QueueEvent.DEEP_ARTIFACT_CREATED == "deep_artifact_created"

    def test_existing_events_unchanged(self):
        """添加 DEEP_THINKING 后，原有事件不应改变。"""
        assert QueueEvent.AGENT_MESSAGE  == "agent_message"
        assert QueueEvent.AGENT_THOUGHT  == "agent_thought"
        assert QueueEvent.AGENT_ACTION   == "agent_action"
        assert QueueEvent.AGENT_END      == "agent_end"
        assert QueueEvent.DATASET_RETRIEVAL == "dataset_retrieval"


# ============================================================
#  Unit Tests: DeepThinkingAgent 图结构
# ============================================================

class TestDeepThinkingAgentGraph:
    """DeepThinkingAgent LangGraph 图结构测试。"""

    @pytest.mark.parametrize("empty_chunk", [False, True])
    def test_a2a_deep_thinking_agent_should_end_without_text(self, empty_chunk):
        chunks = [_make_chunk("")] if empty_chunk else []
        agent = A2ADeepThinkingAgent(
            llm=_make_llm(stream_chunks=chunks),
            agent_config=_make_agent_config(),
        )
        published = []
        agent.agent_queue_manager.publish = lambda _task_id, event: published.append(event)

        result = agent._llm_node({
            "messages": [HumanMessage(content="q")],
            "task_id": uuid4(),
            "iteration_count": 0,
        })

        assert result["messages"][0].content == ""
        assert [event.event for event in published] == [QueueEvent.AGENT_END]

    def _build_agent(self):
        llm = _make_llm()
        config = _make_agent_config(enable_deep_thinking=True)
        return DeepThinkingAgent(llm=llm, agent_config=config)

    @staticmethod
    def _build_state(query: str = "帮我写一个排序算法"):
        return {
            "messages": [HumanMessage(content=query)],
            "task_id": uuid4(),
            "iteration_count": 0,
            "history": [],
            "long_term_memory": "",
        }

    @staticmethod
    def _route(**overrides):
        payload = {
            "need_sandbox": False,
            "need_file_io": False,
            "need_execute": False,
            "need_subagent": False,
            "need_artifact_output": False,
            "reason": "测试路由",
            "summary": "无需沙箱，使用普通深度思考",
        }
        payload.update(overrides)
        return DeepRouteDecision(
            **payload,
        )

    def test_graph_compiles_without_error(self):
        """_build_agent() 应能成功编译 LangGraph 图，不抛异常。"""
        agent = self._build_agent()
        assert agent._agent is not None

    def test_decide_deep_route_for_explicit_artifact_request_skips_model_vote(self):
        """显式文件请求应规则优先，不能先让模型投票决定是否走文件链路。"""
        llm = _make_llm()
        structured_llm = MagicMock()
        structured_llm.invoke.return_value = self._route()
        llm.with_structured_output.return_value = structured_llm

        agent = DeepThinkingAgent(llm=llm, agent_config=_make_agent_config(enable_deep_thinking=True))

        decision = agent._decide_deep_route(
            "生成 SpaceX IPO 招股说明书 txt 文件，要求输出可下载 .txt 附件。"
            "请保存为 SpaceX_IPO_Prospectus_Draft.txt。"
        )

        assert decision.need_sandbox is True
        assert decision.need_file_io is True
        assert decision.need_artifact_output is True
        assert decision.need_execute is False
        llm.with_structured_output.assert_not_called()

    def test_final_llm_node_should_not_bind_tools_after_deep_execution(self):
        """深度执行后的最终回答阶段不应再绑定业务工具，避免误调 sandbox_exec。"""
        @tool
        def google_serper(query: str) -> str:
            """Fake search tool."""
            return query

        llm = _make_llm(stream_chunks=[_make_chunk("最终回答")])
        object.__setattr__(llm, "bind_tools", MagicMock(return_value=llm))
        config = _make_agent_config(
            enable_deep_thinking=True,
            tools=[google_serper],
        )
        agent = DeepThinkingAgent(llm=llm, agent_config=config)
        agent.agent_queue_manager.publish = MagicMock()

        result = agent._llm_node({
            "messages": [
                AIMessage(
                    content=(
                        "<deep_execution_summary>\n"
                        "- used_sandbox: true\n"
                        "</deep_execution_summary>\n"
                        "<deep_thinking_result>\n"
                        "规划完成\n"
                        "</deep_thinking_result>\n"
                        "<generated_artifacts>\n"
                        "- plan.md (https://cos.example.com/plan.md)\n"
                        "</generated_artifacts>"
                    )
                )
            ],
            "task_id": uuid4(),
            "iteration_count": 0,
        })

        assert result["messages"][0].content == "最终回答"
        llm.bind_tools.assert_not_called()
        assert agent.agent_config.tools == config.tools

    def test_final_llm_node_should_strip_sandbox_links_without_artifacts(self):
        """深度执行最终回答不应泄漏 sandbox:/mnt/data 下载链接，且无产物时要明确说明。"""
        llm = _make_llm(
            stream_chunks=[
                _make_chunk(
                    "您可以下载查看完整文件："
                    "[SpaceX_IPO_Prospectus_Draft.md](sandbox:/mnt/data/SpaceX_IPO_Prospectus_Draft.md)"
                )
            ]
        )
        agent = DeepThinkingAgent(llm=llm, agent_config=_make_agent_config(enable_deep_thinking=True))
        published = []
        agent.agent_queue_manager.publish = lambda tid, thought: published.append(thought)

        result = agent._llm_node({
            "messages": [
                AIMessage(
                    content=(
                        "<deep_execution_summary>\n"
                        "- used_sandbox: true\n"
                        "</deep_execution_summary>\n"
                        "<deep_thinking_result>\n"
                        "草案已完成\n"
                        "</deep_thinking_result>"
                    )
                )
            ],
            "task_id": uuid4(),
            "iteration_count": 0,
        })

        final_message = result["messages"][0].content
        assert "sandbox:/mnt/data/" not in final_message
        assert "当前没有可下载附件" in final_message
        assert any(
            event.event == QueueEvent.AGENT_MESSAGE and "sandbox:/mnt/data/" not in event.answer
            for event in published
        )

    def test_final_llm_node_materializes_plain_text_artifact_before_agent_end(self):
        """深度执行最终回答若是完整文本文档，应在 AGENT_END 前自动 materialize 为可下载附件。"""
        llm = _make_llm(
            stream_chunks=[
                _make_chunk(
                    "================================================================================\n"
                    "SPACE EXPLORATION TECHNOLOGIES CORP.\n"
                    "PROSPECTUS DRAFT\n"
                    "================================================================================\n\n"
                    "PROSPECTUS SUMMARY\n"
                    "The Company ...\n\n"
                    "RISK FACTORS\n"
                    "..."
                )
            ]
        )
        agent = DeepThinkingAgent(llm=llm, agent_config=_make_agent_config(enable_deep_thinking=True))
        agent.agent_queue_manager.publish = MagicMock()
        runtime_flask_app = MagicMock()
        runtime_flask_app.app_context.return_value = nullcontext()
        agent.agent_config.runtime_flask_app = runtime_flask_app

        mock_upload_file = SimpleNamespace(
            id=uuid4(),
            name="SpaceX_IPO_Prospectus_Draft.txt",
            size=1024,
            extension="txt",
            mime_type="text/plain",
            key="artifacts/SpaceX_IPO_Prospectus_Draft.txt",
        )
        mock_cos_service = MagicMock()
        mock_cos_service.upload_bytes.return_value = mock_upload_file
        mock_cos_service.get_file_url.return_value = "https://cos.example.com/artifacts/SpaceX_IPO_Prospectus_Draft.txt"
        mock_injector = MagicMock()
        mock_injector.get.return_value = mock_cos_service

        published = []
        agent.agent_queue_manager.publish = lambda tid, thought: published.append(thought)

        with patch("app.http.module.injector", mock_injector), \
             patch("internal.core.agent.agents.deep_thinking_agent.has_app_context", return_value=False):
            result = agent._llm_node({
                "messages": [
                    HumanMessage(
                        content=(
                            "生成 SpaceX IPO 招股说明书 txt 文件，要求输出可下载 .txt 附件。"
                            "内容包含：封面摘要、业务概览、风险因素、MD&A、募集资金用途、法律声明。"
                            "请保存为 SpaceX_IPO_Prospectus_Draft.txt。"
                        )
                    ),
                    AIMessage(
                        content=(
                            "<deep_execution_summary>\n"
                            "- used_sandbox: true\n"
                            "</deep_execution_summary>\n"
                            "<deep_thinking_result>\n"
                            "================================================================================\n"
                            "SPACE EXPLORATION TECHNOLOGIES CORP.\n"
                            "PROSPECTUS DRAFT\n"
                            "================================================================================\n\n"
                            "PROSPECTUS SUMMARY\n"
                            "The Company designs, manufactures, and operates advanced rockets and spacecraft.\n\n"
                            "BUSINESS OVERVIEW\n"
                            "Starlink provides satellite broadband services.\n\n"
                            "RISK FACTORS\n"
                            "Launch and regulatory risk remain material.\n\n"
                            "MD&A\n"
                            "Management expects continued capital intensity.\n\n"
                            "USE OF PROCEEDS\n"
                            "Proceeds will support Starship and Starlink.\n\n"
                            "LEGAL MATTERS\n"
                            "Forward-looking statements apply.\n"
                            "</deep_thinking_result>"
                        )
                    ),
                ],
                "task_id": uuid4(),
                "iteration_count": 0,
            })

        final_message = result["messages"][0].content
        assert "已生成可下载附件：SpaceX_IPO_Prospectus_Draft.txt" in final_message
        assert "当前没有可下载附件" not in final_message
        assert mock_cos_service.upload_bytes.call_count == 1
        assert any(event.event == QueueEvent.DEEP_ARTIFACT_CREATED for event in published)
        artifact_idx = next(i for i, event in enumerate(published) if event.event == QueueEvent.DEEP_ARTIFACT_CREATED)
        end_idx = next(i for i, event in enumerate(published) if event.event == QueueEvent.AGENT_END)
        assert artifact_idx < end_idx
        assert any(
            event.event == QueueEvent.AGENT_MESSAGE and "已生成可下载附件：SpaceX_IPO_Prospectus_Draft.txt" in event.answer
            for event in published
        )

    def test_final_llm_node_prefers_deep_thinking_result_over_short_summary_for_plain_text_artifact(self):
        """当最终回答只是总结句时，应优先使用 deep_thinking_result 中的完整正文生成附件。"""
        llm = _make_llm(
            stream_chunks=[
                _make_chunk("我将合并所有章节内容并保存为完整的招股说明书文件。")
            ]
        )
        agent = DeepThinkingAgent(llm=llm, agent_config=_make_agent_config(enable_deep_thinking=True))
        runtime_flask_app = MagicMock()
        runtime_flask_app.app_context.return_value = nullcontext()
        agent.agent_config.runtime_flask_app = runtime_flask_app

        mock_upload_file = SimpleNamespace(
            id=uuid4(),
            name="SpaceX_IPO_Prospectus_Draft.txt",
            size=8192,
            extension="txt",
            mime_type="text/plain",
            key="artifacts/SpaceX_IPO_Prospectus_Draft.txt",
        )
        mock_cos_service = MagicMock()
        mock_cos_service.upload_bytes.return_value = mock_upload_file
        mock_cos_service.get_file_url.return_value = "https://cos.example.com/artifacts/SpaceX_IPO_Prospectus_Draft.txt"
        mock_injector = MagicMock()
        mock_injector.get.return_value = mock_cos_service

        published = []
        agent.agent_queue_manager.publish = lambda tid, thought: published.append(thought)

        deep_thinking_result = (
            "================================================================================\n"
            "SPACE EXPLORATION TECHNOLOGIES CORP.\n"
            "PROSPECTUS DRAFT\n"
            "================================================================================\n\n"
            "PROSPECTUS SUMMARY\n"
            "The Company designs, manufactures, and operates advanced rockets and spacecraft.\n\n"
            "BUSINESS OVERVIEW\n"
            "Starlink provides satellite broadband services.\n\n"
            "RISK FACTORS\n"
            "Launch and regulatory risk remain material.\n\n"
            "MD&A\n"
            "Management expects continued capital intensity.\n\n"
            "USE OF PROCEEDS\n"
            "Proceeds will support Starship and Starlink.\n\n"
            "LEGAL MATTERS\n"
            "Forward-looking statements apply.\n"
        )

        with patch("app.http.module.injector", mock_injector), \
             patch("internal.core.agent.agents.deep_thinking_agent.has_app_context", return_value=False):
            result = agent._llm_node({
                "messages": [
                    HumanMessage(
                        content=(
                            "生成 SpaceX IPO 招股说明书 txt 文件，要求输出可下载 .txt 附件。"
                            "内容包含：封面摘要、业务概览、风险因素、MD&A、募集资金用途、法律声明。"
                            "请保存为 SpaceX_IPO_Prospectus_Draft.txt。"
                        )
                    ),
                    AIMessage(
                        content=(
                            "<deep_execution_summary>\n"
                            "- used_sandbox: true\n"
                            "</deep_execution_summary>\n"
                            f"<deep_thinking_result>\n{deep_thinking_result}\n</deep_thinking_result>"
                        )
                    ),
                ],
                "task_id": uuid4(),
                "iteration_count": 0,
            })

        final_message = result["messages"][0].content
        assert "已生成可下载附件：SpaceX_IPO_Prospectus_Draft.txt" in final_message
        assert mock_cos_service.upload_bytes.call_count == 1
        uploaded_content = mock_cos_service.upload_bytes.call_args.kwargs["content"].decode("utf-8")
        assert "PROSPECTUS SUMMARY" in uploaded_content
        assert "BUSINESS OVERVIEW" in uploaded_content
        assert "RISK FACTORS" in uploaded_content
        assert "MD&A" in uploaded_content
        assert "USE OF PROCEEDS" in uploaded_content
        assert "LEGAL MATTERS" in uploaded_content
        assert len(uploaded_content) > 500
        assert any(event.event == QueueEvent.DEEP_ARTIFACT_CREATED for event in published)
        assert any(
            event.event == QueueEvent.AGENT_MESSAGE and "已生成可下载附件：SpaceX_IPO_Prospectus_Draft.txt" in event.answer
            for event in published
        )

    def test_final_llm_node_should_not_materialize_from_summary_only(self):
        """最终回答即使看起来像文档，也不应在缺少 deep_thinking_result 时被误当成附件正文。"""
        llm = _make_llm(
            stream_chunks=[
                _make_chunk(
                    "================================================================================\n"
                    "SPACE EXPLORATION TECHNOLOGIES CORP.\n"
                    "PROSPECTUS DRAFT\n"
                    "================================================================================\n\n"
                    "PROSPECTUS SUMMARY\n"
                    "The Company designs, manufactures, and operates advanced rockets and spacecraft.\n\n"
                    "BUSINESS OVERVIEW\n"
                    "Starlink provides satellite broadband services.\n\n"
                    "RISK FACTORS\n"
                    "Launch and regulatory risk remain material.\n"
                )
            ]
        )
        agent = DeepThinkingAgent(llm=llm, agent_config=_make_agent_config(enable_deep_thinking=True))
        agent.agent_queue_manager.publish = MagicMock()
        runtime_flask_app = MagicMock()
        runtime_flask_app.app_context.return_value = nullcontext()
        agent.agent_config.runtime_flask_app = runtime_flask_app

        mock_cos_service = MagicMock()
        mock_injector = MagicMock()
        mock_injector.get.return_value = mock_cos_service

        with patch("app.http.module.injector", mock_injector), \
             patch("internal.core.agent.agents.deep_thinking_agent.has_app_context", return_value=False):
            result = agent._llm_node({
                "messages": [
                    HumanMessage(
                        content=(
                            "生成 SpaceX IPO 招股说明书 txt 文件，要求输出可下载 .txt 附件。"
                            "内容包含：封面摘要、业务概览、风险因素、MD&A、募集资金用途、法律声明。"
                            "请保存为 SpaceX_IPO_Prospectus_Draft.txt。"
                        )
                    ),
                    AIMessage(
                        content=(
                            "<deep_execution_summary>\n"
                            "- used_sandbox: true\n"
                            "</deep_execution_summary>\n"
                            "<deep_thinking_result>\n\n"
                            "</deep_thinking_result>"
                        )
                    ),
                ],
                "task_id": uuid4(),
                "iteration_count": 0,
            })

        assert mock_cos_service.upload_bytes.call_count == 0
        assert "PROSPECTUS SUMMARY" in result["messages"][0].content
        assert "已生成可下载附件" not in result["messages"][0].content

    def test_extract_write_file_payload_from_tool_call_block(self):
        """应能从 write_file 工具调用文本中恢复路径和文件内容。"""
        answer = """<tool_call>write_file<arg_key>path</arg_key><arg_value>SpaceX_IPO_Prospectus_Draft.txt<arg_key>content</arg_key><arg_value>hello world"""

        payload = ArtifactPolicy.extract_write_file_payload(answer)

        assert payload is not None
        path, content = payload
        assert path == "SpaceX_IPO_Prospectus_Draft.txt"
        assert content == "hello world"

    def test_extract_write_file_payload_from_namespaced_xml_tool_call(self):
        """应能从带命名空间前缀的结构化工具调用中恢复路径和文件内容。"""
        answer = """<vendorx:tool_call>
<invoke name="write_file">
    <parameter name="file_name">SpaceX_IPO_Prospectus_Draft.txt</parameter>
    <parameter name="content">hello world
line two</parameter>
</invoke>
</vendorx:tool_call>"""

        payload = ArtifactPolicy.extract_write_file_payload(answer)

        assert payload is not None
        path, content = payload
        assert path == "SpaceX_IPO_Prospectus_Draft.txt"
        assert content == "hello world\nline two"

    def test_extract_write_file_payload_from_python_code_block(self):
        """应能从 Python 代码块中的 filepath/content 恢复路径和文件内容。"""
        answer = """```python
filepath = "SpaceX_IPO_Prospectus_Draft.txt"
content = \"\"\"hello world
line two
\"\"\"

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
```"""

        payload = ArtifactPolicy.extract_write_file_payload(answer)

        assert payload is not None
        path, content = payload
        assert path == "SpaceX_IPO_Prospectus_Draft.txt"
        assert content == "hello world\nline two"

    def test_extract_write_file_payload_from_generated_artifacts_block(self):
        """应能从 generated_artifacts 区块中恢复文件路径和文件内容。"""
        answer = """<generated_artifacts>
<artifact id="spacex_prospectus" title="SpaceX IPO Prospectus Draft" commit_message="Generate SpaceX IPO Prospectus Draft in txt format">

SPACE EXPLORATION TECHNOLOGIES CORP.
IPO招股说明书草案
</artifact>
</generated_artifacts>"""

        payload = ArtifactPolicy.extract_write_file_payload(answer)

        assert payload is not None
        path, content = payload
        assert path == "SpaceX_IPO_Prospectus_Draft.txt"
        assert "SPACE EXPLORATION TECHNOLOGIES CORP." in content
        assert "IPO招股说明书草案" in content

    def test_infer_requested_artifact_filename_from_query(self):
        """应能从用户请求中提取明确的目标文件名。"""
        query = "生成 SpaceX IPO 招股说明书 txt 文件，请保存为 SpaceX_IPO_Prospectus_Draft.txt。"

        filename = ArtifactPolicy.infer_requested_artifact_filename(query)

        assert filename == "SpaceX_IPO_Prospectus_Draft.txt"

    def test_resolve_artifact_filename_without_explicit_name_for_prospectus(self):
        """用户未显式命名时，应能稳定推断出招股书默认文件名。"""
        query = (
            "生成 SpaceX IPO 招股说明书 txt 文件，要求输出可下载 .txt 附件。"
            "内容包含：封面摘要、业务概览、风险因素、MD&A、募集资金用途、法律声明。"
        )

        filename = ArtifactPolicy.resolve_artifact_filename(query, allow_default_filename=True)

        assert filename == "SpaceX_IPO_Prospectus_Draft.txt"

    def test_resolve_artifact_filename_without_explicit_name_for_travel(self):
        """用户未显式命名时，应能退化为通用旅行文件名，而不是依赖城市白名单。"""
        query = (
            "请输出可下载的 Markdown 附件。内容包含：行程总览、每日安排、住宿建议、交通建议、预算。"
            "我第一次去北京，只有 2 天时间，同行有长辈。"
        )

        filename = ArtifactPolicy.resolve_artifact_filename(query, allow_default_filename=True)

        assert filename == "Travel_Plan.md"

    def test_build_document_outline_fallback_is_generic(self):
        """结构化文档 fallback 不应依赖招股书/旅行/报告等领域关键词分支。"""
        prospectus_outline = DeepThinkingAgent._build_document_outline_fallback(
            "生成 SpaceX IPO 招股说明书 txt 文件",
            "SpaceX_IPO_Prospectus_Draft.txt",
        )
        travel_outline = DeepThinkingAgent._build_document_outline_fallback(
            "生成北京旅行规划 markdown 文件",
            "北京旅行规划.md",
        )

        assert [section.title for section in prospectus_outline.sections] == [
            "摘要",
            "主体内容",
            "补充说明",
            "结论与下一步",
        ]
        assert [section.title for section in travel_outline.sections] == [
            "摘要",
            "主体内容",
            "补充说明",
            "结论与下一步",
        ]
        assert prospectus_outline.sections == travel_outline.sections

    def test_build_local_document_section_body_is_generic(self):
        """本地章节兜底不应再根据具体领域词切换不同模板。"""
        outline = StructuredDocumentOutlinePlan(
            document_title="任意文档",
            sections=[
                StructuredDocumentSectionPlan(
                    title="摘要",
                    purpose="概述文档目标。",
                    key_points=["主题", "范围", "关键结论"],
                    target_length_hint="约 200-300 字",
                )
            ],
        )

        body = DeepThinkingAgent._build_local_document_section_body(
            query="生成 SpaceX IPO 招股说明书 txt 文件",
            outline=outline,
            section=outline.sections[0],
            section_index=1,
            section_total=4,
            markdown=True,
        )

        assert "招股说明书" not in body
        assert "旅行" not in body
        assert "报告" not in body
        assert "文档整体目标" in body

    def test_extract_requested_outline_section_titles_from_query(self):
        """应从用户 query 中提取显式章节候选，而不是依赖领域写死。"""
        query = (
            "请输出可下载的 Markdown 附件。内容包含：行程总览、每日安排、住宿建议、交通建议、预算。"
            "我第一次去北京，只有 2 天时间，同行有长辈。"
        )

        titles = DeepThinkingAgent._extract_requested_outline_section_titles(query)

        assert titles == [
            "行程总览",
            "每日安排",
            "住宿建议",
            "交通建议",
            "预算",
        ]

    def test_extract_requested_outline_section_titles_ignores_evaluation_blocks(self):
        """章节提取器应忽略“正常结果/通过标准”一类验收说明，避免把它们误当成文档章节。"""
        query = (
            "生成 SpaceX IPO 招股说明书 txt 文件，要求输出可下载 .txt 附件。"
            "内容包含：封面摘要、业务概览、风险因素、MD&A、募集资金用途、法律声明。"
            "正常结果："
            "- 出现可下载附件 SpaceX_IPO_Prospectus_Draft.txt"
            "- 文件内容包含 6 个章节"
            "- 文件大小应是 KB 级，不是几十字节的短总结"
            "- 不能出现本地沙箱路径链接"
        )

        titles = DeepThinkingAgent._extract_requested_outline_section_titles(query)

        assert titles == [
            "封面摘要",
            "业务概览",
            "风险因素",
            "MD&A",
            "募集资金用途",
            "法律声明",
        ]

    def test_build_document_outline_fallback_ignores_evaluation_blocks(self):
        """当 query 同时包含需求与验收说明时，fallback 仍应只保留需求章节，而不是误吞验收文本。"""
        query = (
            "生成 SpaceX IPO 招股说明书 txt 文件，要求输出可下载 .txt 附件。"
            "内容包含：封面摘 要、业务概览、风险因素、MD&A、募集资金用途、法律声明。"
            "正常结果："
            "- 出现可下载附件 SpaceX_IPO_Prospectus_Draft.txt"
            "- 文件内容包含 6 个章节"
            "- 文件大小应是 KB 级，不是几十字节的短总结"
            "- 不能出现本地沙箱路径链接"
        )

        outline = DeepThinkingAgent._build_document_outline_fallback(
            query=query,
            filename="SpaceX_IPO_Prospectus_Draft.txt",
        )

        assert [section.title for section in outline.sections] == [
            "封面摘要",
            "业务概览",
            "风险因素",
            "MD&A",
            "募集资金用途",
            "法律声明",
        ]

    def test_generate_structured_document_outline_repairs_and_preserves_requested_sections(self):
        """structured output 丢失显式章节时，应进入修复层并尽量保留用户已明确列出的章节。"""
        agent = self._build_agent()
        timeline = MagicMock()

        outline_llm = MagicMock()
        outline_llm.invoke.return_value = StructuredDocumentOutlinePlan(
            document_title="SpaceX IPO Prospectus Draft",
            sections=[
                StructuredDocumentSectionPlan(
                    title="摘要",
                    purpose="概述文档目标。",
                    key_points=["主题", "目标", "范围"],
                    target_length_hint="约 200-300 字",
                ),
                StructuredDocumentSectionPlan(
                    title="主体内容",
                    purpose="展开主要信息。",
                    key_points=["主要内容", "细节", "逻辑"],
                    target_length_hint="约 400-700 字",
                ),
                StructuredDocumentSectionPlan(
                    title="补充说明",
                    purpose="补充约束与注意事项。",
                    key_points=["约束", "注意事项", "风险"],
                    target_length_hint="约 200-400 字",
                ),
                StructuredDocumentSectionPlan(
                    title="结论与下一步",
                    purpose="总结并给出后续建议。",
                    key_points=["结论", "建议", "下一步"],
                    target_length_hint="约 200-300 字",
                ),
            ],
        )
        repair_llm = MagicMock()
        repair_llm.invoke.return_value = StructuredDocumentOutlinePlan(
            document_title="通用文档",
            sections=[
                StructuredDocumentSectionPlan(
                    title="背景",
                    purpose="概述文档背景和目标。",
                    key_points=["背景", "目标", "范围"],
                    target_length_hint="约 200-300 字",
                ),
                StructuredDocumentSectionPlan(
                    title="分析",
                    purpose="展开主要分析内容。",
                    key_points=["主要分析", "细节", "结论依据"],
                    target_length_hint="约 400-700 字",
                ),
                StructuredDocumentSectionPlan(
                    title="结论",
                    purpose="总结并给出下一步。",
                    key_points=["结论", "建议", "下一步"],
                    target_length_hint="约 200-300 字",
                ),
            ],
        )
        agent.llm.with_structured_output.side_effect = [outline_llm, repair_llm]

        query = (
            "请输出可下载的 Markdown 附件。内容包含：背景、分析、结论。"
            "请严格按这三部分组织内容，不要额外扩展章节。"
        )

        outline = agent._generate_structured_document_outline(
            query=query,
            filename="SpaceX_IPO_Prospectus_Draft.txt",
            route_decision=self._route(
                need_sandbox=True,
                need_execute=True,
                need_file_io=True,
                need_artifact_output=True,
                summary="需要沙箱执行",
            ),
            timeline=timeline,
        )

        assert agent.llm.with_structured_output.call_count == 2
        assert [section.title for section in outline.sections] == [
            "背景",
            "分析",
            "结论",
        ]
        assert timeline.publish_step.call_count >= 3

    def test_generate_structured_document_outline_accepts_three_sections_without_repair(self):
        """模型若基于 query 自行决定只产出 3 章，也应被接受，不应被硬性数量门槛拦截。"""
        agent = self._build_agent()
        timeline = MagicMock()

        outline_llm = MagicMock()
        outline_llm.invoke.return_value = StructuredDocumentOutlinePlan(
            document_title="通用文档",
            sections=[
                StructuredDocumentSectionPlan(
                    title="摘要",
                    purpose="概述整体目标。",
                    key_points=["目标", "范围", "结论"],
                    target_length_hint="约 200-300 字",
                ),
                StructuredDocumentSectionPlan(
                    title="主体内容",
                    purpose="展开主要内容。",
                    key_points=["主要内容", "细节", "建议"],
                    target_length_hint="约 400-700 字",
                ),
                StructuredDocumentSectionPlan(
                    title="结论",
                    purpose="总结并给出下一步。",
                    key_points=["结论", "建议", "下一步"],
                    target_length_hint="约 200-300 字",
                ),
            ],
        )
        agent.llm.with_structured_output.return_value = outline_llm

        outline = agent._generate_structured_document_outline(
            query="请帮我写一份简短文档，分为摘要、主体内容和结论即可。",
            filename="generic_document.txt",
            route_decision=self._route(
                need_sandbox=True,
                need_execute=True,
                need_file_io=True,
                need_artifact_output=True,
                summary="需要沙箱执行",
            ),
            timeline=timeline,
        )

        assert agent.llm.with_structured_output.call_count == 1
        assert [section.title for section in outline.sections] == [
            "摘要",
            "主体内容",
            "结论",
        ]
        assert timeline.publish_step.call_count >= 2

    def test_generate_structured_document_outline_falls_back_to_generic_when_repair_fails(self):
        """structured output 与修复都失败时，才回到通用 4 章 fallback。"""
        agent = self._build_agent()
        timeline = MagicMock()

        outline_llm = MagicMock()
        outline_llm.invoke.side_effect = ValueError("Invalid JSON: expected value")
        repair_llm = MagicMock()
        repair_llm.invoke.side_effect = ValueError("repair failed")
        agent.llm.with_structured_output.side_effect = [outline_llm, repair_llm]

        outline = agent._generate_structured_document_outline(
            query="请帮我写一份通用文档，内容尽量完整。",
            filename="generic_document.txt",
            route_decision=self._route(
                need_sandbox=True,
                need_execute=True,
                need_file_io=True,
                need_artifact_output=True,
                summary="需要沙箱执行",
            ),
            timeline=timeline,
        )

        assert agent.llm.with_structured_output.call_count == 2
        assert [section.title for section in outline.sections] == [
            "摘要",
            "主体内容",
            "补充说明",
            "结论与下一步",
        ]
        assert timeline.publish_step.call_count >= 3

    def test_generate_structured_document_outline_preserves_query_sections_when_fallback_is_needed(self):
        """当 structured output 与 repair 都失败时，若 query 已明确列出章节，应保留这些章节，而不是退成通用 4 章。"""
        agent = self._build_agent()
        timeline = MagicMock()

        outline_llm = MagicMock()
        outline_llm.invoke.side_effect = ValueError("Invalid JSON: expected value")
        repair_llm = MagicMock()
        repair_llm.invoke.side_effect = ValueError("repair failed")
        agent.llm.with_structured_output.side_effect = [outline_llm, repair_llm]

        query = (
            "生成 SpaceX IPO 招股说明书 txt 文件，要求输出可下载 .txt 附件。"
            "内容包含：封面摘要、业务概览、风险因素、MD&A、募集资金用途、法律声明。"
        )

        outline = agent._generate_structured_document_outline(
            query=query,
            filename="SpaceX_IPO_Prospectus_Draft.txt",
            route_decision=self._route(
                need_sandbox=True,
                need_execute=True,
                need_file_io=True,
                need_artifact_output=True,
                summary="需要沙箱执行",
            ),
            timeline=timeline,
        )

        assert agent.llm.with_structured_output.call_count == 2
        assert [section.title for section in outline.sections] == [
            "封面摘要",
            "业务概览",
            "风险因素",
            "MD&A",
            "募集资金用途",
            "法律声明",
        ]
        assert timeline.publish_step.call_count >= 3

    def test_strip_plain_text_artifact_preamble_filters_generic_boilerplate(self):
        """附件前导清洗应按通用 boilerplate 规则工作，而不是依赖长名单。"""
        text = (
            "说明：当前对话环境暂不直接支持自动生成可下载附件，但以下为您提供完整、可直接复制保存的 .txt 文件内容。\n\n"
            "================================================================================\n"
            "SPACE EXPLORATION TECHNOLOGIES CORP.\n"
            "PROSPECTUS DRAFT\n"
            "================================================================================\n\n"
            "PROSPECTUS SUMMARY\n"
            "The Company ...\n"
        )

        cleaned = ArtifactPolicy.strip_plain_text_artifact_preamble(text)

        assert "暂不直接支持自动生成可下载附件" not in cleaned
        assert "请复制以下全部内容" not in cleaned
        assert cleaned.startswith("================================================================================")
        assert "SPACE EXPLORATION TECHNOLOGIES CORP." in cleaned

    @patch.object(DeepThinkingAgent, "_build_deep_agent")
    @patch.object(DeepThinkingAgent, "_decide_deep_route")
    def test_deep_agent_node_recovers_missing_write_file_artifact(self, mock_route, mock_build_deep):
        """首次未扫描到附件时，应尝试把 write_file 文本恢复为真实产物并重新扫描。"""
        mock_route.return_value = self._route(
            need_sandbox=True,
            need_execute=True,
            need_file_io=True,
            need_artifact_output=True,
            summary="需要沙箱执行",
        )
        mock_deep_agent = MagicMock()
        mock_deep_agent.invoke.return_value = {
            "messages": [
                AIMessage(
                    content=(
                        "<tool_call>write_file<arg_key>path</arg_key>"
                        "<arg_value>SpaceX_IPO_Prospectus_Draft.json<arg_key>content</arg_key>"
                        "<arg_value>final prospectus text"
                    )
                )
            ],
        }

        backend = MagicMock()
        backend.upload_files.return_value = [
            SimpleNamespace(path="/workspace/artifacts/task-1/SpaceX_IPO_Prospectus_Draft.json", error=None)
        ]
        mock_build_deep.return_value = (mock_deep_agent, backend, "/workspace/artifacts/task-1", True)

        agent = self._build_agent()
        agent.agent_queue_manager.publish = MagicMock()
        recover_mock = MagicMock(return_value=True)
        collect_mock = MagicMock(side_effect=[
            [],
            [{"name": "SpaceX_IPO_Prospectus_Draft.json", "url": "https://cos.example.com/SpaceX_IPO_Prospectus_Draft.json"}],
        ])
        agent._recover_missing_artifact_from_deep_answer = recover_mock
        agent._collect_artifacts = collect_mock

        result = agent._deep_agent_node(
            self._build_state(
                "请生成 SpaceX IPO 数据摘要 json 文件，要求输出可下载 .json 附件。"
                "内容包含：封面摘要、业务概览、风险因素、MD&A、募集资金用途、法律声明。"
                "请保存为 SpaceX_IPO_Prospectus_Draft.json。"
            )
        )

        recover_mock.assert_called_once()
        assert collect_mock.call_count == 2
        assert "<generated_artifacts>" in result["messages"][0].content
        assert "SpaceX_IPO_Prospectus_Draft.json" in result["messages"][0].content

    @patch.object(DeepThinkingAgent, "_build_deep_agent")
    @patch.object(DeepThinkingAgent, "_decide_deep_route")
    def test_deep_agent_node_recovers_python_code_block_artifact(self, mock_route, mock_build_deep):
        """首次未扫描到附件时，应尝试把 Python 代码块恢复为真实产物并重新扫描。"""
        mock_route.return_value = self._route(
            need_sandbox=True,
            need_execute=True,
            need_file_io=True,
            need_artifact_output=True,
            summary="需要沙箱执行",
        )
        mock_deep_agent = MagicMock()
        mock_deep_agent.invoke.return_value = {
            "messages": [
                AIMessage(
                    content=(
                        "```python\n"
                        "filepath = \"SpaceX_IPO_Prospectus_Draft.json\"\n"
                        "content = \"\"\"final prospectus text\"\"\"\n"
                        "with open(filepath, \"w\", encoding=\"utf-8\") as f:\n"
                        "    f.write(content)\n"
                        "```"
                    )
                )
            ],
        }

        backend = MagicMock()
        backend.upload_files.return_value = [
            SimpleNamespace(path="/workspace/artifacts/task-1/SpaceX_IPO_Prospectus_Draft.json", error=None)
        ]
        mock_build_deep.return_value = (mock_deep_agent, backend, "/workspace/artifacts/task-1", True)

        agent = self._build_agent()
        agent.agent_queue_manager.publish = MagicMock()
        collect_mock = MagicMock(side_effect=[
            [],
            [{"name": "SpaceX_IPO_Prospectus_Draft.json", "url": "https://cos.example.com/SpaceX_IPO_Prospectus_Draft.json"}],
        ])
        agent._collect_artifacts = collect_mock

        result = agent._deep_agent_node(
            self._build_state(
                "生成 SpaceX IPO 数据摘要 json 文件，要求输出可下载 .json 附件。"
                "内容包含：封面摘要、业务概览、风险因素、MD&A、募集资金用途、法律声明。"
                "请保存为 SpaceX_IPO_Prospectus_Draft.json。"
            )
        )

        backend.upload_files.assert_called_once()
        uploaded_path, uploaded_content = backend.upload_files.call_args.args[0][0]
        assert uploaded_path.endswith("SpaceX_IPO_Prospectus_Draft.json")
        assert b"final prospectus text" in uploaded_content
        assert collect_mock.call_count == 2
        assert "<generated_artifacts>" in result["messages"][0].content
        assert "SpaceX_IPO_Prospectus_Draft.json" in result["messages"][0].content

    @patch.object(DeepThinkingAgent, "_build_deep_agent")
    @patch.object(DeepThinkingAgent, "_decide_deep_route")
    def test_deep_agent_node_recovers_namespaced_xml_artifact(self, mock_route, mock_build_deep):
        """首次未扫描到附件时，应尝试把带命名空间前缀的 XML 工具调用恢复为真实产物。"""
        mock_route.return_value = self._route(
            need_sandbox=True,
            need_execute=True,
            need_file_io=True,
            need_artifact_output=True,
            summary="需要沙箱执行",
        )
        mock_deep_agent = MagicMock()
        mock_deep_agent.invoke.return_value = {
            "messages": [
                AIMessage(
                    content=(
                        "<vendorx:tool_call>\n"
                        "<invoke name=\"write_file\">\n"
                        "    <parameter name=\"file_name\">SpaceX_IPO_Prospectus_Draft.json</parameter>\n"
                        "    <parameter name=\"content\">final prospectus text</parameter>\n"
                        "</invoke>\n"
                        "</vendorx:tool_call>"
                    )
                )
            ],
        }

        backend = MagicMock()
        backend.upload_files.return_value = [
            SimpleNamespace(path="/workspace/artifacts/task-1/SpaceX_IPO_Prospectus_Draft.json", error=None)
        ]
        mock_build_deep.return_value = (mock_deep_agent, backend, "/workspace/artifacts/task-1", True)

        agent = self._build_agent()
        agent.agent_queue_manager.publish = MagicMock()
        recover_mock = MagicMock(return_value=True)
        collect_mock = MagicMock(side_effect=[
            [],
            [{"name": "SpaceX_IPO_Prospectus_Draft.json", "url": "https://cos.example.com/SpaceX_IPO_Prospectus_Draft.json"}],
        ])
        agent._recover_missing_artifact_from_deep_answer = recover_mock
        agent._collect_artifacts = collect_mock

        result = agent._deep_agent_node(
            self._build_state(
                "生成 SpaceX IPO 数据摘要 json 文件，要求输出可下载 .json 附件。"
                "内容包含：封面摘要、业务概览、风险因素、MD&A、募集资金用途、法律声明。"
                "请保存为 SpaceX_IPO_Prospectus_Draft.json。"
            )
        )

        recover_mock.assert_called_once()
        assert collect_mock.call_count == 2
        assert "<generated_artifacts>" in result["messages"][0].content
        assert "SpaceX_IPO_Prospectus_Draft.json" in result["messages"][0].content

    @patch.object(DeepThinkingAgent, "_build_deep_agent")
    @patch.object(DeepThinkingAgent, "_decide_deep_route")
    def test_deep_agent_node_recovers_generated_artifacts_block(self, mock_route, mock_build_deep):
        """首次未扫描到附件时，应尝试把 generated_artifacts 区块恢复为真实产物。"""
        mock_route.return_value = self._route(
            need_sandbox=True,
            need_execute=True,
            need_file_io=True,
            need_artifact_output=True,
            summary="需要沙箱执行",
        )
        mock_deep_agent = MagicMock()
        mock_deep_agent.invoke.return_value = {
            "messages": [
                AIMessage(
                    content=(
                        "<generated_artifacts>\n"
                        "<artifact id=\"spacex_prospectus\" title=\"SpaceX IPO Prospectus Draft.json\" "
                        "commit_message=\"Generate SpaceX IPO Prospectus Draft in txt format\">\n\n"
                        "SPACE EXPLORATION TECHNOLOGIES CORP.\n"
                        "IPO招股说明书草案\n"
                        "</artifact>\n"
                        "</generated_artifacts>"
                    )
                )
            ],
        }

        backend = MagicMock()
        backend.upload_files.return_value = [
            SimpleNamespace(path="/workspace/artifacts/task-1/SpaceX_IPO_Prospectus_Draft.json", error=None)
        ]
        mock_build_deep.return_value = (mock_deep_agent, backend, "/workspace/artifacts/task-1", True)

        agent = self._build_agent()
        agent.agent_queue_manager.publish = MagicMock()
        collect_mock = MagicMock(side_effect=[
            [],
            [{"name": "SpaceX_IPO_Prospectus_Draft.json", "url": "https://cos.example.com/SpaceX_IPO_Prospectus_Draft.json"}],
        ])
        agent._collect_artifacts = collect_mock

        result = agent._deep_agent_node(
            self._build_state(
                "生成 SpaceX IPO 数据摘要 json 文件，要求输出可下载 .json 附件。"
                "内容包含：封面摘要、业务概览、风险因素、MD&A、募集资金用途、法律声明。"
                "请保存为 SpaceX_IPO_Prospectus_Draft.json。"
            )
        )

        backend.upload_files.assert_called_once()
        uploaded_path, uploaded_content = backend.upload_files.call_args.args[0][0]
        assert uploaded_path.endswith("SpaceX_IPO_Prospectus_Draft.json")
        assert b"SPACE EXPLORATION TECHNOLOGIES CORP." in uploaded_content
        assert collect_mock.call_count == 2
        assert "SpaceX_IPO_Prospectus_Draft.json" in result["messages"][0].content

    def test_recover_missing_artifact_should_publish_warning_then_recovered_success(self):
        """附件恢复成功时，应先给出可恢复 warning，再给出自动修复成功状态。"""
        agent = self._build_agent()
        published = []
        timeline = DeepTimelineMiddleware(task_id=uuid4(), publisher=lambda tid, thought: published.append(thought))
        backend = MagicMock()
        backend.upload_files.return_value = [
            SimpleNamespace(path="/workspace/artifacts/task-1/SpaceX_IPO_Prospectus_Draft.json", error=None)
        ]

        recovered = agent._recover_missing_artifact_from_deep_answer(
            backend=backend,
            artifact_root="/workspace/artifacts/task-1",
            query="请生成 SpaceX IPO 招股说明书 txt 文件，并保存为 SpaceX_IPO_Prospectus_Draft.txt",
            deep_answer=(
                "```python\n"
                "filepath = \"SpaceX_IPO_Prospectus_Draft.txt\"\n"
                "content = \"final prospectus text\"\n"
                "```"
            ),
            timeline=timeline,
        )

        assert recovered is True
        step_events = [
            event
            for event in published
            if event.event == QueueEvent.DEEP_STEP and event.tool == "write_file"
        ]
        assert [event.tool_input["timeline"]["phase"] for event in step_events] == [
            "recovery_attempt",
            "recovery_success",
        ]
        assert step_events[0].tool_input["timeline"]["status"] == "warning"
        assert step_events[0].tool_input["timeline"]["recoverable"] is True
        assert step_events[0].tool_input["timeline"]["error_kind"] == "protocol_error"
        assert step_events[1].tool_input["timeline"]["status"] == "success"
        assert step_events[1].tool_input["timeline"]["recovered"] is True
        assert step_events[1].tool_input["timeline"]["result_preview"] == "已写入 SpaceX_IPO_Prospectus_Draft.txt"

    def test_recover_missing_artifact_should_publish_final_failure_when_upload_fails(self):
        """附件恢复失败时，应明确发布最终失败，而不是伪装成恢复成功。"""
        agent = self._build_agent()
        published = []
        timeline = DeepTimelineMiddleware(task_id=uuid4(), publisher=lambda tid, thought: published.append(thought))
        backend = MagicMock()
        backend.upload_files.return_value = [
            SimpleNamespace(
                path="/workspace/artifacts/task-1/SpaceX_IPO_Prospectus_Draft.txt",
                error="permission denied",
            )
        ]

        recovered = agent._recover_missing_artifact_from_deep_answer(
            backend=backend,
            artifact_root="/workspace/artifacts/task-1",
            query="请生成 SpaceX IPO 招股说明书 txt 文件，并保存为 SpaceX_IPO_Prospectus_Draft.txt",
            deep_answer=(
                "```python\n"
                "filepath = \"SpaceX_IPO_Prospectus_Draft.txt\"\n"
                "content = \"final prospectus text\"\n"
                "```"
            ),
            timeline=timeline,
        )

        assert recovered is False
        step_events = [
            event
            for event in published
            if event.event == QueueEvent.DEEP_STEP and event.tool == "write_file"
        ]
        assert [event.tool_input["timeline"]["phase"] for event in step_events] == [
            "recovery_attempt",
            "final_failure",
        ]
        assert step_events[0].tool_input["timeline"]["status"] == "warning"
        assert step_events[-1].tool_input["timeline"]["status"] == "error"
        assert step_events[-1].tool_input["timeline"]["error_kind"] == "artifact_materialization"
        assert step_events[-1].tool_input["timeline"]["recovered"] is False

    def test_recover_missing_artifact_should_fallback_plain_text_when_tool_call_absent(self):
        """当模型只输出正文时，应基于用户请求推断文件名并保存为可下载 txt。"""
        agent = self._build_agent()
        published = []
        timeline = DeepTimelineMiddleware(task_id=uuid4(), publisher=lambda tid, thought: published.append(thought))
        backend = MagicMock()
        backend.upload_files.return_value = [
            SimpleNamespace(path="/workspace/artifacts/task-1/SpaceX_IPO_Prospectus_Draft.txt", error=None)
        ]

        recovered = agent._recover_missing_artifact_from_deep_answer(
            backend=backend,
            artifact_root="/workspace/artifacts/task-1",
            query="生成 SpaceX IPO 招股说明书 txt 文件，要求输出可下载 .txt 附件。",
            deep_answer=(
                "说明：当前对话环境暂不直接支持自动生成可下载附件，但以下为您提供完整、可直接复制保存的 .txt 文件内容。\n\n"
                "================================================================================\n"
                "SPACE EXPLORATION TECHNOLOGIES CORP.\n"
                "PROSPECTUS DRAFT\n"
                "================================================================================\n\n"
                "PROSPECTUS SUMMARY\n"
                "The Company ...\n\n"
                "RISK FACTORS\n"
                "..."
            ),
            timeline=timeline,
            allow_default_filename=True,
        )

        assert recovered is True
        backend.upload_files.assert_called_once()
        uploaded_path, uploaded_content = backend.upload_files.call_args.args[0][0]
        assert uploaded_path.endswith("SpaceX_IPO_Prospectus_Draft.txt")
        assert "暂不直接支持自动生成可下载附件".encode("utf-8") not in uploaded_content
        assert b"SPACE EXPLORATION TECHNOLOGIES CORP." in uploaded_content
        step_events = [
            event
            for event in published
            if event.event == QueueEvent.DEEP_STEP and event.tool == "write_file"
        ]
        assert [event.tool_input["timeline"]["phase"] for event in step_events] == [
            "plain_text_fallback_attempt",
            "plain_text_fallback_success",
        ]
        assert step_events[0].tool_input["timeline"]["preview_kind"] == "summary"
        assert step_events[0].tool_input["timeline"]["error_kind"] == "plain_text_artifact_fallback"
        assert step_events[1].tool_input["timeline"]["recovered"] is True
        assert step_events[1].tool_input["timeline"]["result_preview"] == "已写入 SpaceX_IPO_Prospectus_Draft.txt"

    @patch.object(DeepThinkingAgent, "_build_deep_agent")
    @patch.object(DeepThinkingAgent, "_decide_deep_route")
    def test_deep_agent_node_should_use_structured_document_pipeline_without_explicit_filename(
        self,
        mock_route,
        mock_build_deep,
    ):
        """用户未写文件名时，结构化文档流水线也应能自动推断默认文件名并生成附件。"""
        mock_route.return_value = self._route(
            need_sandbox=True,
            need_execute=True,
            need_file_io=True,
            need_artifact_output=True,
            summary="需要沙箱执行",
        )

        mock_deep_agent = MagicMock()

        backend = MagicMock()
        final_path = "/workspace/artifacts/task-1/北京旅行规划.md"
        assembled_content = (
            "# 北京旅行规划\n\n"
            "## 行程总览\n"
            "以地铁和步行为主，控制每日节奏。\n\n"
            "## 每日安排\n"
            "Day 1: 故宫与天安门周边。\n\n"
            "## 住宿建议\n"
            "建议住在 2/4/5/8 号线附近。\n\n"
            "## 交通建议\n"
            "优先地铁，必要时短途打车补最后一公里。\n\n"
            "## 预算\n"
            "单人预算控制在 3000 元以内。\n"
        )

        def execute_side_effect(command, timeout=None):
            if command.startswith("mkdir -p "):
                return SimpleNamespace(exit_code=0, output="")
            if command.startswith("cat "):
                assert final_path in command
                return SimpleNamespace(exit_code=0, output="")
            if "find " in command:
                return SimpleNamespace(exit_code=0, output=f"{final_path}\n")
            raise AssertionError(f"unexpected command: {command}")

        backend.execute.side_effect = execute_side_effect
        backend.upload_files.return_value = [
            SimpleNamespace(path=final_path, error=None),
        ]
        backend.download_files.return_value = [
            SimpleNamespace(path=final_path, content=assembled_content.encode("utf-8"), error=None),
        ]
        mock_build_deep.return_value = (mock_deep_agent, backend, "/workspace/artifacts/task-1", True)

        agent = self._build_agent()
        published = []
        agent.agent_queue_manager.publish = lambda tid, thought: published.append(thought)

        outline_llm = MagicMock()
        outline_llm.invoke.return_value = StructuredDocumentOutlinePlan(
            document_title="北京旅行规划",
            sections=[
                StructuredDocumentSectionPlan(
                    title="行程总览",
                    purpose="概述行程结构与节奏。",
                    key_points=["景点数量", "步行强度", "交通方式"],
                    target_length_hint="约 200-300 字",
                ),
                StructuredDocumentSectionPlan(
                    title="每日安排",
                    purpose="按天给出可执行安排。",
                    key_points=["Day 1", "Day 2", "地铁", "步行"],
                    target_length_hint="约 500-800 字",
                ),
                StructuredDocumentSectionPlan(
                    title="住宿建议",
                    purpose="给出稳妥的住宿区域建议。",
                    key_points=["地铁站附近", "少换乘", "长辈友好"],
                    target_length_hint="约 200-300 字",
                ),
                StructuredDocumentSectionPlan(
                    title="交通建议",
                    purpose="说明地铁优先和补充交通方式。",
                    key_points=["地铁", "换乘", "短途打车"],
                    target_length_hint="约 200-300 字",
                ),
                StructuredDocumentSectionPlan(
                    title="预算",
                    purpose="给出总预算和分项预算。",
                    key_points=["住宿", "餐饮", "门票", "交通"],
                    target_length_hint="约 200-300 字",
                ),
            ],
        )
        agent.llm.with_structured_output.return_value = outline_llm
        agent.llm.invoke.side_effect = [
            AIMessage(content="北京旅行规划的总览应体现少折腾与地铁优先。"),
            AIMessage(content="每日安排应保持低强度并给出明确站点。"),
            AIMessage(content="住宿建议应优先地铁枢纽附近。"),
            AIMessage(content="交通建议应优先地铁并说明必要时短途打车。"),
            AIMessage(content="预算应控制在 3000 元以内。"),
        ]

        query = (
            "请输出可下载的 Markdown 附件。内容包含：行程总览、每日安排、住宿建议、交通建议、预算。"
            "我第一次去北京，只有 2 天时间，同行有长辈。请先说明你会怎么权衡景点数量、步行强度和交通方式，"
            "再给出一个保守、少折腾、以地铁和步行为主的 2 天游玩方案。"
        )

        mock_cos_service = MagicMock()
        mock_cos_service.upload_bytes.return_value = SimpleNamespace(
            id=uuid4(),
            name="北京旅行规划.md",
            size=len(assembled_content.encode("utf-8")),
            extension="md",
            mime_type="text/markdown",
            key="artifacts/北京旅行规划.md",
        )
        mock_cos_service.get_file_url.return_value = "https://cos.example.com/artifacts/北京旅行规划.md"
        mock_injector = MagicMock()
        mock_injector.get.return_value = mock_cos_service

        with patch("app.http.module.injector", mock_injector), \
             patch("internal.core.agent.agents.deep_thinking_agent.has_app_context", return_value=False):
            result = agent._deep_agent_node(self._build_state(query))

        mock_deep_agent.invoke.assert_not_called()
        agent.llm.with_structured_output.assert_called_once_with(StructuredDocumentOutlinePlan)
        assert agent.llm.invoke.call_count == 5
        backend.upload_files.assert_called_once()
        uploaded_fragments = backend.upload_files.call_args.args[0]
        assert len(uploaded_fragments) == 6
        assert uploaded_fragments[0][0].endswith("00_front_matter.txt")
        assert all(path.startswith("/tmp/openagent_doc_build/") for path, _ in uploaded_fragments)
        assert all(path.endswith(".txt") for path, _ in uploaded_fragments)
        assert any("行程总览" in path for path, _ in uploaded_fragments)
        assert any("每日安排" in path for path, _ in uploaded_fragments)
        assert any("住宿建议" in path for path, _ in uploaded_fragments)
        assert any("交通建议" in path for path, _ in uploaded_fragments)
        assert any("预算" in path for path, _ in uploaded_fragments)
        uploaded_fragment_content = b"\n".join(content for _, content in uploaded_fragments)
        assert "# 北京旅行规划".encode("utf-8") in uploaded_fragment_content
        assert mock_build_deep.called
        assert any(event.event == QueueEvent.DEEP_ARTIFACT_CREATED for event in published)
        assert mock_cos_service.upload_bytes.call_count == 1
        assert mock_cos_service.upload_bytes.call_args.kwargs["filename"] == "北京旅行规划.md"
        assert mock_cos_service.get_file_url.call_count == 1
        assert "北京旅行规划.md" in result["messages"][0].content

    def test_recover_missing_artifact_should_fallback_plain_text_for_markdown(self):
        """plain-text 兜底也应支持 markdown 等文本类文件。"""
        agent = self._build_agent()
        backend = MagicMock()
        backend.upload_files.return_value = [
            SimpleNamespace(path="/workspace/artifacts/task-1/SpaceX_IPO_Prospectus_Draft.md", error=None)
        ]
        timeline = DeepTimelineMiddleware(task_id=uuid4(), publisher=lambda *_: None)

        recovered = agent._recover_missing_artifact_from_deep_answer(
            backend=backend,
            artifact_root="/workspace/artifacts/task-1",
            query="生成 SpaceX IPO 招股说明书 markdown 文件，请保存为 SpaceX_IPO_Prospectus_Draft.md。",
            deep_answer=(
                "说明：当前对话环境暂不直接支持自动生成可下载附件，但以下为您提供完整内容。\n\n"
                "# SpaceX IPO 招股说明书\n"
                "## 封面摘要\n"
                "SpaceX 是一家私营航天运输与卫星通信公司。\n"
                "## 业务概览\n"
                "Starlink 提供低轨卫星互联网服务。\n"
                "## 风险因素\n"
                "航天发射、监管审批和竞争压力均构成风险。\n"
                "## MD&A\n"
                "管理层持续投入研发和基础设施建设。\n"
                "## 募集资金用途\n"
                "资金将用于星舰、星链及一般公司用途。\n"
                "## 法律声明\n"
                "前瞻性陈述适用法律免责声明。"
            ),
            timeline=timeline,
        )

        assert recovered is True
        uploaded_path, uploaded_content = backend.upload_files.call_args.args[0][0]
        assert uploaded_path.endswith("SpaceX_IPO_Prospectus_Draft.md")
        assert "# SpaceX IPO 招股说明书".encode("utf-8") in uploaded_content

    def test_build_plain_text_artifact_payload_rejects_binary_extensions(self):
        """plain-text 兜底不应把二进制文档后缀误当成可直接 materialize 的文本。"""
        payload = ArtifactPolicy.build_plain_text_artifact_payload(
            "请保存为 report.docx",
            "# title\ncontent",
        )

        assert payload is None

    def test_build_plain_text_artifact_payload_rejects_short_summary(self):
        """短总结不应被误判为可下载正文。"""
        payload = ArtifactPolicy.build_plain_text_artifact_payload(
            "请保存为 SpaceX_IPO_Prospectus_Draft.txt",
            "我将合并所有章节内容并保存为完整的招股说明书文件。",
        )

        assert payload is None

    def test_recover_missing_artifact_should_not_fallback_without_filename(self):
        """没有可推断的文件名时，不应把纯文本误恢复成附件。"""
        agent = self._build_agent()
        backend = MagicMock()
        timeline = DeepTimelineMiddleware(task_id=uuid4(), publisher=lambda *_: None)

        recovered = agent._recover_missing_artifact_from_deep_answer(
            backend=backend,
            artifact_root="/workspace/artifacts/task-1",
            query="请帮我分析一下 SpaceX IPO 的风险。",
            deep_answer="这是一段很长的分析正文，但没有指定文件名。",
            timeline=timeline,
        )

        assert recovered is False
        backend.upload_files.assert_not_called()

    @patch.object(DeepThinkingAgent, "_build_deep_agent")
    @patch.object(DeepThinkingAgent, "_decide_deep_route")
    def test_deep_agent_node_should_fallback_to_plain_text_on_bad_request(
        self,
        mock_route,
        mock_build_deep,
    ):
        """deep agent 遇到 provider 400 时，应降级为纯文本兜底并继续产物恢复。"""
        mock_route.return_value = self._route(
            need_sandbox=True,
            need_execute=True,
            need_file_io=True,
            need_artifact_output=True,
            summary="需要沙箱执行",
        )
        mock_deep_agent = MagicMock()
        mock_deep_agent.invoke.side_effect = Exception(
            "Error code: 400 - {'code': 400, 'msg': 'bad request'}"
        )

        backend = MagicMock()
        backend.upload_files.return_value = [
            SimpleNamespace(path="/workspace/artifacts/task-1/SpaceX_IPO_Prospectus_Draft.txt", error=None)
        ]
        mock_build_deep.return_value = (mock_deep_agent, backend, "/workspace/artifacts/task-1", True)

        agent = self._build_agent()
        agent.agent_queue_manager.publish = MagicMock()
        fallback_llm = MagicMock(spec=BaseLanguageModel)
        fallback_llm.invoke.return_value = AIMessage(
            content=(
                "================================================================================\n"
                "SPACE EXPLORATION TECHNOLOGIES CORP.\n"
                "PROSPECTUS DRAFT\n"
                "================================================================================\n\n"
                "PROSPECTUS SUMMARY\n"
                "The Company ...\n\n"
                "RISK FACTORS\n"
                "..."
            )
        )
        fallback_service = MagicMock()
        fallback_service.load_default_language_model.return_value = fallback_llm
        agent.agent_config.language_model_service = fallback_service

        collect_mock = MagicMock(
            return_value=[
                {
                    "name": "SpaceX_IPO_Prospectus_Draft.json",
                    "url": "https://cos.example.com/SpaceX_IPO_Prospectus_Draft.json",
                }
            ]
        )
        agent._collect_artifacts = collect_mock

        result = agent._deep_agent_node(
            self._build_state(
                "生成 SpaceX IPO 数据摘要 json 文件，要求输出可下载 .json 附件。"
                "内容包含：封面摘要、业务概览、风险因素、MD&A、募集资金用途、法律声明。"
                "请保存为 SpaceX_IPO_Prospectus_Draft.json。"
            )
        )

        mock_deep_agent.invoke.assert_called_once()
        fallback_service.load_default_language_model.assert_called_once()
        fallback_llm.invoke.assert_called_once()
        backend.upload_files.assert_called_once()
        assert collect_mock.call_count == 1
        assert "SpaceX_IPO_Prospectus_Draft.json" in result["messages"][0].content
        assert "https://cos.example.com/SpaceX_IPO_Prospectus_Draft.json" in result["messages"][0].content
        step_events = [
            event
            for event in agent.agent_queue_manager.publish.call_args_list
            if event.args and getattr(event.args[1], "tool", "") == "model_fallback"
        ]
        assert step_events, "应发布模型请求兜底的时间线事件"

    @patch.object(DeepThinkingAgent, "_build_deep_agent")
    @patch.object(DeepThinkingAgent, "_decide_deep_route")
    def test_deep_agent_node_should_fallback_to_plain_text_on_structured_document_bad_request(
        self,
        mock_route,
        mock_build_deep,
    ):
        """结构化文档模式下若 provider 400，应切换到 deepseek-chat 兜底并继续恢复附件。"""
        mock_route.return_value = self._route(
            need_sandbox=True,
            need_execute=True,
            need_file_io=True,
            need_artifact_output=True,
            summary="需要沙箱执行",
        )
        mock_deep_agent = MagicMock()

        backend = MagicMock()
        backend.upload_files.return_value = [
            SimpleNamespace(path="/workspace/artifacts/task-1/SpaceX_IPO_Prospectus_Draft.txt", error=None)
        ]
        mock_build_deep.return_value = (mock_deep_agent, backend, "/workspace/artifacts/task-1", True)

        agent = self._build_agent()
        agent.agent_queue_manager.publish = MagicMock()

        outline_llm = MagicMock()
        outline_llm.invoke.side_effect = Exception(
            "Error code: 400 - {'code': 400, 'msg': 'bad request'}"
        )
        agent.llm.with_structured_output.return_value = outline_llm

        fallback_llm = MagicMock(spec=BaseLanguageModel)
        fallback_llm.invoke.return_value = AIMessage(content=(
            "================================================================================\n"
            "SPACE EXPLORATION TECHNOLOGIES CORP.\n"
            "PROSPECTUS DRAFT\n"
            "================================================================================\n\n"
            "PROSPECTUS SUMMARY\n"
            "The Company ...\n\n"
            "BUSINESS OVERVIEW\n"
            "...\n\n"
            "RISK FACTORS\n"
            "...\n\n"
            "MD&A\n"
            "...\n\n"
            "USE OF PROCEEDS\n"
            "...\n\n"
            "LEGAL MATTERS\n"
            "...\n"
        ))
        fallback_service = MagicMock()
        fallback_service.load_default_language_model.return_value = fallback_llm
        agent.agent_config.language_model_service = fallback_service

        collect_mock = MagicMock(
            return_value=[
                {
                    "name": "SpaceX_IPO_Prospectus_Draft.txt",
                    "url": "https://cos.example.com/artifacts/SpaceX_IPO_Prospectus_Draft.txt",
                }
            ]
        )
        agent._collect_artifacts = collect_mock

        mock_upload_file = SimpleNamespace(
            id=uuid4(),
            name="SpaceX_IPO_Prospectus_Draft.txt",
            size=2048,
            extension="txt",
            mime_type="text/plain",
            key="artifacts/SpaceX_IPO_Prospectus_Draft.txt",
        )
        mock_cos_service = MagicMock()
        mock_cos_service.upload_bytes.return_value = mock_upload_file
        mock_cos_service.get_file_url.return_value = "https://cos.example.com/artifacts/SpaceX_IPO_Prospectus_Draft.txt"
        mock_injector = MagicMock()
        mock_injector.get.return_value = mock_cos_service

        query = (
            "生成 SpaceX IPO 招股说明书 txt 文件，要求输出可下载 .txt 附件。"
            "内容包含：封面摘要、业务概览、风险因素、MD&A、募集资金用途、法律声明。"
        )

        with patch("app.http.module.injector", mock_injector), \
             patch("internal.core.agent.agents.deep_thinking_agent.has_app_context", return_value=False):
            result = agent._deep_agent_node(self._build_state(query))

        mock_deep_agent.invoke.assert_not_called()
        agent.llm.with_structured_output.assert_called_once_with(StructuredDocumentOutlinePlan)
        fallback_service.load_default_language_model.assert_called_once()
        fallback_llm.invoke.assert_called_once()
        backend.upload_files.assert_called_once()
        assert collect_mock.call_count == 1
        assert "SpaceX_IPO_Prospectus_Draft.txt" in result["messages"][0].content
        assert "https://cos.example.com/artifacts/SpaceX_IPO_Prospectus_Draft.txt" in result["messages"][0].content
        step_events = [
            event
            for event in agent.agent_queue_manager.publish.call_args_list
            if event.args and getattr(event.args[1], "tool", "") == "model_fallback"
        ]
        assert step_events, "应发布结构化文档模型请求兜底的时间线事件"

    @patch.object(DeepThinkingAgent, "_build_deep_agent")
    @patch.object(DeepThinkingAgent, "_decide_deep_route")
    def test_deep_agent_node_should_use_structured_document_pipeline_for_text_artifact(
        self,
        mock_route,
        mock_build_deep,
    ):
        """显式 .txt 文档请求应优先走结构化章节流水线，再由沙箱拼接成最终附件。"""
        mock_route.return_value = self._route(
            need_sandbox=True,
            need_execute=True,
            need_file_io=True,
            need_artifact_output=True,
            summary="需要沙箱执行",
        )

        mock_deep_agent = MagicMock()

        backend = MagicMock()
        final_path = "/workspace/artifacts/task-1/SpaceX_IPO_Prospectus_Draft.txt"
        assembled_content = (
            "SPACE EXPLORATION TECHNOLOGIES CORP.\n"
            "PROSPECTUS DRAFT\n\n"
            "PROSPECTUS SUMMARY\n"
            "SpaceX 当前围绕封面摘要展开，重点覆盖公司概况、发行概览、核心业务与投资亮点。\n\n"
            "BUSINESS OVERVIEW\n"
            "SpaceX 当前围绕业务概览展开，重点覆盖星链、猎鹰火箭、星舰与龙飞船。\n\n"
            "RISK FACTORS\n"
            "SpaceX 当前围绕风险因素展开，重点覆盖技术、监管、竞争与财务风险。\n\n"
            "MD&A\n"
            "SpaceX 当前围绕 MD&A 展开，重点覆盖经营成果、流动性和资本资源。\n\n"
            "USE OF PROCEEDS\n"
            "SpaceX 当前围绕募集资金用途展开，重点覆盖星舰、星链和一般公司用途。\n\n"
            "LEGAL MATTERS\n"
            "SpaceX 当前围绕法律声明展开，重点覆盖前瞻性陈述和免责声明。\n"
        )

        def execute_side_effect(command, timeout=None):
            if command.startswith("mkdir -p "):
                return SimpleNamespace(exit_code=0, output="")
            if command.startswith("cat "):
                assert final_path in command
                return SimpleNamespace(exit_code=0, output="")
            if "find " in command:
                return SimpleNamespace(exit_code=0, output=f"{final_path}\n")
            raise AssertionError(f"unexpected command: {command}")

        backend.execute.side_effect = execute_side_effect
        backend.upload_files.return_value = [
            SimpleNamespace(path=final_path, error=None),
        ]
        backend.download_files.return_value = [
            SimpleNamespace(path=final_path, content=assembled_content.encode("utf-8"), error=None),
        ]
        mock_build_deep.return_value = (mock_deep_agent, backend, "/workspace/artifacts/task-1", True)

        agent = self._build_agent()
        published = []
        agent.agent_queue_manager.publish = lambda tid, thought: published.append(thought)

        outline_llm = MagicMock()
        outline_llm.invoke.return_value = StructuredDocumentOutlinePlan(
            document_title="SpaceX IPO Prospectus Draft",
            sections=[
                StructuredDocumentSectionPlan(
                    title="封面摘要 (Prospectus Summary)",
                    purpose="概述公司定位、发行信息和核心投资亮点。",
                    key_points=["公司概况", "发行概览", "核心业务", "投资亮点"],
                    target_length_hint="约 300-500 字",
                ),
                StructuredDocumentSectionPlan(
                    title="业务概览 (Business Overview)",
                    purpose="分业务板块介绍公司商业模式和经营范围。",
                    key_points=["星链", "猎鹰火箭", "星舰", "龙飞船"],
                    target_length_hint="约 600-900 字",
                ),
                StructuredDocumentSectionPlan(
                    title="风险因素 (Risk Factors)",
                    purpose="说明主要经营、监管和市场风险。",
                    key_points=["技术风险", "监管风险", "竞争风险", "财务风险"],
                    target_length_hint="约 600-900 字",
                ),
                StructuredDocumentSectionPlan(
                    title="MD&A",
                    purpose="讨论经营成果、流动性和资本资源。",
                    key_points=["收入来源", "成本结构", "现金流", "资本支出"],
                    target_length_hint="约 500-800 字",
                ),
                StructuredDocumentSectionPlan(
                    title="募集资金用途 (Use of Proceeds)",
                    purpose="说明募集资金的使用方向和优先级。",
                    key_points=["星舰开发", "星链扩展", "研发投入", "一般公司用途"],
                    target_length_hint="约 300-500 字",
                ),
                StructuredDocumentSectionPlan(
                    title="法律声明 (Legal Matters)",
                    purpose="说明法律、前瞻性陈述和免责声明。",
                    key_points=["前瞻性陈述", "合规声明", "法律适用", "免责声明"],
                    target_length_hint="约 300-500 字",
                ),
            ],
        )
        agent.llm.with_structured_output.return_value = outline_llm
        agent.llm.invoke.side_effect = [
            AIMessage(content=(
                (
                    "SpaceX 的封面摘要应突出公司定位、发行信息、核心业务与投资亮点。"
                    "确认不会回退到本地模板。"
                ) * 3
            )),
            AIMessage(content=(
                (
                    "SpaceX 的业务概览应围绕星链、猎鹰火箭、星舰与龙飞船展开。"
                    "确认不会回退到本地模板。"
                ) * 3
            )),
            AIMessage(content=(
                (
                    "SpaceX 的风险因素应覆盖技术、监管、竞争和财务层面的主要风险。"
                    "确认不会回退到本地模板。"
                ) * 3
            )),
            AIMessage(content=(
                (
                    "MD&A 章节应讨论经营成果、流动性、资本资源与未来展望。"
                    "确认不会回退到本地模板。"
                ) * 3
            )),
            AIMessage(content=(
                (
                    "募集资金用途章节应说明星舰开发、星链扩展、研发投入与一般公司用途。"
                    "确认不会回退到本地模板。"
                ) * 3
            )),
            AIMessage(content=(
                (
                    "法律声明章节应覆盖前瞻性陈述、合规说明与免责声明。"
                    "确认不会回退到本地模板。"
                ) * 3
            )),
        ]

        mock_upload_file = SimpleNamespace(
            id=uuid4(),
            name="SpaceX_IPO_Prospectus_Draft.txt",
            size=len(assembled_content.encode("utf-8")),
            extension="txt",
            mime_type="text/plain",
            key="artifacts/SpaceX_IPO_Prospectus_Draft.txt",
        )
        mock_cos_service = MagicMock()
        mock_cos_service.upload_bytes.return_value = mock_upload_file
        mock_cos_service.get_file_url.return_value = "https://cos.example.com/artifacts/SpaceX_IPO_Prospectus_Draft.txt"
        mock_injector = MagicMock()
        mock_injector.get.return_value = mock_cos_service

        query = (
            "生成 SpaceX IPO 招股说明书 txt 文件，要求输出可下载 .txt 附件。"
            "内容包含：封面摘要、业务概览、风险因素、MD&A、募集资金用途、法律声明。"
            "请保存为 SpaceX_IPO_Prospectus_Draft.txt。"
        )

        with patch("app.http.module.injector", mock_injector), \
             patch("internal.core.agent.agents.deep_thinking_agent.has_app_context", return_value=False):
            result = agent._deep_agent_node(self._build_state(query))

        mock_deep_agent.invoke.assert_not_called()
        agent.llm.with_structured_output.assert_called_once_with(StructuredDocumentOutlinePlan)
        assert agent.llm.invoke.call_count == 6
        assert backend.upload_files.call_count == 1
        uploaded_fragment_paths = [path for path, _ in backend.upload_files.call_args.args[0]]
        uploaded_fragment_content = b"\n".join(content for _, content in backend.upload_files.call_args.args[0])
        assert uploaded_fragment_paths[0].endswith("00_front_matter.txt")
        assert any(path.endswith("01_") or "封面摘要" in path for path in uploaded_fragment_paths)
        assert any(path.endswith("02_") or "业务概览" in path for path in uploaded_fragment_paths)
        assert backend.execute.call_count == 3
        assert uploaded_fragment_content.decode("utf-8").count("确认不会回退到本地模板") >= 6
        assert mock_cos_service.upload_bytes.call_count == 1
        uploaded_content = mock_cos_service.upload_bytes.call_args.kwargs["content"].decode("utf-8")
        assert "PROSPECTUS SUMMARY" in uploaded_content
        assert "BUSINESS OVERVIEW" in uploaded_content
        assert "RISK FACTORS" in uploaded_content
        assert "MD&A" in uploaded_content
        assert "USE OF PROCEEDS" in uploaded_content
        assert "LEGAL MATTERS" in uploaded_content
        assert any(event.event == QueueEvent.DEEP_ARTIFACT_CREATED for event in published)

        final_message = result["messages"][0].content
        assert "SpaceX_IPO_Prospectus_Draft.txt" in final_message
        assert "https://cos.example.com/artifacts/SpaceX_IPO_Prospectus_Draft.txt" in final_message

    @patch.object(DeepThinkingAgent, "_build_deep_agent")
    @patch.object(DeepThinkingAgent, "_decide_deep_route")
    def test_deep_agent_node_publishes_timeline_events(self, mock_route, mock_build_deep):
        """_deep_agent_node 应发布 Timeline 事件和完成事件。"""
        mock_route.return_value = self._route()
        mock_deep_agent = MagicMock()
        mock_deep_agent.invoke.return_value = {
            "messages": [AIMessage(content="深度思考后的规划结果")],
        }
        mock_build_deep.return_value = (mock_deep_agent, MagicMock(), "/workspace/artifacts/test", False)

        agent = self._build_agent()
        published = []
        agent.agent_queue_manager.publish = lambda tid, thought: published.append(thought)

        agent._deep_agent_node(self._build_state())

        assert any(event.event == QueueEvent.DEEP_STEP for event in published)
        assert any(event.event == QueueEvent.DEEP_COMPLETE for event in published)

    @patch.object(DeepThinkingAgent, "_build_deep_agent")
    @patch.object(DeepThinkingAgent, "_decide_deep_route")
    def test_deep_agent_node_should_publish_timeout_failure(self, mock_route, mock_build_deep):
        """深度执行异常时应发布 timeout/error 终态，而不是静默继续。"""
        mock_route.return_value = self._route()

        class _FailingDeepAgent:
            def invoke(self, _payload):
                raise TimeoutError("deep timeout")

        mock_build_deep.return_value = (_FailingDeepAgent(), SimpleNamespace(close=lambda: None), "/workspace/artifacts/test", False)

        agent = self._build_agent()
        published = []
        agent.agent_queue_manager.publish = lambda tid, thought: published.append(thought)

        with pytest.raises(TimeoutError, match="deep timeout"):
            agent._deep_agent_node(self._build_state())

        assert any(event.event == QueueEvent.TIMEOUT for event in published)

    @patch.object(DeepThinkingAgent, "_build_deep_agent")
    @patch.object(DeepThinkingAgent, "_decide_deep_route")
    def test_deep_agent_node_graceful_degradation(self, mock_route, mock_build_deep):
        """deepagents 初始化失败时，应优雅降级。"""
        mock_route.return_value = self._route()
        mock_build_deep.side_effect = ImportError("deepagents 未安装")

        agent = self._build_agent()
        published = []
        agent.agent_queue_manager.publish = lambda tid, thought: published.append(thought)

        result = agent._deep_agent_node(self._build_state("test"))

        assert isinstance(result, dict)
        assert result["messages"] == []
        assert any(
            event.event == QueueEvent.DEEP_STEP and "deepagents 未安装" in event.observation
            for event in published
        )

    @patch.object(DeepThinkingAgent, "_build_deep_agent")
    @patch.object(DeepThinkingAgent, "_decide_deep_route")
    def test_deep_agent_node_injects_context_to_messages(self, mock_route, mock_build_deep):
        """_deep_agent_node 应将深度思考摘要注入 messages。"""
        mock_route.return_value = self._route(
            need_sandbox=True,
            need_execute=True,
            summary="需要沙箱执行",
        )
        mock_deep_agent = MagicMock()
        mock_deep_agent.invoke.return_value = {
            "messages": [AIMessage(content="规划：先做A，再做B")],
        }
        mock_build_deep.return_value = (mock_deep_agent, MagicMock(), "/workspace/artifacts/test", True)

        agent = self._build_agent()
        agent.agent_queue_manager.publish = MagicMock()

        result = agent._deep_agent_node(self._build_state("帮我写代码"))

        assert "messages" in result
        msgs = result["messages"]
        assert any(isinstance(message, AIMessage) for message in msgs)
        assert "<deep_execution_summary>" in msgs[0].content
        assert "<deep_thinking_result>" in msgs[0].content

    @patch.object(DeepThinkingAgent, "_build_deep_agent")
    def test_deep_agent_node_should_publish_deep_usage_totals(self, mock_build_deep):
        llm = _make_llm()

        structured_llm = MagicMock()
        structured_llm.invoke.return_value = self._route()
        llm.with_structured_output.return_value = structured_llm

        tool_llm = MagicMock()
        tool_llm.invoke.return_value = "工具调用完成"
        object.__setattr__(llm, "bind_tools", MagicMock(return_value=tool_llm))

        agent = DeepThinkingAgent(llm=llm, agent_config=_make_agent_config(enable_deep_thinking=True))
        published = []
        agent.agent_queue_manager.publish = lambda tid, thought: published.append(thought)

        class _DeepAgent:
            def invoke(self, _payload):
                llm.bind_tools(["weather"]).invoke("查询上海天气")
                return {
                    "messages": [AIMessage(content="深度思考后的规划结果")],
                }

        mock_build_deep.return_value = (_DeepAgent(), MagicMock(), "/workspace/artifacts/test", False)

        agent._deep_agent_node(self._build_state("请生成上海旅行规划"))

        complete_event = next(
            event for event in published if event.event == QueueEvent.DEEP_COMPLETE
        )
        assert complete_event.total_token_count > 0
        assert complete_event.total_price > 0

    def test_build_deep_agent_uses_sandbox_when_env_set(self):
        """配置完整且路由要求沙箱时，应构建 BaiduCfcSandboxBackend。"""
        captured = {}
        agent = self._build_agent()
        timeline = DeepTimelineMiddleware(task_id=uuid4(), publisher=lambda *_: None)
        task_id = uuid4()
        route = self._route(
            need_sandbox=True,
            need_execute=True,
            summary="需要沙箱执行",
        )

        def capture_create_deep_agent(*args, **kwargs):
            captured["backend"] = kwargs.get("backend")
            captured["middleware"] = kwargs.get("middleware")
            return MagicMock()

        with patch("deepagents.create_deep_agent", side_effect=capture_create_deep_agent), \
             patch.object(BaiduCfcSandboxBackend, "ensure_ready", return_value=None), \
             patch.object(
                 BaiduCfcSandboxBackend,
                 "execute",
                 return_value=SimpleNamespace(exit_code=0, output=f"/home/user/artifacts/{task_id}"),
             ), \
             patch.dict(os.environ, {
                "E2B_API_KEY": "test-key",
                "E2B_DOMAIN": "sandbox.example.com",
             }, clear=False):
            _, backend, artifact_root, used_sandbox = agent._build_deep_agent(
                task_id=task_id,
                route_decision=route,
                timeline=timeline,
            )

        assert isinstance(backend, BaiduCfcSandboxBackend)
        assert used_sandbox is True
        assert artifact_root == f"/home/user/artifacts/{task_id}"
        assert isinstance(captured["middleware"][0], DeepTimelineMiddleware)

    def test_build_deep_agent_unwraps_runtime_fallback_proxy_before_deepagents(self):
        """deepagents 只接受真正的 chat model；运行时 fallback 代理需先解包。"""
        base_model = OpenAIChat(model="gpt-4o-mini", api_key="test-key")
        proxy = RuntimeFallbackLanguageModelProxy.from_model(
            base_model,
            fallback_loader=lambda: base_model,
            requested_model_config={"provider": "openai", "model": "gpt-4o-mini"},
            runtime_fallback_enabled=True,
        )

        captured = {}
        agent = DeepThinkingAgent(llm=proxy, agent_config=_make_agent_config(enable_deep_thinking=True))
        timeline = DeepTimelineMiddleware(task_id=uuid4(), publisher=lambda *_: None)
        route = self._route(
            need_sandbox=True,
            need_execute=True,
            summary="需要沙箱执行",
        )

        def capture_create_deep_agent(*args, **kwargs):
            captured["model"] = kwargs.get("model")
            return MagicMock()

        with patch("deepagents.create_deep_agent", side_effect=capture_create_deep_agent), \
             patch.object(BaiduCfcSandboxBackend, "execute", return_value=SimpleNamespace(exit_code=0, output="/home/user/artifacts/test-task")), \
             patch.dict(os.environ, {
                "E2B_API_KEY": "test-key",
                "E2B_DOMAIN": "sandbox.example.com",
                "SANDBOX_TEMPLATE_ALIAS": "",
                "SANDBOX_FALLBACK_TEMPLATE_ALIAS": "",
             }, clear=False):
            agent._build_deep_agent(
                task_id=uuid4(),
                route_decision=route,
                timeline=timeline,
            )

        assert captured["model"] is getattr(proxy, "_primary_model")
        assert isinstance(captured["model"], type(base_model))
        assert captured["model"] is not proxy

    def test_build_deep_agent_fallback_to_state_backend(self):
        """未请求沙箱时，应使用 StateBackend。"""
        captured = {}
        agent = self._build_agent()
        timeline = DeepTimelineMiddleware(task_id=uuid4(), publisher=lambda *_: None)
        route = self._route()

        def capture_create_deep_agent(*args, **kwargs):
            captured["backend"] = kwargs.get("backend")
            return MagicMock()

        with patch("deepagents.create_deep_agent", side_effect=capture_create_deep_agent), \
             patch.dict(os.environ, {}, clear=True):
            _, backend, _, used_sandbox = agent._build_deep_agent(
                task_id=uuid4(),
                route_decision=route,
                timeline=timeline,
            )

        assert type(backend).__name__ == "StateBackend"
        assert type(captured["backend"]).__name__ == "StateBackend"
        assert used_sandbox is False

    def test_build_deep_agent_uses_template_config_from_env(self):
        """SANDBOX_* 环境变量应正确映射到沙箱模板配置。"""
        captured_backend = {}
        agent = self._build_agent()
        timeline = DeepTimelineMiddleware(task_id=uuid4(), publisher=lambda *_: None)
        task_id = uuid4()
        route = self._route(
            need_sandbox=True,
            need_execute=True,
            summary="需要沙箱执行",
        )

        def capture_create_deep_agent(*args, **kwargs):
            captured_backend["backend"] = kwargs.get("backend")
            return MagicMock()

        with patch("deepagents.create_deep_agent", side_effect=capture_create_deep_agent), \
             patch.object(BaiduCfcSandboxBackend, "ensure_ready", return_value=None) as ensure_ready_mock, \
             patch.object(
                 BaiduCfcSandboxBackend,
                 "execute",
                 return_value=SimpleNamespace(exit_code=0, output=f"/home/user/artifacts/{task_id}"),
             ), \
             patch.dict(os.environ, {
                "E2B_API_KEY": "test-key",
                "E2B_DOMAIN": "sandbox.example.com",
                "SANDBOX_TEMPLATE_ALIAS": "lite-template",
                "SANDBOX_FALLBACK_TEMPLATE_ALIAS": "fallback-template",
                "SANDBOX_TIMEOUT_SECONDS": "1801",
                "SANDBOX_EXECUTE_TIMEOUT_SECONDS": "601",
             }, clear=False):
            _, backend, artifact_root, used_sandbox = agent._build_deep_agent(
                task_id=task_id,
                route_decision=route,
                timeline=timeline,
            )

        assert isinstance(backend, BaiduCfcSandboxBackend)
        assert backend._template_alias == "lite-template"
        assert backend._fallback_template_alias == "fallback-template"
        assert backend._sandbox_timeout == 1801
        assert backend._timeout == 601
        assert used_sandbox is True
        assert artifact_root == f"/home/user/artifacts/{task_id}"
        ensure_ready_mock.assert_called_once()
        assert captured_backend["backend"] is backend

    def test_build_deep_agent_clamps_timeout_env_values_to_minimums(self):
        """较低的 SANDBOX_* 环境变量应被抬升到安全下限。"""
        captured_backend = {}
        agent = self._build_agent()
        timeline = DeepTimelineMiddleware(task_id=uuid4(), publisher=lambda *_: None)
        task_id = uuid4()
        route = self._route(
            need_sandbox=True,
            need_execute=True,
            summary="需要沙箱执行",
        )

        def capture_create_deep_agent(*args, **kwargs):
            captured_backend["backend"] = kwargs.get("backend")
            return MagicMock()

        with patch("deepagents.create_deep_agent", side_effect=capture_create_deep_agent), \
             patch.object(BaiduCfcSandboxBackend, "ensure_ready", return_value=None), \
             patch.object(
                 BaiduCfcSandboxBackend,
                 "execute",
                 return_value=SimpleNamespace(exit_code=0, output=f"/home/user/artifacts/{task_id}"),
             ), \
             patch.dict(os.environ, {
                "E2B_API_KEY": "test-key",
                "E2B_DOMAIN": "sandbox.example.com",
                "SANDBOX_TIMEOUT_SECONDS": "123",
                "SANDBOX_EXECUTE_TIMEOUT_SECONDS": "45",
             }, clear=False):
            _, backend, artifact_root, used_sandbox = agent._build_deep_agent(
                task_id=task_id,
                route_decision=route,
                timeline=timeline,
            )

        assert isinstance(backend, BaiduCfcSandboxBackend)
        assert backend._sandbox_timeout == 1800
        assert backend._timeout == 600
        assert used_sandbox is True
        assert artifact_root == f"/home/user/artifacts/{task_id}"
        assert captured_backend["backend"] is backend

    def test_build_deep_agent_falls_back_to_state_backend_when_sandbox_validation_fails(self):
        """模板验证失败时，应自动回退到 StateBackend。"""
        agent = self._build_agent()
        timeline = DeepTimelineMiddleware(task_id=uuid4(), publisher=lambda *_: None)
        route = self._route(
            need_sandbox=True,
            need_execute=True,
            summary="需要沙箱执行",
        )

        with patch("deepagents.create_deep_agent", return_value=MagicMock()), \
             patch.object(BaiduCfcSandboxBackend, "ensure_ready", side_effect=RuntimeError("template invalid")), \
             patch.dict(os.environ, {
                "E2B_API_KEY": "test-key",
                "E2B_DOMAIN": "sandbox.example.com",
                "SANDBOX_TEMPLATE_ALIAS": "lite-template",
             }, clear=False):
            _, backend, _, used_sandbox = agent._build_deep_agent(
                task_id=uuid4(),
                route_decision=route,
                timeline=timeline,
            )

        assert type(backend).__name__ == "StateBackend"
        assert used_sandbox is False

    def test_collect_artifacts_uploads_to_cos_and_publishes_events(self):
        """沙箱生成的附件应被下载、上传 COS，并发布 artifact 事件。"""
        agent = self._build_agent()
        published = []
        timeline = DeepTimelineMiddleware(task_id=uuid4(), publisher=lambda tid, thought: published.append(thought))

        backend = MagicMock()
        backend.execute.return_value = SimpleNamespace(
            exit_code=0,
            output="/workspace/artifacts/task-1/plan.txt\n",
        )
        backend.download_files.return_value = [
            SimpleNamespace(path="/workspace/artifacts/task-1/plan.txt", content=b"hello", error=None)
        ]

        mock_upload_file = SimpleNamespace(
            id=uuid4(),
            name="plan.txt",
            size=5,
            extension="txt",
            mime_type="text/plain",
            key="artifacts/plan.txt",
        )
        mock_cos_service = MagicMock()
        mock_cos_service.upload_bytes.return_value = mock_upload_file
        mock_cos_service.get_file_url.return_value = "https://cos.example.com/artifacts/plan.txt"
        mock_injector = MagicMock()
        mock_injector.get.return_value = mock_cos_service

        with patch("app.http.module.injector", mock_injector):
            artifacts = agent._collect_artifacts(
                backend=backend,
                artifact_root="/workspace/artifacts/task-1",
                timeline=timeline,
            )

        assert len(artifacts) == 1
        assert artifacts[0]["name"] == "plan.txt"
        assert any(event.event == QueueEvent.DEEP_ARTIFACT_CREATED for event in published)

    def test_collect_artifacts_scans_home_user_fallback_root(self):
        """当 /workspace 不可写时，应能从 /home/user/artifacts 中发现产物。"""
        agent = self._build_agent()
        published = []
        timeline = DeepTimelineMiddleware(task_id=uuid4(), publisher=lambda tid, thought: published.append(thought))

        backend = MagicMock()
        backend.execute.return_value = SimpleNamespace(
            exit_code=0,
            output="/home/user/artifacts/task-1/plan.txt\n",
        )
        backend.download_files.return_value = [
            SimpleNamespace(path="/home/user/artifacts/task-1/plan.txt", content=b"hello", error=None)
        ]

        mock_upload_file = SimpleNamespace(
            id=uuid4(),
            name="plan.txt",
            size=5,
            extension="txt",
            mime_type="text/plain",
            key="artifacts/plan.txt",
        )
        mock_cos_service = MagicMock()
        mock_cos_service.upload_bytes.return_value = mock_upload_file
        mock_cos_service.get_file_url.return_value = "https://cos.example.com/artifacts/plan.txt"
        mock_injector = MagicMock()
        mock_injector.get.return_value = mock_cos_service

        with patch("app.http.module.injector", mock_injector):
            artifacts = agent._collect_artifacts(
                backend=backend,
                artifact_root="/workspace/artifacts/task-1",
                timeline=timeline,
            )

        assert len(artifacts) == 1
        assert artifacts[0]["path"] == "/home/user/artifacts/task-1/plan.txt"
        scan_command = backend.execute.call_args.args[0]
        assert "/workspace/artifacts/task-1" in scan_command
        assert "/home/user/artifacts/task-1" in scan_command
        assert any(event.event == QueueEvent.DEEP_ARTIFACT_CREATED for event in published)

    def test_collect_artifacts_enters_flask_app_context_when_needed(self):
        """产物持久化在线程内无 app context 时，应显式进入 runtime_flask_app.app_context()。"""
        runtime_flask_app = MagicMock()
        runtime_flask_app.app_context.return_value = nullcontext()
        agent = self._build_agent()
        agent.agent_config.runtime_flask_app = runtime_flask_app
        published = []
        timeline = DeepTimelineMiddleware(task_id=uuid4(), publisher=lambda tid, thought: published.append(thought))

        backend = MagicMock()
        backend.execute.return_value = SimpleNamespace(
            exit_code=0,
            output="/home/user/artifacts/task-1/plan.txt\n",
        )
        backend.download_files.return_value = [
            SimpleNamespace(path="/home/user/artifacts/task-1/plan.txt", content=b"hello", error=None)
        ]

        mock_upload_file = SimpleNamespace(
            id=uuid4(),
            name="plan.txt",
            size=5,
            extension="txt",
            mime_type="text/plain",
            key="artifacts/plan.txt",
        )
        mock_cos_service = MagicMock()
        mock_cos_service.upload_bytes.return_value = mock_upload_file
        mock_cos_service.get_file_url.return_value = "https://cos.example.com/artifacts/plan.txt"
        mock_injector = MagicMock()
        mock_injector.get.return_value = mock_cos_service

        with patch("app.http.module.injector", mock_injector), \
             patch("internal.core.agent.agents.deep_thinking_agent.has_app_context", return_value=False):
            artifacts = agent._collect_artifacts(
                backend=backend,
                artifact_root="/workspace/artifacts/task-1",
                timeline=timeline,
            )

        assert len(artifacts) == 1
        runtime_flask_app.app_context.assert_called_once()
        assert any(event.event == QueueEvent.DEEP_ARTIFACT_CREATED for event in published)

    def test_collect_artifacts_scans_top_level_artifact_root_when_task_folder_is_empty(self):
        """当产物误写到 /home/user/artifacts 顶层时，应通过 marker 兜底扫描发现文件。"""
        agent = self._build_agent()
        published = []
        timeline = DeepTimelineMiddleware(task_id=uuid4(), publisher=lambda tid, thought: published.append(thought))

        backend = MagicMock()
        backend._openagent_artifact_markers = [
            "/home/user/artifacts/.openagent_artifact_marker_task-1",
        ]
        backend.execute.side_effect = [
            SimpleNamespace(exit_code=0, output=""),
            SimpleNamespace(exit_code=0, output="/home/user/artifacts/shanghai_travel_outfits.svg\n"),
        ]
        backend.download_files.return_value = [
            SimpleNamespace(
                path="/home/user/artifacts/shanghai_travel_outfits.svg",
                content=b"<svg></svg>",
                error=None,
            )
        ]

        mock_upload_file = SimpleNamespace(
            id=uuid4(),
            name="shanghai_travel_outfits.svg",
            size=11,
            extension="svg",
            mime_type="image/svg+xml",
            key="artifacts/shanghai_travel_outfits.svg",
        )
        mock_cos_service = MagicMock()
        mock_cos_service.upload_bytes.return_value = mock_upload_file
        mock_cos_service.get_file_url.return_value = "https://cos.example.com/artifacts/shanghai_travel_outfits.svg"
        mock_injector = MagicMock()
        mock_injector.get.return_value = mock_cos_service

        with patch("app.http.module.injector", mock_injector):
            artifacts = agent._collect_artifacts(
                backend=backend,
                artifact_root="/workspace/artifacts/task-1",
                timeline=timeline,
            )

        assert len(artifacts) == 1
        assert artifacts[0]["path"] == "/home/user/artifacts/shanghai_travel_outfits.svg"
        assert backend.execute.call_count == 2
        fallback_scan_command = backend.execute.call_args_list[1].args[0]
        assert "/home/user/artifacts" in fallback_scan_command
        assert "-maxdepth 1" in fallback_scan_command
        assert ".openagent_artifact_marker_task-1" in fallback_scan_command
        assert any(event.event == QueueEvent.DEEP_ARTIFACT_CREATED for event in published)

    def test_collect_artifacts_scans_mnt_data_top_level_when_model_uses_code_interpreter_path(self):
        """当模型把文件写到 /mnt/data 顶层时，应通过 marker 兜底扫描发现文件。"""
        agent = self._build_agent()
        published = []
        timeline = DeepTimelineMiddleware(task_id=uuid4(), publisher=lambda tid, thought: published.append(thought))

        backend = MagicMock()
        backend._openagent_artifact_markers = [
            "/mnt/data/.openagent_artifact_marker_task-1",
        ]
        backend.execute.side_effect = [
            SimpleNamespace(exit_code=0, output=""),
            SimpleNamespace(exit_code=0, output="/mnt/data/SpaceX_IPO_Prospectus_Draft.md\n"),
        ]
        backend.download_files.return_value = [
            SimpleNamespace(
                path="/mnt/data/SpaceX_IPO_Prospectus_Draft.md",
                content=b"# SpaceX IPO\n",
                error=None,
            )
        ]

        mock_upload_file = SimpleNamespace(
            id=uuid4(),
            name="SpaceX_IPO_Prospectus_Draft.md",
            size=13,
            extension="md",
            mime_type="text/markdown",
            key="artifacts/SpaceX_IPO_Prospectus_Draft.md",
        )
        mock_cos_service = MagicMock()
        mock_cos_service.upload_bytes.return_value = mock_upload_file
        mock_cos_service.get_file_url.return_value = "https://cos.example.com/artifacts/SpaceX_IPO_Prospectus_Draft.md"
        mock_injector = MagicMock()
        mock_injector.get.return_value = mock_cos_service

        with patch("app.http.module.injector", mock_injector):
            artifacts = agent._collect_artifacts(
                backend=backend,
                artifact_root="/workspace/artifacts/task-1",
                timeline=timeline,
            )

        assert len(artifacts) == 1
        assert artifacts[0]["path"] == "/mnt/data/SpaceX_IPO_Prospectus_Draft.md"
        fallback_scan_command = backend.execute.call_args_list[1].args[0]
        assert "/mnt/data" in fallback_scan_command
        assert "-maxdepth 1" in fallback_scan_command
        assert ".openagent_artifact_marker_task-1" in fallback_scan_command
        assert any(event.event == QueueEvent.DEEP_ARTIFACT_CREATED for event in published)

    def test_sanitize_deep_answer_removes_fake_download_link_and_local_path(self):
        """应清理 deepagents 回答中的伪下载链接和沙箱本地路径。"""
        answer = """📄 可下载文件
📥 [点击下载：计划.txt]（需在沙箱中查看）
文件路径：/home/user/artifacts/task-1/计划.txt
这里是正文摘要。"""

        sanitized = DeepThinkingAgent._sanitize_deep_answer(
            answer,
            artifacts=[{"name": "计划.txt", "url": "https://cos.example.com/plan.txt"}],
        )

        assert "点击下载" not in sanitized
        assert "/home/user/artifacts/" not in sanitized
        assert "这里是正文摘要" in sanitized
        assert "generated_artifacts" not in sanitized

    def test_sanitize_deep_answer_removes_sandbox_uri_links(self):
        """应清理 sandbox:/mnt/data 伪下载链接，避免前端出现不可用链接。"""
        answer = """下载地址：sandbox:/mnt/data/shanghai_travel_outfits.svg
请点击下载。"""

        sanitized = DeepThinkingAgent._sanitize_deep_answer(answer, artifacts=[])

        assert "sandbox:/mnt/data/" not in sanitized

    def test_sanitize_deep_answer_removes_raw_mnt_data_links(self):
        """应清理 /mnt/data 本地路径，避免前端出现不可用链接。"""
        answer = "文件已保存到 /mnt/data/SpaceX_IPO_Prospectus_Draft.md"

        sanitized = DeepThinkingAgent._sanitize_deep_answer(answer, artifacts=[])

        assert "/mnt/data/" not in sanitized

    def test_sanitize_deep_answer_removes_namespaced_tool_call_tags(self):
        """应清理带命名空间前缀的原始工具调用标签，避免暴露模型原文。"""
        answer = """<vendorx:tool_call>
<invoke name="write_file">
    <parameter name="file_name">SpaceX_IPO_Prospectus_Draft.txt</parameter>
    <parameter name="content">hello world</parameter>
</invoke>
</vendorx:tool_call>"""

        sanitized = DeepThinkingAgent._sanitize_deep_answer(answer, artifacts=[])

        assert "<vendorx:tool_call>" not in sanitized
        assert "<invoke name=\"write_file\">" not in sanitized
        assert "<parameter name=\"file_name\">" not in sanitized

    def test_sanitize_deep_answer_removes_generated_artifacts_block(self):
        """应清理 generated_artifacts 区块，避免把内部 artifact 协议暴露给用户。"""
        answer = """<generated_artifacts>
<artifact id="spacex_prospectus" title="SpaceX IPO Prospectus Draft">
SPACE EXPLORATION TECHNOLOGIES CORP.
</artifact>
</generated_artifacts>
正文摘要。"""

        sanitized = DeepThinkingAgent._sanitize_deep_answer(answer, artifacts=[])

        assert "<generated_artifacts>" not in sanitized
        assert "<artifact id=" not in sanitized
        assert "正文摘要。" in sanitized


# ============================================================
#  Integration Tests（需要真实百度 CFC 沙箱）
# ============================================================

@pytest.mark.integration
class TestBaiduCfcSandboxIntegration:
    """集成测试：需要真实的百度 CFC 沙箱环境。

    运行前确保 .env 中配置了：
        E2B_API_KEY=bce-v3/ALTAK-...
        E2B_DOMAIN=sandbox-execute.bj.baidubce.com
    """

    @pytest.fixture(scope="class")
    def sandbox(self):
        """创建真实沙箱实例，测试完成后关闭。"""
        pytest.importorskip("e2b_code_interpreter", reason="e2b-code-interpreter 未安装，跳过真实沙箱集成测试")
        api_key = os.environ.get("E2B_API_KEY", "")
        domain  = os.environ.get("E2B_DOMAIN",  "")
        if not api_key or not domain:
            pytest.skip("E2B_API_KEY 或 E2B_DOMAIN 未配置，跳过集成测试")

        backend = BaiduCfcSandboxBackend(api_key=api_key, domain=domain)
        yield backend
        backend.close()

    def test_execute_python_code(self, sandbox):
        """真实沙箱：执行 Python 代码并验证输出。"""
        result = sandbox.execute("python3 -c 'print(1 + 2 + 3)'")
        assert result.exit_code == 0
        assert "6" in result.output

    def test_execute_shell_command(self, sandbox):
        """真实沙箱：执行 Shell 命令。"""
        result = sandbox.execute("echo 'hello from baidu cfc sandbox'")
        assert result.exit_code == 0
        assert "hello from baidu cfc sandbox" in result.output

    def test_execute_multiline_python(self, sandbox):
        """真实沙箱：执行多行 Python 脚本。"""
        script = "python3 -c \"\nimport math\nresult = math.sqrt(144)\nprint(f'sqrt(144)={result}')\n\""
        result = sandbox.execute(script)
        assert result.exit_code == 0
        assert "12.0" in result.output

    def test_file_upload_and_download(self, sandbox):
        """真实沙箱：上传文件后能下载回来内容一致。"""
        content = b"# hello from unit test\nprint('hi')\n"
        path    = "/tmp/test_upload.py"

        upload_resp = sandbox.upload_files([(path, content)])
        assert upload_resp[0].error is None

        download_resp = sandbox.download_files([path])
        assert download_resp[0].content == content

    def test_execute_uploaded_file(self, sandbox):
        """真实沙箱：上传 Python 文件后能执行。"""
        code = b"result = 2 ** 10\nprint(f'2^10={result}')\n"
        path = "/tmp/test_exec.py"

        sandbox.upload_files([(path, code)])
        result = sandbox.execute(f"python3 {path}")

        assert result.exit_code == 0
        assert "1024" in result.output

    def test_sandbox_id_is_string(self, sandbox):
        """真实沙箱：sandbox_id 应为非空字符串。"""
        assert isinstance(sandbox.id, str)
        assert len(sandbox.id) > 0
