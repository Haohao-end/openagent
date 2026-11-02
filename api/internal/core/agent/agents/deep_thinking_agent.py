"""DeepThinkingAgent — 深度思考智能体。"""
from __future__ import annotations

from contextlib import nullcontext
import logging
import mimetypes
import os
import re
import shlex
import time
import uuid
import textwrap
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field
from flask import has_app_context

from internal.core.agent.agents.base_agent import AgentStreamCancelled
from internal.core.agent.agents.function_call_agent import FunctionCallAgent
from internal.core.agent.entities.artifact_policy_entity import ArtifactPolicy
from internal.core.agent.entities.agent_entity import (
    DEEP_THINKING_SYSTEM_PROMPT,
    AgentState,
)
from internal.core.agent.entities.sandbox_policy_entity import SandboxPolicy
from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.core.agent.middleware import DeepTimelineMiddleware
from internal.core.agent.usage_utils import track_language_model_usage

logger = logging.getLogger(__name__)


def _read_positive_int_env(env_name: str, default: int, *, minimum: int | None = None) -> int:
    raw_value = (os.getenv(env_name) or "").strip()
    if not raw_value:
        return default

    try:
        parsed_value = int(raw_value)
    except ValueError:
        logger.warning("%s=%r 无法解析为整数，使用默认值 %s", env_name, raw_value, default)
        return default

    if parsed_value <= 0:
        logger.warning("%s=%r 必须大于 0，使用默认值 %s", env_name, raw_value, default)
        return default

    if minimum is not None and parsed_value < minimum:
        logger.warning("%s=%r 小于最小值 %s，使用最小值 %s", env_name, raw_value, minimum, minimum)
        return minimum

    return parsed_value


class DeepRouteDecision(BaseModel):
    """深度思考阶段的运行时能力判断结果。"""

    need_sandbox: bool = False
    need_file_io: bool = False
    need_execute: bool = False
    need_subagent: bool = False
    need_artifact_output: bool = False
    reason: str = ""
    summary: str = ""


class StructuredDocumentSectionPlan(BaseModel):
    """结构化文档章节规划。"""

    title: str = Field(description="章节标题")
    purpose: str = Field(default="", description="章节写作目的")
    key_points: list[str] = Field(default_factory=list, description="章节需要覆盖的关键点")
    target_length_hint: str = Field(default="", description="章节长度提示")


class StructuredDocumentOutlinePlan(BaseModel):
    """结构化文档大纲。"""

    document_title: str = Field(default="", description="文档标题")
    sections: list[StructuredDocumentSectionPlan] = Field(default_factory=list, description="文档章节列表")


class DeepThinkingAgent(FunctionCallAgent):
    """深度思考智能体：先判断能力，再按需使用沙箱和 deepagents。"""

    name: str = "deep_thinking_agent"

    def _build_agent(self) -> CompiledStateGraph:
        graph = StateGraph(AgentState)
        graph.add_node("preset_operation", self._preset_operation_node)
        graph.add_node("long_term_memory_recall", self._long_term_memory_recall_node)
        graph.add_node("deep_agent", self._deep_agent_node)
        graph.add_node("llm", self._llm_node)
        graph.add_node("tools", self._tools_node)

        graph.set_entry_point("preset_operation")
        graph.add_conditional_edges("preset_operation", self._preset_operation_condition)
        graph.add_edge("long_term_memory_recall", "deep_agent")
        graph.add_edge("deep_agent", "llm")
        graph.add_conditional_edges("llm", self._tools_condition)
        graph.add_edge("tools", "llm")
        return graph.compile()

    def _llm_node(self, state: AgentState) -> AgentState:
        """深度执行后的最终回答阶段只做整理，不再绑定普通工具。"""
        messages = state.get("messages") or []
        last_message = messages[-1] if messages else None
        last_content = self._extract_query(last_message) if last_message is not None else ""
        if "<deep_execution_summary>" not in last_content:
            return super()._llm_node(state)

        original_tools = self.agent_config.tools
        self.agent_config.tools = []
        try:
            return super()._llm_node(state)
        finally:
            self.agent_config.tools = original_tools

    def _finalize_llm_output(self, state: AgentState, content: str) -> str:
        """深度执行最终输出的额外收口：没有真实附件时不允许保留下载暗示。"""
        finalized = super()._finalize_llm_output(state, content)
        messages = state.get("messages") or []
        last_message = messages[-1] if messages else None
        last_content = self._extract_query(last_message) if last_message is not None else ""
        if "<deep_execution_summary>" not in last_content:
            return finalized
        if "<generated_artifacts>" in last_content:
            return finalized

        sanitized_lines: list[str] = []
        for raw_line in finalized.splitlines():
            line = raw_line.strip()
            if not line:
                sanitized_lines.append(raw_line)
                continue

            if any(
                keyword in line
                for keyword in (
                    "点击下载",
                    "下载链接",
                    "可下载文件",
                    "下载附件",
                    "附件下载",
                    "附件",
                    "sandbox:/mnt/data/",
                    "/mnt/data/",
                )
            ):
                continue

            sanitized_lines.append(raw_line)

        sanitized = self._sanitize_sandbox_artifact_text("\n".join(sanitized_lines).strip())
        if sanitized and "当前没有可下载附件" not in sanitized and "未生成可下载产物" not in sanitized:
            sanitized += "\n\n当前没有可下载附件。"
        return sanitized or "当前没有可下载附件。"

    @classmethod
    def _extract_tagged_block_content(cls, text: str, tag_name: str) -> str:
        if not text or not tag_name:
            return ""

        pattern = re.compile(
            rf"(?is)<{re.escape(tag_name)}>\s*(?P<body>.*?)\s*</{re.escape(tag_name)}\s*>",
            re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(str(text))
        if not match:
            return ""

        return textwrap.dedent(str(match.group("body") or "")).strip()

    @classmethod
    def _score_plain_text_artifact_content(cls, text: str) -> tuple[int, int, int, int]:
        normalized = str(text or "").strip()
        if not normalized:
            return (0, 0, 0, 0)

        lines = [line.strip() for line in normalized.splitlines() if line.strip()]
        markers = (
            "PROSPECTUS",
            "招股说明书",
            "PROSPECTUS SUMMARY",
            "RISK FACTORS",
            "BUSINESS",
            "MD&A",
            "USE OF PROCEEDS",
            "LEGAL",
            "第一章",
            "第二章",
            "第三章",
            "封面摘要",
            "业务概览",
            "风险因素",
            "募集资金用途",
            "法律声明",
        )
        upper_text = normalized.upper()
        section_hits = sum(1 for marker in markers if marker.upper() in upper_text)
        heading_hits = sum(
            1
            for line in lines
            if (
                line.startswith("#")
                or re.match(r"^\d+(?:\.\d+)*\s+", line)
                or re.match(r"^[一二三四五六七八九十]+[、\.]", line)
            )
        )
        return (section_hits, heading_hits, len(lines), len(normalized))

    def _postprocess_llm_output(self, state: AgentState, content: str) -> str:
        """在最终回答发布前，尝试把纯文本最终正文直接 materialize 成附件。"""
        finalized = super()._postprocess_llm_output(state, content)
        messages = state.get("messages") or []
        last_message = messages[-1] if messages else None
        last_content = self._extract_query(last_message) if last_message is not None else ""
        if "<deep_execution_summary>" not in last_content:
            return finalized
        if "<generated_artifacts>" in last_content:
            return finalized

        query = self._extract_last_human_query(messages)
        if not query:
            return finalized
        deep_thinking_result = self._extract_tagged_block_content(last_content, "deep_thinking_result")
        selected_source = ArtifactPolicy.select_plain_text_artifact_source(
            query,
            deep_thinking_result,
            sanitize_text=self._sanitize_sandbox_artifact_text,
        )
        payload = ArtifactPolicy.build_plain_text_artifact_payload(
            query,
            selected_source,
            sanitize_text=self._sanitize_sandbox_artifact_text,
        )
        if payload is None:
            return finalized

        filename, payload_content = payload
        recovery_preview = f"plain_text -> {filename}"
        self.agent_queue_manager.publish(
            state["task_id"],
            AgentThought(
                id=uuid.uuid4(),
                task_id=state["task_id"],
                event=QueueEvent.DEEP_STEP.value,
                thought=f"模型未输出结构化写文件协议，正在按请求保存为附件：{filename}",
                observation=recovery_preview,
                tool="write_file",
                tool_input={
                    "timeline": DeepTimelineMiddleware._build_tool_timeline_metadata(
                        phase="plain_text_fallback_attempt",
                        preview=recovery_preview,
                        preview_kind="summary",
                        result_preview="",
                        result_kind="artifact",
                        error_kind="plain_text_artifact_fallback",
                        recovered=False,
                        recoverable=True,
                        output_empty=False,
                    )
                },
            ),
        )

        try:
            artifact = self._upload_plain_text_artifact(
                filename=filename,
                content=payload_content,
            )
        except Exception as exc:
            logger.warning("纯文本附件兜底失败: %s", exc)
            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(
                    id=uuid.uuid4(),
                    task_id=state["task_id"],
                    event=QueueEvent.DEEP_STEP.value,
                    thought=f"恢复附件失败：{filename}",
                    observation=f"{type(exc).__name__}: {exc}",
                    tool="write_file",
                    tool_input={
                        "timeline": DeepTimelineMiddleware._build_tool_timeline_metadata(
                            phase="final_failure",
                            preview=recovery_preview,
                            preview_kind="summary",
                            result_preview="",
                            result_kind="artifact",
                            error_kind="plain_text_artifact_fallback",
                            recovered=False,
                            recoverable=True,
                            output_empty=False,
                        )
                    },
                ),
            )
            return finalized

        self.agent_queue_manager.publish(
            state["task_id"],
            AgentThought(
                id=uuid.uuid4(),
                task_id=state["task_id"],
                event=QueueEvent.DEEP_ARTIFACT_CREATED.value,
                thought=str(artifact.get("name", "")),
                observation=str(artifact.get("url", "")),
                tool="artifact",
                tool_input={"artifact": artifact},
            ),
        )
        self.agent_queue_manager.publish(
            state["task_id"],
            AgentThought(
                id=uuid.uuid4(),
                task_id=state["task_id"],
                event=QueueEvent.DEEP_STEP.value,
                thought=f"已自动保存纯文本附件：{filename}",
                observation=recovery_preview,
                tool="write_file",
                tool_input={
                    "timeline": DeepTimelineMiddleware._build_tool_timeline_metadata(
                        phase="plain_text_fallback_success",
                        preview=recovery_preview,
                        preview_kind="summary",
                        result_preview=f"已写入 {filename}",
                        result_kind="artifact",
                        error_kind="plain_text_artifact_fallback",
                        recovered=True,
                        recoverable=True,
                        output_empty=False,
                    )
                },
            ),
        )

        sanitized_lines: list[str] = []
        for raw_line in finalized.splitlines():
            line = raw_line.strip()
            if not line:
                sanitized_lines.append(raw_line)
                continue

            if any(
                keyword in line
                for keyword in (
                    "当前没有可下载附件",
                    "未生成可下载产物",
                    "点击下载",
                    "下载链接",
                    "下载附件",
                    "附件下载",
                    "sandbox:/mnt/data/",
                    "/mnt/data/",
                )
            ):
                continue

            sanitized_lines.append(raw_line)

        sanitized = "\n".join(sanitized_lines).strip()
        if sanitized:
            sanitized += f"\n\n已生成可下载附件：{filename}"
        else:
            sanitized = f"已生成可下载附件：{filename}"
        return sanitized

    @staticmethod
    def _is_recoverable_model_request_error(error: Exception) -> bool:
        """判断是否属于可通过纯文本兜底恢复的模型请求错误。"""
        status_code = getattr(error, "status_code", None)
        if status_code == 400:
            return True

        response = getattr(error, "response", None)
        if getattr(response, "status_code", None) == 400:
            return True

        text = f"{type(error).__name__}: {error}".lower()
        return any(
            marker in text
            for marker in (
                "bad request",
                "error code: 400",
                "code\": 400",
                "'code': 400",
                "status code: 400",
                "400 bad request",
            )
        )

    def _invoke_plain_text_fallback(self, query: str) -> str:
        """在模型请求被拒时，退回到无工具的纯文本生成。"""
        fallback_llm = self._load_default_plain_text_fallback_llm()
        if fallback_llm is not None:
            try:
                response = fallback_llm.invoke([
                    SystemMessage(content=(
                        f"{self.agent_config.preset_prompt}\n\n"
                        "你正在直接生成用户需要的最终内容。"
                        "不要调用任何工具，不要输出 XML/JSON 工具标签，不要输出代码块围栏，"
                        "不要输出解释性前缀。"
                        "如果用户要求生成文件，请直接输出该文件的正文内容。"
                    ).strip()),
                    HumanMessage(content=query),
                ])
                normalized_content = self._extract_llm_text(response)
                if normalized_content:
                    return normalized_content
            except Exception as exc:
                logger.warning("默认模型兜底失败，改用本地模板: %s", exc)

        return self._build_local_plain_text_fallback(query)

    def _load_default_plain_text_fallback_llm(self) -> Any | None:
        service = getattr(self.agent_config, "language_model_service", None)
        load_default = getattr(service, "load_default_language_model", None)
        if not callable(load_default):
            return None

        try:
            return load_default()
        except Exception as exc:
            logger.warning("默认语言模型兜底加载失败，改用本地模板: %s", exc)
            return None

    @staticmethod
    def _build_local_plain_text_fallback(query: str) -> str:
        normalized_query = str(query or "").strip()
        upper_query = normalized_query.upper()
        is_markdown = any(token in normalized_query.lower() for token in (".md", "markdown"))
        title = "# SpaceX IPO Prospectus Draft" if is_markdown else "SPACE EXPLORATION TECHNOLOGIES CORP.\nPROSPECTUS DRAFT"
        sections = [
            "PROSPECTUS SUMMARY",
            "BUSINESS OVERVIEW",
            "RISK FACTORS",
            "MANAGEMENT'S DISCUSSION AND ANALYSIS",
            "USE OF PROCEEDS",
            "LEGAL MATTERS AND DISCLAIMERS",
        ]
        if "招股说明书" not in normalized_query and "prospectus" not in upper_query:
            sections = [
                "OVERVIEW",
                "BACKGROUND",
                "ANALYSIS",
                "SUMMARY",
            ]

        lines = [
            title,
            "",
            "This is a local fallback generated after the provider rejected the model request.",
            f"Original request: {normalized_query or 'N/A'}",
            "",
        ]
        for section in sections:
            if is_markdown:
                lines.extend([
                    f"## {section}",
                    "",
                    "TBD",
                    "",
                ])
            else:
                lines.extend([
                    section,
                    "TBD",
                    "",
                ])

        return "\n".join(lines).strip()

    @staticmethod
    def _extract_llm_text(response: Any) -> str:
        content = getattr(response, "content", response)
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = str(block.get("text", "") or "").strip()
                    if text:
                        parts.append(text)
                elif isinstance(block, str):
                    text = block.strip()
                    if text:
                        parts.append(text)
            return "\n".join(parts).strip()
        return str(content or "").strip()

    @classmethod
    def _should_use_structured_document_pipeline(cls, query: str, route_decision: DeepRouteDecision) -> bool:
        if not route_decision.need_artifact_output:
            return False

        filename = ArtifactPolicy.resolve_artifact_filename(query, allow_default_filename=True)
        if not filename:
            return False

        return ArtifactPolicy.is_text_document_artifact_extension(filename)

    @classmethod
    def _build_document_outline_fallback(cls, query: str, filename: str) -> StructuredDocumentOutlinePlan:
        document_title = ArtifactPolicy.humanize_filename_stem(filename)
        requested_section_titles = cls._extract_requested_outline_section_titles(query)
        if requested_section_titles:
            sections = [
                StructuredDocumentSectionPlan(
                    title=title,
                    purpose="围绕用户在请求中明确列出的章节展开。",
                    key_points=[title, "核心内容", "关键细节"],
                    target_length_hint="根据章节内容保持适度篇幅",
                )
                for title in requested_section_titles[:8]
            ]
            return StructuredDocumentOutlinePlan(document_title=document_title, sections=sections)

        sections = [
            StructuredDocumentSectionPlan(
                title="摘要",
                purpose="概述文档目标、范围和核心信息。",
                key_points=["主题", "目标", "范围", "关键结论"],
                target_length_hint="约 200-300 字",
            ),
            StructuredDocumentSectionPlan(
                title="主体内容",
                purpose="展开主要信息、步骤或说明。",
                key_points=["主要内容", "细节", "逻辑", "示例"],
                target_length_hint="约 400-700 字",
            ),
            StructuredDocumentSectionPlan(
                title="补充说明",
                purpose="补充边界条件、约束和注意事项。",
                key_points=["约束", "注意事项", "风险", "参考信息"],
                target_length_hint="约 200-400 字",
            ),
            StructuredDocumentSectionPlan(
                title="结论与下一步",
                purpose="总结并给出后续建议。",
                key_points=["结论", "建议", "下一步"],
                target_length_hint="约 200-300 字",
            ),
        ]

        return StructuredDocumentOutlinePlan(document_title=document_title, sections=sections)

    @staticmethod
    def _normalize_outline_title(title: str) -> str:
        return re.sub(r"[\s\W_]+", "", str(title or ""), flags=re.UNICODE).casefold()

    @classmethod
    def _extract_requested_outline_section_titles(cls, query: str) -> list[str]:
        normalized_query = textwrap.dedent(str(query or "")).strip()
        if not normalized_query:
            return []

        cue_patterns = (
            r"(?:内容包含|包含|包括|涵盖|应包含|需包含|请包含|章节包括|结构包括|主要包含|主要包括|项目包括|项目包含)\s*[:：]?\s*(?P<body>[^\n\r。！？]+)",
            r"(?:章节|小节|部分|条目)\s*(?:包括|包含|如下|如下所示|有)\s*[:：]?\s*(?P<body>[^\n\r。！？]+)",
        )
        candidate_bodies: list[str] = []
        lines = [line.strip() for line in normalized_query.splitlines() if line.strip()]
        boundary_markers = (
            "正常结果",
            "通过标准",
            "期望结果",
            "验收标准",
            "测试完成后",
            "测试标准",
            "正常输出",
            "输出应该",
        )
        in_evaluation_section = False

        for line in lines:
            if in_evaluation_section:
                break

            boundary_index = min(
                [
                    index
                    for marker in boundary_markers
                    if (index := line.find(marker)) >= 0
                ],
                default=-1,
            )
            if boundary_index >= 0:
                line = line[:boundary_index].strip()
                in_evaluation_section = True

            for pattern in cue_patterns:
                match = re.search(pattern, line, flags=re.IGNORECASE)
                if match:
                    candidate_bodies.append(str(match.group("body") or "").strip())

            if re.match(r"^(?:\d+[.)、\-]|[-*•])\s+.+", line):
                candidate_bodies.append(re.sub(r"^(?:\d+[.)、\-]|[-*•])\s*", "", line).strip())

        if not candidate_bodies:
            for match in re.finditer(
                r"(?:内容包含|包含|包括|涵盖|应包含|需包含|请包含|章节包括|结构包括|主要包含|主要包括|项目包括|项目包含)\s*[:：]?\s*([^\n\r。！？]+)",
                normalized_query,
                flags=re.IGNORECASE,
            ):
                candidate_bodies.append(str(match.group(1) or "").strip())

        titles: list[str] = []
        seen: set[str] = set()
        stop_tokens = {
            "请",
            "不要",
            "我",
            "我们",
            "你",
            "附件",
            "文件",
            "下载",
            "输出",
            "保存",
            "生成",
            "结果",
            "正常结果",
            "正常",
            "内容",
            "要求",
            "包括",
            "包含",
            "以及",
            "和",
            "与",
            "等",
            "等等",
        }
        for body in candidate_bodies:
            for token in re.split(r"[、,，;；/|]+", body):
                candidate = re.sub(r"^[\d.、\-\*\s]+", "", str(token or "").strip())
                candidate = candidate.strip(" \t\r\n。！？；;，,:：`'\"")
                if not candidate:
                    continue
                if re.search(r"[\u4e00-\u9fff]", candidate):
                    candidate = re.sub(r"\s+", "", candidate)
                else:
                    candidate = re.sub(r"\s+", " ", candidate).strip()
                if len(candidate) > 60:
                    continue
                if any(stop in candidate for stop in ("正常结果", "下载链接", "sandbox:/", "/mnt/data/", "本地路径")):
                    continue
                if any(candidate == stop or candidate.startswith(f"{stop} ") for stop in stop_tokens):
                    continue

                normalized_candidate = cls._normalize_outline_title(candidate)
                if not normalized_candidate or normalized_candidate in seen:
                    continue
                seen.add(normalized_candidate)
                titles.append(candidate)
                if len(titles) >= 12:
                    return titles

        return titles

    @classmethod
    def _outline_preserves_requested_sections(
        cls,
        outline: StructuredDocumentOutlinePlan,
        requested_section_titles: list[str],
    ) -> bool:
        if not requested_section_titles:
            return True

        outline_titles = [
            cls._normalize_outline_title(getattr(section, "title", "") or "")
            for section in outline.sections or []
            if str(getattr(section, "title", "") or "").strip()
        ]
        if not outline_titles:
            return False

        for requested_title in requested_section_titles:
            normalized_requested = cls._normalize_outline_title(requested_title)
            if not normalized_requested:
                continue
            if not any(
                normalized_requested in outline_title or outline_title in normalized_requested
                for outline_title in outline_titles
            ):
                return False

        return True

    @classmethod
    def _build_document_outline_repair_prompt(
        cls,
        *,
        query: str,
        filename: str,
        route_decision: DeepRouteDecision,
        requested_section_titles: list[str],
        current_outline: StructuredDocumentOutlinePlan | None = None,
        reason: str = "",
    ) -> str:
        requested_section_lines = "\n".join(f"- {title}" for title in requested_section_titles) if requested_section_titles else "（用户未显式列出固定章节）"
        current_outline_text = current_outline.model_dump_json() if current_outline is not None else "（无）"
        return textwrap.dedent(
            f"""
            你是一个结构化文档大纲修复器。
            你的任务不是自由写作，而是把文档整理成可供后续章节生成使用的 StructuredDocumentOutlinePlan。
            规则：
            - 尽量保留用户已经明确写出的章节/条目，并维持其顺序。
            - 如果用户没有给出明确章节，就根据任务意图生成最小可用大纲。
            - 章节数由任务意图和用户要求决定，不要为了凑数强行增删章节。
            - 章节标题应简洁、可直接用于最终文件。
            - 不要输出解释性文字，只输出结构化结果。
            - 如果当前大纲不完整，请修复，而不是复述原文或输出普通文本。

            目标文件：{filename}
            用户任务：{query}
            路由摘要：{route_decision.summary or route_decision.reason}
            修复原因：{reason or '结构化输出失败或章节覆盖不完整'}
            用户显式章节候选：
            {requested_section_lines}
            当前大纲（仅供修复参考，可能不完整）：
            {current_outline_text}
            """
        ).strip()

    @classmethod
    def _normalize_structured_document_outline(
        cls,
        outline: StructuredDocumentOutlinePlan | dict[str, Any] | Any,
        *,
        query: str,
        filename: str,
    ) -> StructuredDocumentOutlinePlan:
        fallback = cls._build_document_outline_fallback(query, filename)
        if isinstance(outline, dict):
            try:
                outline = StructuredDocumentOutlinePlan(**outline)
            except Exception:
                return fallback
        elif not isinstance(outline, StructuredDocumentOutlinePlan):
            return fallback

        document_title = str(outline.document_title or "").strip() or fallback.document_title
        normalized_sections: list[StructuredDocumentSectionPlan] = []
        seen_titles: set[str] = set()
        for raw_section in outline.sections or []:
            if isinstance(raw_section, dict):
                try:
                    raw_section = StructuredDocumentSectionPlan(**raw_section)
                except Exception:
                    continue

            title = str(getattr(raw_section, "title", "") or "").strip()
            if not title:
                continue
            normalized_title = re.sub(r"[\s\W_]+", "", title, flags=re.UNICODE).casefold()
            if normalized_title in seen_titles:
                continue
            seen_titles.add(normalized_title)
            purpose = str(getattr(raw_section, "purpose", "") or "").strip()
            key_points = [
                str(item).strip()
                for item in (getattr(raw_section, "key_points", []) or [])
                if str(item).strip()
            ]
            target_length_hint = str(getattr(raw_section, "target_length_hint", "") or "").strip()
            normalized_sections.append(
                StructuredDocumentSectionPlan(
                    title=title,
                    purpose=purpose,
                    key_points=key_points,
                    target_length_hint=target_length_hint,
                )
            )
            if len(normalized_sections) >= 8:
                break

        if not normalized_sections:
            return fallback

        return StructuredDocumentOutlinePlan(
            document_title=document_title,
            sections=normalized_sections,
        )

    @classmethod
    def _build_document_fragment_stem(cls, title: str, index: int) -> str:
        candidate = ArtifactPolicy.build_generated_artifact_filename(title) or f"section_{index}"
        stem = os.path.splitext(candidate)[0]
        stem = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "_", stem, flags=re.UNICODE)
        stem = stem.strip("._")
        return stem or f"section_{index}"

    @classmethod
    def _render_document_front_matter(
        cls,
        *,
        outline: StructuredDocumentOutlinePlan,
        filename: str,
        markdown: bool,
    ) -> str:
        title = str(outline.document_title or "").strip() or ArtifactPolicy.humanize_filename_stem(filename)
        if markdown:
            return f"# {title}\n\n"

        separator = "=" * max(32, min(80, len(title) * 2))
        return f"{title}\n{separator}\n\n"

    @classmethod
    def _render_document_section_block(
        cls,
        *,
        section: StructuredDocumentSectionPlan,
        body: str,
        markdown: bool,
    ) -> str:
        normalized_body = textwrap.dedent(str(body or "")).strip()
        if not normalized_body:
            normalized_body = "待补充内容"

        if markdown:
            return f"## {section.title}\n\n{normalized_body}\n\n"

        separator = "-" * max(32, min(80, len(section.title) * 2))
        return f"{section.title}\n{separator}\n\n{normalized_body}\n\n"

    @classmethod
    def _build_document_section_prompt(
        cls,
        *,
        query: str,
        filename: str,
        outline: StructuredDocumentOutlinePlan,
        section: StructuredDocumentSectionPlan,
        section_index: int,
        section_total: int,
        markdown: bool,
    ) -> str:
        output_style = "Markdown" if markdown else "纯文本"
        key_points = "；".join(section.key_points[:8]) or "按章节目标展开"
        return textwrap.dedent(
            f"""
            你正在为最终会被拼接成文件的文档撰写单个章节正文。
            输出风格：{output_style}
            规则：
            - 只输出本章节正文，不要输出章节标题，不要输出前言，不要输出代码块围栏。
            - 不要提及“以下是”“我将”“本章将”这类元叙述。
            - 内容要与整篇文档保持一致，并且可以直接拼接到最终文件中。
            - 如有需要，可以使用简洁的列表，但不要在每一小段前重复章节标题。

            文档标题：{outline.document_title}
            目标文件：{filename}
            章节序号：{section_index}/{section_total}
            章节标题：{section.title}
            写作目的：{section.purpose or '围绕章节标题展开'}
            关键点：{key_points}
            长度提示：{section.target_length_hint or '保持适度篇幅，内容完整'}

            用户原始请求：
            {query}
            """
        ).strip()

    @classmethod
    def _build_local_document_section_body(
        cls,
        *,
        query: str,
        outline: StructuredDocumentOutlinePlan,
        section: StructuredDocumentSectionPlan,
        section_index: int,
        section_total: int,
        markdown: bool,
    ) -> str:
        key_points = [point for point in section.key_points[:6] if point]
        intro = section.purpose or "根据用户要求生成本章节内容。"
        opening = f"{section.title}围绕文档整体目标展开，重点覆盖{ '、'.join(key_points) if key_points else '关键内容、约束和建议' }。"

        lines = [intro, "", opening]
        if key_points:
            lines.append("")
            lines.extend(f"- {point}" for point in key_points)
        if markdown:
            lines.append("")
            lines.append(f"> 章节 {section_index}/{section_total} 已按本地模板补全。")
        else:
            lines.append("")
            lines.append(f"（章节 {section_index}/{section_total} 已按本地模板补全。）")

        return "\n".join(line for line in lines if line is not None).strip()

    def _generate_structured_document_outline(
        self,
        *,
        query: str,
        filename: str,
        route_decision: DeepRouteDecision,
        timeline: DeepTimelineMiddleware,
    ) -> StructuredDocumentOutlinePlan:
        requested_section_titles = self._extract_requested_outline_section_titles(query)
        requested_section_titles_text = (
            "\n".join(f"- {title}" for title in requested_section_titles)
            if requested_section_titles
            else "（无）"
        )
        step_id = uuid.uuid4()
        timeline.publish_step(
            step_id=step_id,
            step_type="plan",
            status="start",
            title="规划文档结构与章节内容框架",
            detail="正在生成结构化文档大纲",
            technical_detail=f"filename={filename}",
            tool="document_outline",
        )

        outline_prompt = textwrap.dedent(
            f"""
            你是一个结构化文档大纲规划器。
            你的目标是为最终要拼接成文件的文档输出标题和章节列表。
            规则：
            - 章节数由任务复杂度和用户要求决定，避免空洞或重复，不要为了凑数强行控制为固定数量。
            - 章节标题必须简洁、可直接作为最终文件中的章节名。
            - 每章都要包含写作目的、关键点和长度提示。
            - 如果用户明确要求了固定章节，请优先满足用户要求。
            - 不要输出 Markdown、JSON 或解释性文字，只通过结构化输出返回结果。

            目标文件：{filename}
            用户任务：{query}
            路由摘要：{route_decision.summary or route_decision.reason}
            用户显式章节候选：
            {requested_section_titles_text}
            """
        ).strip()

        try:
            structured_llm = self.llm.with_structured_output(StructuredDocumentOutlinePlan)
            response = structured_llm.invoke([
                HumanMessage(content=outline_prompt),
            ])
            outline = self._normalize_structured_document_outline(
                response,
                query=query,
                filename=filename,
            )
            if requested_section_titles and not self._outline_preserves_requested_sections(
                outline,
                requested_section_titles,
            ):
                repaired_outline = self._repair_structured_document_outline(
                    query=query,
                    filename=filename,
                    route_decision=route_decision,
                    requested_section_titles=requested_section_titles,
                    current_outline=outline,
                    timeline=timeline,
                    reason="当前大纲未满足用户显式章节或结构不完整",
                )
                if repaired_outline is not None:
                    outline = repaired_outline
                else:
                    outline = self._build_document_outline_fallback(query, filename)
            timeline.publish_step(
                step_id=step_id,
                step_type="plan",
                status="success",
                title="规划文档结构与章节内容框架",
                detail=f"已生成 {len(outline.sections)} 个章节",
                technical_detail=outline.model_dump_json(),
                tool="document_outline",
            )
            return outline
        except Exception as exc:
            if self._is_recoverable_model_request_error(exc):
                logger.warning("结构化文档大纲生成请求被模型提供方拒绝，将回退到外层纯文本兜底: %s", exc)
                raise
            logger.warning("结构化文档大纲生成失败，回退到启发式大纲: %s", exc)
            repaired_outline = self._repair_structured_document_outline(
                query=query,
                filename=filename,
                route_decision=route_decision,
                requested_section_titles=requested_section_titles,
                current_outline=None,
                timeline=timeline,
                reason=str(exc),
            )
            outline = repaired_outline or self._build_document_outline_fallback(query, filename)
            timeline.publish_step(
                step_id=step_id,
                step_type="plan",
                status="warning",
                title="规划文档结构与章节内容框架",
                detail="已回退到启发式大纲",
                technical_detail=f"{type(exc).__name__}: {exc}",
                tool="document_outline",
            )
            return outline

    def _repair_structured_document_outline(
        self,
        *,
        query: str,
        filename: str,
        route_decision: DeepRouteDecision,
        requested_section_titles: list[str],
        current_outline: StructuredDocumentOutlinePlan | None,
        timeline: DeepTimelineMiddleware,
        reason: str,
    ) -> StructuredDocumentOutlinePlan | None:
        step_id = uuid.uuid4()
        timeline.publish_step(
            step_id=step_id,
            step_type="plan",
            status="start",
            title="修复文档结构与章节内容框架",
            detail="正在尝试修复结构化文档大纲",
            technical_detail=reason,
            tool="document_outline_repair",
        )

        repair_prompt = self._build_document_outline_repair_prompt(
            query=query,
            filename=filename,
            route_decision=route_decision,
            requested_section_titles=requested_section_titles,
            current_outline=current_outline,
            reason=reason,
        )

        try:
            structured_llm = self.llm.with_structured_output(StructuredDocumentOutlinePlan)
            response = structured_llm.invoke([
                HumanMessage(content=repair_prompt),
            ])
            repaired_outline = self._normalize_structured_document_outline(
                response,
                query=query,
                filename=filename,
            )
            if not repaired_outline.sections:
                logger.warning("修复后大纲为空，回退到通用大纲")
                timeline.publish_step(
                    step_id=step_id,
                    step_type="plan",
                    status="warning",
                    title="修复文档结构与章节内容框架",
                    detail="修复后大纲为空，继续回退到通用大纲",
                    technical_detail="empty_outline",
                    tool="document_outline_repair",
                )
                return None
            if requested_section_titles and not self._outline_preserves_requested_sections(
                repaired_outline,
                requested_section_titles,
            ):
                logger.warning("修复后大纲未保留用户显式章节，回退到通用大纲")
                timeline.publish_step(
                    step_id=step_id,
                    step_type="plan",
                    status="warning",
                    title="修复文档结构与章节内容框架",
                    detail="修复后大纲未保留用户显式章节，继续回退到通用大纲",
                    technical_detail="requested_sections_lost",
                    tool="document_outline_repair",
                )
                return None

            timeline.publish_step(
                step_id=step_id,
                step_type="plan",
                status="success",
                title="修复文档结构与章节内容框架",
                detail=f"已修复为 {len(repaired_outline.sections)} 个章节",
                technical_detail=repaired_outline.model_dump_json(),
                tool="document_outline_repair",
            )
            return repaired_outline
        except Exception as exc:
            if self._is_recoverable_model_request_error(exc):
                logger.warning("结构化文档大纲修复请求被模型提供方拒绝，将回退到外层纯文本兜底: %s", exc)
                raise
            logger.warning("结构化文档大纲修复失败: %s", exc)
            timeline.publish_step(
                step_id=step_id,
                step_type="plan",
                status="warning",
                title="修复文档结构与章节内容框架",
                detail="修复失败，继续回退到通用大纲",
                technical_detail=f"{type(exc).__name__}: {exc}",
                tool="document_outline_repair",
            )
            return None

    def _generate_document_section_body(
        self,
        *,
        query: str,
        filename: str,
        outline: StructuredDocumentOutlinePlan,
        section: StructuredDocumentSectionPlan,
        section_index: int,
        section_total: int,
        markdown: bool,
        timeline: DeepTimelineMiddleware,
    ) -> str:
        step_id = uuid.uuid4()
        start_detail = f"第 {section_index}/{section_total} 章：{section.title}"
        timeline.publish_step(
            step_id=step_id,
            step_type="reflection",
            status="start",
            title=f"生成章节：{section.title}",
            detail=start_detail,
            technical_detail=section.purpose or section.target_length_hint,
            tool="document_section",
        )

        section_prompt = self._build_document_section_prompt(
            query=query,
            filename=filename,
            outline=outline,
            section=section,
            section_index=section_index,
            section_total=section_total,
            markdown=markdown,
        )

        try:
            response = self.llm.invoke([
                SystemMessage(
                    content=(
                        "你正在生成最终文档的一个章节正文。"
                        "只输出章节正文，不要输出章节标题，不要输出解释。"
                    )
                ),
                HumanMessage(content=section_prompt),
            ])
            body = self._extract_llm_text(response)
            body = self._sanitize_document_section_body(body, section.title)
            if not body or len(body) < 120:
                raise ValueError("章节正文过短")

            timeline.publish_step(
                step_id=step_id,
                step_type="reflection",
                status="success",
                title=f"生成章节：{section.title}",
                detail=start_detail,
                technical_detail=body[:1200],
                tool="document_section",
            )
            return body
        except Exception as exc:
            if self._is_recoverable_model_request_error(exc):
                logger.warning("章节生成请求被模型提供方拒绝，将回退到外层纯文本兜底: %s", exc)
                raise
            logger.warning("章节生成失败，回退本地模板: %s", exc)
            fallback_body = self._build_local_document_section_body(
                query=query,
                outline=outline,
                section=section,
                section_index=section_index,
                section_total=section_total,
                markdown=markdown,
            )
            timeline.publish_step(
                step_id=step_id,
                step_type="reflection",
                status="warning",
                title=f"章节回退本地模板：{section.title}",
                detail="已使用本地模板补全章节内容",
                technical_detail=f"{type(exc).__name__}: {exc}",
                tool="document_section",
            )
            return fallback_body

    @staticmethod
    def _sanitize_document_section_body(text: str, section_title: str = "") -> str:
        normalized = textwrap.dedent(str(text or "")).strip()
        if not normalized:
            return ""

        cleaned_lines: list[str] = []
        section_title = str(section_title or "").strip()
        seen_content = False
        for raw_line in normalized.splitlines():
            line = raw_line.strip()
            if not line:
                if seen_content:
                    cleaned_lines.append("")
                continue

            if not seen_content and (
                line.startswith("#")
                or line == section_title
                or line == section_title.upper()
                or (section_title and section_title in line and len(line) <= len(section_title) + 6)
            ):
                continue

            if line in {"text", "markdown", "md", "txt", "复制代码"}:
                continue

            seen_content = True
            cleaned_lines.append(raw_line.rstrip())

        return "\n".join(cleaned_lines).strip()

    def _generate_structured_document_artifact(
        self,
        *,
        backend: Any,
        artifact_root: str,
        query: str,
        route_decision: DeepRouteDecision,
        timeline: DeepTimelineMiddleware,
        task_id: Any,
    ) -> tuple[str, list[dict[str, Any]]]:
        explicit_filename = ArtifactPolicy.infer_requested_artifact_filename(query)
        filename = ArtifactPolicy.resolve_artifact_filename(query, allow_default_filename=True)
        if not filename:
            raise ValueError("结构化文档流水线要求明确的目标文件名")

        markdown = os.path.splitext(filename)[1].lower() in {".md", ".markdown"}
        outline = self._generate_structured_document_outline(
            query=query,
            filename=filename,
            route_decision=route_decision,
            timeline=timeline,
        )
        if not explicit_filename and outline.document_title:
            refined_filename = ArtifactPolicy.build_generated_artifact_filename(
                f"{outline.document_title}{os.path.splitext(filename)[1]}"
            )
            if refined_filename:
                filename = refined_filename

        build_root = f"{SandboxPolicy.document_build_base_dir.rstrip('/')}/{str(task_id).strip()}"
        build_dir = f"{build_root}/{self._build_document_fragment_stem(filename, 0)}"
        final_path = f"{artifact_root.rstrip('/')}/{filename}"

        assembled_parts: list[str] = [
            self._render_document_front_matter(
                outline=outline,
                filename=filename,
                markdown=markdown,
            )
        ]
        fragment_files: list[tuple[str, bytes]] = [
            (f"{build_dir}/00_front_matter.txt", assembled_parts[0].encode("utf-8"))
        ]

        section_total = len(outline.sections)
        if not section_total:
            raise ValueError("结构化文档大纲没有章节")

        for index, section in enumerate(outline.sections, start=1):
            body = self._generate_document_section_body(
                query=query,
                filename=filename,
                outline=outline,
                section=section,
                section_index=index,
                section_total=section_total,
                markdown=markdown,
                timeline=timeline,
            )
            block = self._render_document_section_block(
                section=section,
                body=body,
                markdown=markdown,
            )
            assembled_parts.append(block)
            fragment_stem = self._build_document_fragment_stem(section.title, index)
            fragment_files.append(
                (
                    f"{build_dir}/{index:02d}_{fragment_stem}.txt",
                    block.encode("utf-8"),
                )
            )

        assembled_content = "".join(assembled_parts).strip() + "\n"
        execute_method = getattr(backend, "execute", None)
        upload_method = getattr(backend, "upload_files", None)
        if callable(execute_method) and callable(upload_method):
            mkdir_result = execute_method(
                f"mkdir -p {shlex.quote(build_root)} {shlex.quote(build_dir)} {shlex.quote(artifact_root.rstrip('/'))}",
                timeout=15,
            )
            if getattr(mkdir_result, "exit_code", 1) == 0:
                upload_responses = upload_method(fragment_files)
                upload_errors = [response for response in upload_responses if getattr(response, "error", None)]
                if not upload_errors:
                    stitch_command = "cat " + " ".join(shlex.quote(path) for path, _ in fragment_files)
                    stitch_command += f" > {shlex.quote(final_path)}"
                    stitch_result = execute_method(stitch_command, timeout=60)
                    if getattr(stitch_result, "exit_code", 1) == 0:
                        artifacts = self._collect_artifacts(
                            backend=backend,
                            artifact_root=artifact_root,
                            timeline=timeline,
                        )
                        if artifacts:
                            return (
                                f"已按 {section_total} 个章节生成并保存为 {filename}",
                                artifacts,
                            )
                        logger.warning("结构化文档已拼接但未扫描到产物，准备回退直接上传")
                    else:
                        logger.warning(
                            "结构化文档拼接命令失败，准备回退直接上传: %s",
                            getattr(stitch_result, "output", ""),
                        )
                else:
                    logger.warning("结构化文档章节上传失败，准备回退直接上传: %s", upload_errors)
            else:
                logger.warning("结构化文档目录创建失败，准备回退直接上传: %s", getattr(mkdir_result, "output", ""))

        artifact = self._upload_plain_text_artifact(
            filename=filename,
            content=assembled_content,
        )
        if artifact is None:
            raise RuntimeError(f"无法保存结构化文档附件：{filename}")

        self.agent_queue_manager.publish(
            task_id,
            AgentThought(
                id=uuid.uuid4(),
                task_id=task_id,
                event=QueueEvent.DEEP_ARTIFACT_CREATED.value,
                thought=str(artifact.get("name", "")),
                observation=str(artifact.get("url", "")),
                tool="artifact",
                tool_input={"artifact": artifact},
            ),
        )
        return (
            f"已按 {section_total} 个章节生成并保存为 {filename}",
            [artifact],
        )

    @staticmethod
    def _extract_last_human_query(messages: list[Any]) -> str:
        if not isinstance(messages, list):
            return ""

        for message in reversed(messages):
            message_type = str(getattr(message, "type", "") or "").strip().lower()
            if not message_type and isinstance(message, dict):
                message_type = str(message.get("type", "") or "").strip().lower()
            if message_type != "human":
                continue

            content = getattr(message, "content", "")
            if not content and isinstance(message, dict):
                content = message.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return str(block.get("text", ""))
            return str(content or "")

        return ""

    def _upload_plain_text_artifact(
        self,
        *,
        filename: str,
        content: str,
    ) -> dict[str, Any] | None:
        flask_app = self.agent_config.runtime_flask_app
        app_context = nullcontext()
        if flask_app is not None and not has_app_context():
            app_context = flask_app.app_context()

        with app_context:
            from app.http.module import injector  # noqa: PLC0415
            from internal.service import CosService  # noqa: PLC0415

            cos_service = injector.get(CosService)
            mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            upload_file = cos_service.upload_bytes(
                filename=filename,
                content=content.encode("utf-8"),
                account_id=self.agent_config.user_id,
                mime_type=mime_type,
                folder="artifacts",
            )
            return {
                "id": str(upload_file.id),
                "name": upload_file.name,
                "size": upload_file.size,
                "extension": upload_file.extension,
                "mime_type": upload_file.mime_type,
                "url": cos_service.get_file_url(upload_file.key, download_name=upload_file.name),
            }

    def _recover_missing_artifact_from_deep_answer(
        self,
        *,
        backend: Any,
        artifact_root: str,
        query: str,
        deep_answer: str,
        timeline: DeepTimelineMiddleware,
        allow_default_filename: bool = False,
    ) -> bool:
        payload = ArtifactPolicy.extract_write_file_payload(deep_answer)
        recovery_mode = "protocol"
        if payload is None:
            payload = ArtifactPolicy.build_plain_text_artifact_payload(
                query,
                deep_answer,
                allow_default_filename=allow_default_filename,
                sanitize_text=self._sanitize_sandbox_artifact_text,
            )
            if payload is None:
                return False
            recovery_mode = "plain_text"

        write_path, content = payload
        normalized_path = write_path.strip()
        if not normalized_path.startswith("/"):
            normalized_path = f"{artifact_root.rstrip('/')}/{os.path.basename(normalized_path)}"

        artifact_name = os.path.basename(normalized_path) or normalized_path
        recovery_preview = f"{recovery_mode} -> {artifact_name}"
        attempt_title = "写文件协议待修复" if recovery_mode == "protocol" else "纯文本附件兜底"
        attempt_detail = (
            f"检测到可恢复的写文件协议，正在尝试恢复附件：{artifact_name}"
            if recovery_mode == "protocol"
            else f"模型未输出结构化写文件协议，正在按请求保存为附件：{artifact_name}"
        )
        timeline.publish_step(
            step_id=uuid.uuid4(),
            step_type="artifact",
            status="warning",
            title=attempt_title,
            detail=attempt_detail,
            technical_detail=recovery_preview,
            tool="write_file",
            tool_input={
                "timeline": {
                    "phase": "recovery_attempt" if recovery_mode == "protocol" else "plain_text_fallback_attempt",
                    "preview": recovery_preview,
                    "preview_kind": "protocol" if recovery_mode == "protocol" else "summary",
                    "result_preview": "",
                    "result_kind": "artifact",
                    "error_kind": "protocol_error" if recovery_mode == "protocol" else "plain_text_artifact_fallback",
                    "recovered": False,
                    "recoverable": True,
                    "output_empty": recovery_mode == "protocol",
                }
            },
        )

        upload_method = getattr(backend, "upload_files", None)
        if not callable(upload_method):
            timeline.publish_step(
                step_id=uuid.uuid4(),
                step_type="artifact",
                status="error",
                title="恢复附件失败",
                detail=f"沙箱不支持文件上传，无法恢复附件：{artifact_name}",
                technical_detail="upload_files unavailable",
                tool="write_file",
                tool_input={
                    "timeline": {
                        "phase": "final_failure",
                        "preview": recovery_preview,
                        "preview_kind": "protocol" if recovery_mode == "protocol" else "summary",
                        "result_preview": "",
                        "result_kind": "artifact",
                        "error_kind": "artifact_materialization" if recovery_mode == "protocol" else "plain_text_artifact_fallback",
                        "recovered": False,
                        "recoverable": True,
                        "output_empty": recovery_mode == "protocol",
                    }
                },
            )
            return False

        upload_responses = upload_method([(normalized_path, content.encode("utf-8"))])
        if not upload_responses:
            timeline.publish_step(
                step_id=uuid.uuid4(),
                step_type="artifact",
                status="error",
                title="恢复附件失败",
                detail=f"无法将模型输出恢复为附件：{artifact_name}",
                technical_detail="upload_files returned no responses",
                tool="write_file",
                tool_input={
                    "timeline": {
                        "phase": "final_failure",
                        "preview": recovery_preview,
                        "preview_kind": "protocol" if recovery_mode == "protocol" else "summary",
                        "result_preview": "",
                        "result_kind": "artifact",
                        "error_kind": "artifact_materialization" if recovery_mode == "protocol" else "plain_text_artifact_fallback",
                        "recovered": False,
                        "recoverable": True,
                        "output_empty": recovery_mode == "protocol",
                    }
                },
            )
            return False
        if any(getattr(response, "error", None) for response in upload_responses):
            timeline.publish_step(
                step_id=uuid.uuid4(),
                step_type="artifact",
                status="error",
                title="恢复附件失败",
                detail=f"无法将模型输出恢复为附件：{artifact_name}",
                technical_detail="; ".join(
                    str(getattr(response, "error", "")) for response in upload_responses if getattr(response, "error", None)
                ),
                tool="write_file",
                tool_input={
                    "timeline": {
                        "phase": "final_failure",
                        "preview": recovery_preview,
                        "preview_kind": "protocol" if recovery_mode == "protocol" else "summary",
                        "result_preview": "",
                        "result_kind": "artifact",
                        "error_kind": "artifact_materialization" if recovery_mode == "protocol" else "plain_text_artifact_fallback",
                        "recovered": False,
                        "recoverable": True,
                        "output_empty": recovery_mode == "protocol",
                    }
                },
            )
            return False

        timeline.publish_step(
            step_id=uuid.uuid4(),
            step_type="artifact",
            status="success",
            title="已自动修复并恢复附件" if recovery_mode == "protocol" else "已自动保存纯文本附件",
            detail=f"已将 {artifact_name} 写入沙箱，准备重新扫描产物",
            technical_detail=recovery_preview,
            tool="write_file",
            tool_input={
                "timeline": {
                    "phase": "recovery_success" if recovery_mode == "protocol" else "plain_text_fallback_success",
                    "preview": recovery_preview,
                    "preview_kind": "protocol" if recovery_mode == "protocol" else "summary",
                    "result_preview": f"已写入 {artifact_name}",
                    "result_kind": "artifact",
                    "error_kind": "protocol_error" if recovery_mode == "protocol" else "plain_text_artifact_fallback",
                    "recovered": True,
                    "recoverable": True,
                    "output_empty": False,
                }
            },
        )
        return True

    def _deep_agent_node(self, state: AgentState) -> AgentState:
        task_id = state["task_id"]
        cancel_event = state.get("cancel_event")

        def raise_if_cancelled() -> None:
            if cancel_event is not None and cancel_event.is_set():
                raise AgentStreamCancelled()

        raise_if_cancelled()
        start_at = time.perf_counter()
        timeline = DeepTimelineMiddleware(
            task_id=task_id,
            publisher=self.agent_queue_manager.publish,
            tool_policy=getattr(self.agent_config, "tool_policy", None),
            cancel_event=state.get("cancel_event"),
        )
        query = self._extract_query(state["messages"][-1])

        route_step_id = uuid.uuid4()
        timeline.publish_step(
            step_id=route_step_id,
            step_type="plan",
            status="start",
            title="分析执行策略",
            detail="正在判断是否需要沙箱、文件输出和子任务拆解",
        )

        with track_language_model_usage(self.llm) as usage_tracker:
            route_decision = self._decide_deep_route(query)
            raise_if_cancelled()
            timeline.publish_step(
                step_id=route_step_id,
                step_type="plan",
                status="success",
                title="分析执行策略",
                detail=route_decision.summary or route_decision.reason or "已完成执行策略分析",
                technical_detail=route_decision.model_dump_json(),
                tool_input={"route": route_decision.model_dump()},
            )

            backend = None
            raise_if_cancelled()
            try:
                deep_agent, backend, artifact_root, used_sandbox = self._build_deep_agent(
                    task_id=task_id,
                    route_decision=route_decision,
                    timeline=timeline,
                )
            except Exception as e:
                raise_if_cancelled()
                logger.warning("deepagents 子 Agent 构建失败，降级为普通模式: %s", e)
                timeline.publish_step(
                    step_id=uuid.uuid4(),
                    step_type="reflection",
                    status="error",
                    title="初始化深度执行失败",
                    detail="深度执行初始化失败，已回退到普通流程",
                    technical_detail=f"{type(e).__name__}: {e}",
                )
                return {"messages": []}

            if cancel_event is not None and cancel_event.is_set():
                close_method = getattr(backend, "close", None)
                if callable(close_method):
                    try:
                        close_method()
                    except Exception:
                        logger.debug("关闭已取消的深度执行 backend 时发生异常", exc_info=True)
                raise AgentStreamCancelled()

            deep_answer = ""
            artifacts: list[dict[str, Any]] = []
            structured_document_mode = self._should_use_structured_document_pipeline(query, route_decision)
            skip_regular_deep_invoke = False
            if structured_document_mode:
                try:
                    deep_answer, artifacts = self._generate_structured_document_artifact(
                        backend=backend,
                        artifact_root=artifact_root,
                        query=query,
                        route_decision=route_decision,
                        timeline=timeline,
                        task_id=task_id,
                    )
                except Exception as e:
                    raise_if_cancelled()
                    if self._is_recoverable_model_request_error(e):
                        logger.warning("结构化文档流水线请求被模型提供方拒绝，切换到纯文本兜底: %s", e)
                        timeline.publish_step(
                            step_id=uuid.uuid4(),
                            step_type="reflection",
                            status="warning",
                            title="结构化文档请求被拒，切换纯文本兜底",
                            detail="结构化文档请求返回 bad request，已切换到无工具的纯文本生成模式",
                            technical_detail=f"{type(e).__name__}: {e}",
                            tool="model_fallback",
                            tool_input={
                                "timeline": {
                                    "phase": "structured_document_model_request_fallback",
                                    "preview": "bad request -> plain text fallback",
                                    "preview_kind": "summary",
                                    "result_preview": "",
                                    "result_kind": "text",
                                    "error_kind": "model_request_bad_request",
                                    "recovered": False,
                                    "recoverable": True,
                                    "output_empty": True,
                                }
                            },
                        )
                        deep_answer = self._invoke_plain_text_fallback(query)
                        if used_sandbox and route_decision.need_artifact_output and deep_answer:
                            if self._recover_missing_artifact_from_deep_answer(
                                backend=backend,
                                artifact_root=artifact_root,
                                query=query,
                                deep_answer=deep_answer,
                                timeline=timeline,
                                allow_default_filename=True,
                            ):
                                artifacts = self._collect_artifacts(
                                    backend=backend,
                                    artifact_root=artifact_root,
                                    timeline=timeline,
                                )
                        if not deep_answer:
                            logger.error("纯文本兜底未能生成有效内容")
                            self.agent_queue_manager.publish_failure(
                                task_id,
                                e,
                                context="深度执行过程中出现错误",
                            )
                            raise
                        structured_document_mode = False
                        skip_regular_deep_invoke = True
                    else:
                        logger.warning("结构化文档流水线失败，回退到常规深度执行: %s", e)
                        timeline.publish_step(
                            step_id=uuid.uuid4(),
                            step_type="reflection",
                            status="warning",
                            title="结构化文档流水线失败",
                            detail="已回退到常规深度执行流程",
                            technical_detail=f"{type(e).__name__}: {e}",
                            tool="structured_document_pipeline",
                        )
                        structured_document_mode = False

            try:
                if not structured_document_mode and not skip_regular_deep_invoke:
                    raise_if_cancelled()
                    result = deep_agent.invoke({
                        "messages": [HumanMessage(content=query)],
                    })
                    raise_if_cancelled()
                    messages = result.get("messages", [])
                    if messages:
                        last = messages[-1]
                        deep_answer = self._extract_llm_text(last)

                    if used_sandbox:
                        artifacts = self._collect_artifacts(
                            backend=backend,
                            artifact_root=artifact_root,
                            timeline=timeline,
                        )
                        if not artifacts and route_decision.need_artifact_output:
                            if self._recover_missing_artifact_from_deep_answer(
                                backend=backend,
                                artifact_root=artifact_root,
                                query=query,
                                deep_answer=deep_answer,
                                timeline=timeline,
                                allow_default_filename=True,
                            ):
                                artifacts = self._collect_artifacts(
                                    backend=backend,
                                    artifact_root=artifact_root,
                                    timeline=timeline,
                                )
            except AgentStreamCancelled:
                raise
            except Exception as e:
                raise_if_cancelled()
                if structured_document_mode:
                    raise
                if self._is_recoverable_model_request_error(e):
                    logger.warning("deepagents 请求被模型提供方拒绝，切换到纯文本兜底: %s", e)
                    timeline.publish_step(
                        step_id=uuid.uuid4(),
                        step_type="reflection",
                        status="warning",
                        title="模型请求被拒，切换纯文本兜底",
                        detail="当前模型请求返回 bad request，已切换到无工具的纯文本生成模式",
                        technical_detail=f"{type(e).__name__}: {e}",
                        tool="model_fallback",
                        tool_input={
                            "timeline": {
                                "phase": "model_request_fallback",
                                "preview": "bad request -> plain text fallback",
                                "preview_kind": "summary",
                                "result_preview": "",
                                "result_kind": "text",
                                "error_kind": "model_request_bad_request",
                                "recovered": False,
                                "recoverable": True,
                                "output_empty": True,
                            }
                        },
                    )
                    deep_answer = self._invoke_plain_text_fallback(query)
                    if used_sandbox and route_decision.need_artifact_output and deep_answer:
                        if self._recover_missing_artifact_from_deep_answer(
                            backend=backend,
                            artifact_root=artifact_root,
                            query=query,
                            deep_answer=deep_answer,
                            timeline=timeline,
                            allow_default_filename=True,
                        ):
                            artifacts = self._collect_artifacts(
                                backend=backend,
                                artifact_root=artifact_root,
                                timeline=timeline,
                            )
                    if not deep_answer:
                        logger.error("纯文本兜底未能生成有效内容")
                        self.agent_queue_manager.publish_failure(
                            task_id,
                            e,
                            context="深度执行过程中出现错误",
                        )
                        raise
                else:
                    logger.error("deepagents 执行失败: %s", e)
                    self.agent_queue_manager.publish_failure(
                        task_id,
                        e,
                        context="深度执行过程中出现错误",
                    )
                    raise
            finally:
                close_method = getattr(backend, "close", None)
                if callable(close_method):
                    try:
                        close_method()
                    except Exception:
                        logger.debug("关闭深度执行 backend 时发生异常", exc_info=True)

        raise_if_cancelled()
        latency = time.perf_counter() - start_at
        deep_answer = self._sanitize_deep_answer(deep_answer, artifacts=artifacts)
        completion_summary = self._build_completion_summary(
            route_decision=route_decision,
            used_sandbox=used_sandbox,
            deep_answer=deep_answer,
            artifacts=artifacts,
        )
        timeline.publish_complete(
            completion_summary,
            latency=latency,
            artifact_count=len(artifacts),
            total_token_count=usage_tracker.total_token_count,
            total_price=usage_tracker.total_price,
        )

        thinking_context = self._build_thinking_context(
            route_decision=route_decision,
            used_sandbox=used_sandbox,
            deep_answer=deep_answer,
            artifacts=artifacts,
        )
        return {"messages": [AIMessage(content=thinking_context)]}

    @staticmethod
    def _extract_query(message: Any) -> str:
        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    return str(block.get("text", ""))
        return str(content)

    def _decide_deep_route(self, query: str) -> DeepRouteDecision:
        if self._is_explicit_artifact_request(query):
            normalized = self._heuristic_deep_route(query)
            normalized.need_file_io = True
            normalized.need_artifact_output = True
            normalized.need_sandbox = True
            normalized.reason = "规则判断：明确请求文件或附件输出，优先走文件链路"
            normalized.summary = "需要沙箱执行"
            return normalized

        routing_prompt = (
            "你是一个深度执行路由器。请判断这次任务是否需要沙箱执行、文件读写、"
            "代码执行、子任务拆解、产物输出。"
            "如果需要生成 txt/csv/json/md/html/docx/xlsx/代码文件，need_artifact_output 必须为 true。"
            "如果需要执行 Python/Shell、读写真实文件或生成可下载附件，need_sandbox 必须为 true。"
        )
        try:
            structured_llm = self.llm.with_structured_output(DeepRouteDecision)
            decision = structured_llm.invoke([
                HumanMessage(
                    content=(
                        f"{routing_prompt}\n\n"
                        f"预设提示：{self.agent_config.preset_prompt}\n\n"
                        f"用户任务：{query}"
                    )
                )
            ])
            if isinstance(decision, DeepRouteDecision):
                normalized = decision
            elif isinstance(decision, dict):
                normalized = DeepRouteDecision(**decision)
            else:
                normalized = DeepRouteDecision()
        except Exception:
            logger.debug("结构化路由判断失败，回退到启发式策略", exc_info=True)
            normalized = self._heuristic_deep_route(query)

        if normalized.need_execute or normalized.need_file_io or normalized.need_artifact_output:
            normalized.need_sandbox = True
        if not normalized.summary:
            normalized.summary = (
                "需要沙箱执行"
                if normalized.need_sandbox
                else "无需沙箱，使用普通深度思考"
            )
        return normalized

    @classmethod
    def _is_explicit_artifact_request(cls, query: str) -> bool:
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return False

        if ArtifactPolicy.infer_requested_artifact_filename(normalized_query):
            return True

        lower_query = normalized_query.lower()
        output_verbs = (
            "保存",
            "导出",
            "另存",
            "写入",
            "生成",
            "输出",
            "下载",
            "附件",
        )
        if not any(keyword in normalized_query for keyword in output_verbs) and not any(
            keyword in lower_query for keyword in ("save", "export", "write", "download", "file", "attachment")
        ):
            return False

        artifact_terms = (
            ".txt",
            ".md",
            ".markdown",
            ".csv",
            ".json",
            ".html",
            ".htm",
            ".docx",
            ".xlsx",
            ".pdf",
            ".py",
            ".ipynb",
            ".log",
            "txt",
            "md",
            "markdown",
            "csv",
            "json",
            "html",
            "docx",
            "xlsx",
            "pdf",
            "文档",
            "文件",
            "附件",
        )
        return any(term in normalized_query or term in lower_query for term in artifact_terms)

    @staticmethod
    def _heuristic_deep_route(query: str) -> DeepRouteDecision:
        normalized_query = query.lower()
        artifact_keywords = [
            "txt", "csv", "json", "markdown", "md", "html", "word", "docx",
            "excel", "xlsx", "pdf", "文件", "附件", "导出", "生成文档", "表格",
        ]
        execute_keywords = [
            "python", "shell", "bash", "脚本", "代码", "运行", "执行", "测试",
            "benchmark", "命令", "程序",
        ]
        file_keywords = [
            "read file", "write file", "edit file", "grep", "glob", "保存", "读取文件",
            "写入文件", "编辑文件", "搜索文件", "目录",
        ]
        subagent_keywords = ["拆分任务", "分步骤", "多任务", "多个子任务", "并行"]

        need_artifact_output = any(keyword in normalized_query for keyword in artifact_keywords)
        need_execute = any(keyword in normalized_query for keyword in execute_keywords)
        need_file_io = need_artifact_output or any(keyword in normalized_query for keyword in file_keywords)
        need_subagent = any(keyword in normalized_query for keyword in subagent_keywords)
        need_sandbox = need_execute or need_file_io or need_artifact_output
        summary = "需要沙箱执行" if need_sandbox else "无需沙箱，使用普通深度思考"
        reason = "启发式判断：涉及代码执行、文件输出或真实文件操作" if need_sandbox else "启发式判断：任务偏文本规划与分析"
        return DeepRouteDecision(
            need_sandbox=need_sandbox,
            need_file_io=need_file_io,
            need_execute=need_execute,
            need_subagent=need_subagent,
            need_artifact_output=need_artifact_output,
            reason=reason,
            summary=summary,
        )

    def _prepare_artifact_markers(self, *, backend: Any, artifact_root: str) -> list[str]:
        execute_method = getattr(backend, "execute", None)
        if not callable(execute_method):
            return []

        marker_name = SandboxPolicy.build_artifact_marker_name(artifact_root)
        fallback_roots = SandboxPolicy.build_fallback_artifact_roots(artifact_root)
        if not fallback_roots:
            return []

        command_segments = []
        for root in fallback_roots:
            marker_path = f"{root}/{marker_name}"
            command_segments.append(
                f"if mkdir -p {shlex.quote(root)} 2>/dev/null; then "
                f": > {shlex.quote(marker_path)} && printf '%s\\n' {shlex.quote(marker_path)}; "
                "fi"
            )

        result = execute_method(" ; ".join(command_segments), timeout=15)
        if getattr(result, "exit_code", 1) != 0:
            logger.warning("准备沙箱产物标记失败，继续使用常规扫描: %s", getattr(result, "output", ""))
            return []

        return self._extract_artifact_paths(getattr(result, "output", ""))

    @staticmethod
    def _extract_artifact_paths(output: Any) -> list[str]:
        return [
            line.strip()
            for line in str(output or "").splitlines()
            if line.strip() and not line.startswith("[stderr]") and line.startswith("/")
        ]

    def _resolve_sandbox_artifact_root(
        self,
        *,
        backend: Any,
        task_id: Any,
    ) -> str:
        default_root = SandboxPolicy.build_default_artifact_root(task_id)
        execute_method = getattr(backend, "execute", None)
        if not callable(execute_method):
            return default_root

        task_id_text = str(task_id)
        probe_command = (
            "for base in /workspace \"$HOME\" /home/user /tmp /mnt/data; do "
            f"if [ -n \"$base\" ] && mkdir -p \"$base/artifacts/{task_id_text}\" 2>/dev/null; then "
            f"printf '%s/artifacts/{task_id_text}' \"$base\"; "
            "exit 0; "
            "fi; "
            "done; "
            "exit 1"
        )
        result = execute_method(probe_command, timeout=15)
        if getattr(result, "exit_code", 1) != 0:
            logger.warning("探测沙箱产物目录失败，回退默认目录: %s", getattr(result, "output", ""))
            return default_root

        detected_root = str(getattr(result, "output", "")).strip()
        return detected_root if detected_root.startswith("/") else default_root

    def _build_deep_agent(
        self,
        *,
        task_id,
        route_decision: DeepRouteDecision,
        timeline: DeepTimelineMiddleware,
    ):
        from deepagents import create_deep_agent  # noqa: PLC0415
        from deepagents.backends import StateBackend  # noqa: PLC0415

        e2b_key = os.environ.get("E2B_API_KEY", "")
        e2b_domain = os.environ.get("E2B_DOMAIN", "")
        sandbox_enabled = bool(route_decision.need_sandbox and e2b_key and e2b_domain)
        sandbox_profile = (os.getenv("SANDBOX_PROFILE") or "").strip().lower()
        sandbox_template_alias = (os.getenv("SANDBOX_TEMPLATE_ALIAS") or "").strip()
        sandbox_fallback_template_alias = (os.getenv("SANDBOX_FALLBACK_TEMPLATE_ALIAS") or "").strip()
        sandbox_timeout = _read_positive_int_env(
            "SANDBOX_TIMEOUT_SECONDS",
            SandboxPolicy.default_sandbox_timeout_seconds,
            minimum=SandboxPolicy.default_sandbox_timeout_seconds,
        )
        execute_timeout = _read_positive_int_env(
            "SANDBOX_EXECUTE_TIMEOUT_SECONDS",
            SandboxPolicy.default_execute_timeout_seconds,
            minimum=SandboxPolicy.default_execute_timeout_seconds,
        )

        sandbox_template_alias = SandboxPolicy.resolve_sandbox_template_alias(
            sandbox_profile,
            sandbox_template_alias,
        )
        sandbox_fallback_template_alias = SandboxPolicy.resolve_sandbox_fallback_template_alias(
            sandbox_fallback_template_alias,
            sandbox_template_alias=sandbox_template_alias,
        )

        artifact_root = SandboxPolicy.build_default_artifact_root(task_id)
        used_sandbox = False
        if sandbox_enabled:
            try:
                from internal.core.agent.backends import BaiduCfcSandboxBackend  # noqa: PLC0415

                backend = BaiduCfcSandboxBackend(
                    api_key=e2b_key,
                    domain=e2b_domain,
                    timeout=execute_timeout,
                    sandbox_timeout=sandbox_timeout,
                    template_alias=sandbox_template_alias or None,
                    fallback_template_alias=sandbox_fallback_template_alias or None,
                )
                if sandbox_template_alias:
                    backend.ensure_ready()
                artifact_root = self._resolve_sandbox_artifact_root(
                    backend=backend,
                    task_id=task_id,
                )
                setattr(
                    backend,
                    "_openagent_artifact_markers",
                    self._prepare_artifact_markers(backend=backend, artifact_root=artifact_root),
                )
                used_sandbox = True
                timeline.publish_step(
                    step_id=uuid.uuid4(),
                    step_type="tool",
                    status="success",
                    title="进入沙箱执行",
                    detail=f"已启用沙箱模板：{sandbox_template_alias or '<default>'}",
                    technical_detail=f"artifact_root={artifact_root}",
                    tool="sandbox",
                )
            except Exception as e:
                logger.warning("沙箱初始化失败，降级为普通深度思考: %s", e)
                timeline.publish_step(
                    step_id=uuid.uuid4(),
                    step_type="tool",
                    status="error",
                    title="沙箱初始化失败",
                    detail="无法创建沙箱，已回退到普通深度思考",
                    technical_detail=f"{type(e).__name__}: {e}",
                    tool="sandbox",
                )
                backend = StateBackend()
                sandbox_enabled = False

        if not sandbox_enabled:
            backend = StateBackend()
            timeline.publish_step(
                step_id=uuid.uuid4(),
                step_type="tool",
                status="success",
                title="使用普通深度思考",
                detail="本次任务未启用沙箱，将使用无执行环境的深度思考模式",
                technical_detail=route_decision.reason,
                tool="state_backend",
            )

        system_prompt = DEEP_THINKING_SYSTEM_PROMPT.format(
            preset_prompt=self.agent_config.preset_prompt,
            long_term_memory="",
        )
        system_prompt += (
            f"\n\n## 本次运行约束\n"
            f"- 是否允许沙箱执行: {'是' if sandbox_enabled else '否'}\n"
            f"- 产物输出目录: {artifact_root}\n"
            f"- 如需生成最终可下载文件，请只写入该目录。\n"
            f"- 生成完文件后，请在最终回答中简要说明文件名称和用途。\n"
            f"- 如需生成配图，默认只保留一张主图；如果已经成功生成且可直接满足需求，不要重复调用图像工具。\n"
            f"- 禁止把沙箱本地路径（如 /workspace、/home/user、/tmp、sandbox:/mnt/data 下的路径）当成下载链接返回给用户。\n"
            f"- 如果生成了附件，只能说明文件名和用途，真实下载链接由系统注入。"
        )
        if not sandbox_enabled:
            system_prompt += "\n- 当前未提供沙箱执行能力，不要调用 execute 解决任务。"

        deepagent_model = self._resolve_deepagents_model()
        deep_agent = create_deep_agent(
            model=deepagent_model,
            tools=list(self.agent_config.tools),
            system_prompt=system_prompt,
            backend=backend,
            middleware=[timeline],
        )
        return deep_agent, backend, artifact_root, used_sandbox

    def _resolve_deepagents_model(self) -> Any:
        """将运行时模型规整为 deepagents 可直接接收的 chat model。"""
        model = self.llm
        if isinstance(model, BaseChatModel):
            return model

        primary_model = getattr(model, "_primary_model", None)
        if isinstance(primary_model, BaseChatModel):
            return primary_model

        raw_model = getattr(model, "_model", None)
        if isinstance(raw_model, BaseChatModel):
            return raw_model

        return model

    def _collect_artifacts(
        self,
        *,
        backend: Any,
        artifact_root: str,
        timeline: DeepTimelineMiddleware,
    ) -> list[dict[str, Any]]:
        execute_method = getattr(backend, "execute", None)
        download_method = getattr(backend, "download_files", None)
        if not callable(execute_method) or not callable(download_method):
            return []

        artifact_paths_step_id = uuid.uuid4()
        timeline.publish_step(
            step_id=artifact_paths_step_id,
            step_type="artifact",
            status="start",
            title="检查生成产物",
            detail=f"扫描目录 {artifact_root}",
                    technical_detail="\n".join(SandboxPolicy.build_candidate_artifact_roots(artifact_root)),
            tool="artifact_scan",
        )

        scan_roots = SandboxPolicy.build_candidate_artifact_roots(artifact_root)
        find_command = SandboxPolicy.build_find_command(scan_roots)
        result = execute_method(find_command, timeout=15)
        if getattr(result, "exit_code", 1) != 0:
            timeline.publish_step(
                step_id=artifact_paths_step_id,
                step_type="artifact",
                status="error",
                title="检查生成产物",
                detail="扫描产物目录失败",
                technical_detail=str(getattr(result, "output", "")),
                tool="artifact_scan",
                latency=0,
            )
            return []

        artifact_paths = self._extract_artifact_paths(getattr(result, "output", ""))
        if not artifact_paths:
            fallback_roots = SandboxPolicy.build_fallback_artifact_roots(artifact_root)
            marker_paths_by_root = {
                os.path.dirname(path): path
                for path in (getattr(backend, "_openagent_artifact_markers", None) or [])
                if path
            }
            if fallback_roots and marker_paths_by_root:
                fallback_find_command = SandboxPolicy.build_find_command(
                    [root for root in fallback_roots if root in marker_paths_by_root],
                    max_depth=1,
                    marker_paths_by_root=marker_paths_by_root,
                )
                fallback_result = execute_method(fallback_find_command, timeout=15)
                if getattr(fallback_result, "exit_code", 1) == 0:
                    artifact_paths = self._extract_artifact_paths(getattr(fallback_result, "output", ""))
        if not artifact_paths:
            timeline.publish_step(
                step_id=artifact_paths_step_id,
                step_type="artifact",
                status="success",
                title="检查生成产物",
                detail="本次未生成可下载产物",
                tool="artifact_scan",
                latency=0,
            )
            return []

        timeline.publish_step(
            step_id=artifact_paths_step_id,
            step_type="artifact",
            status="success",
            title="检查生成产物",
            detail=f"发现 {len(artifact_paths)} 个产物文件",
            technical_detail="\n".join(artifact_paths[:20]),
            tool="artifact_scan",
            latency=0,
        )

        responses = download_method(artifact_paths)
        artifacts: list[dict[str, Any]] = []

        flask_app = self.agent_config.runtime_flask_app
        app_context = nullcontext()
        if flask_app is not None and not has_app_context():
            app_context = flask_app.app_context()

        with app_context:
            from app.http.module import injector  # noqa: PLC0415
            from internal.service import CosService  # noqa: PLC0415

            cos_service = injector.get(CosService)
            for response in responses:
                if getattr(response, "error", None) or getattr(response, "content", None) is None:
                    timeline.publish_step(
                        step_id=uuid.uuid4(),
                        step_type="artifact",
                        status="error",
                        title="持久化产物失败",
                        detail=f"无法下载沙箱产物：{getattr(response, 'path', '')}",
                        technical_detail=str(getattr(response, "error", "")),
                        tool="artifact_download",
                    )
                    continue

                artifact_path = str(response.path)
                artifact_name = os.path.basename(artifact_path)
                mime_type = mimetypes.guess_type(artifact_name)[0] or "application/octet-stream"
                try:
                    upload_file = cos_service.upload_bytes(
                        filename=artifact_name,
                        content=response.content,
                        account_id=self.agent_config.user_id,
                        mime_type=mime_type,
                        folder="artifacts",
                    )
                    artifact = {
                        "id": str(upload_file.id),
                        "name": upload_file.name,
                        "path": artifact_path,
                        "size": upload_file.size,
                        "extension": upload_file.extension,
                        "mime_type": upload_file.mime_type,
                        "url": cos_service.get_file_url(upload_file.key, download_name=upload_file.name),
                    }
                    artifacts.append(artifact)
                    timeline.publish_artifact(artifact_id=uuid.uuid4(), artifact=artifact)
                except Exception as e:
                    timeline.publish_step(
                        step_id=uuid.uuid4(),
                        step_type="artifact",
                        status="error",
                        title="持久化产物失败",
                        detail=f"上传产物失败：{artifact_name}",
                        technical_detail=f"{type(e).__name__}: {e}",
                        tool="artifact_upload",
                    )
        return artifacts

    @staticmethod
    def _build_completion_summary(
        *,
        route_decision: DeepRouteDecision,
        used_sandbox: bool,
        deep_answer: str,
        artifacts: list[dict[str, Any]],
    ) -> str:
        summary_parts = [route_decision.summary or "深度思考已完成"]
        if used_sandbox:
            summary_parts.append("执行环境：沙箱")
        elif route_decision.need_sandbox:
            summary_parts.append("执行环境：已回退为无沙箱模式")
        if artifacts:
            summary_parts.append("生成附件：" + "、".join(artifact["name"] for artifact in artifacts[:5]))
        if deep_answer:
            summary_parts.append("已生成最终答复")
        return "；".join(summary_parts)

    @staticmethod
    def _build_thinking_context(
        *,
        route_decision: DeepRouteDecision,
        used_sandbox: bool,
        deep_answer: str,
        artifacts: list[dict[str, Any]],
    ) -> str:
        artifact_summary = ""
        if artifacts:
            artifact_lines = "\n".join(
                f"- {artifact['name']} ({artifact['url']})"
                for artifact in artifacts
            )
            artifact_summary = f"\n\n<generated_artifacts>\n{artifact_lines}\n</generated_artifacts>"

        final_answer_instruction = (
            "以上是深度思考阶段的分析结果。请基于此给用户一个简洁、准确的最终回答。"
            "如果 <generated_artifacts> 存在，只能使用其中的真实下载 URL；"
            "绝不要向用户暴露沙箱本地路径（包括 sandbox:/mnt/data），也不要伪造“点击下载”链接。"
            "如果 <generated_artifacts> 不存在，请明确说明当前没有可下载附件。"
        )

        return (
            f"<deep_execution_summary>\n"
            f"- route: {route_decision.summary or route_decision.reason}\n"
            f"- need_sandbox: {route_decision.need_sandbox}\n"
            f"- used_sandbox: {used_sandbox}\n"
            f"- need_execute: {route_decision.need_execute}\n"
            f"- need_file_io: {route_decision.need_file_io}\n"
            f"- need_subagent: {route_decision.need_subagent}\n"
            f"</deep_execution_summary>\n\n"
            f"<deep_thinking_result>\n{deep_answer}\n</deep_thinking_result>"
            f"{artifact_summary}\n\n"
            f"{final_answer_instruction}"
        )

    @classmethod
    def _sanitize_deep_answer(cls, deep_answer: str, *, artifacts: list[dict[str, Any]]) -> str:
        if not deep_answer:
            return ""

        if ArtifactPolicy.contains_plain_text_artifact_preamble(deep_answer):
            deep_answer = ArtifactPolicy.strip_plain_text_artifact_preamble(deep_answer)

        if "<generated_artifacts>" not in str(deep_answer):
            payload = ArtifactPolicy.extract_write_file_payload(deep_answer)
            if payload is not None:
                _, payload_content = payload
                deep_answer = payload_content

        deep_answer = re.sub(
            r"(?is)<generated_artifacts>.*?</generated_artifacts>",
            "",
            str(deep_answer),
        )
        deep_answer = re.sub(
            r"(?is)<artifact\b[^>]*>.*?</artifact\s*>",
            "",
            deep_answer,
        )

        sanitized_lines: list[str] = []
        for raw_line in str(deep_answer).splitlines():
            line = raw_line.strip()
            if not line:
                sanitized_lines.append(raw_line)
                continue

            if (
                "点击下载" in line
                or "需在沙箱中查看" in line
                or line.startswith("文件路径：")
                or line.startswith("文件路径:")
                or re.search(r"</?(?:[\w.-]+:)?(?:tool_call|invoke|tool|function|parameter|param|arg)\b", line, flags=re.IGNORECASE)
                or "<arg_key>" in line
                or "<arg_value>" in line
            ):
                continue

            if any(
                marker in line
                for marker in (
                    "/workspace/artifacts/",
                    "/home/user/artifacts/",
                    "/tmp/artifacts/",
                    "sandbox:/mnt/data/",
                )
            ):
                continue

            sanitized_lines.append(raw_line)

        sanitized = cls._sanitize_sandbox_artifact_text("\n".join(sanitized_lines).strip())

        if artifacts and sanitized:
            sanitized += "\n\n已生成可下载附件，具体下载链接以后端返回的附件列表为准。"

        return sanitized

    @classmethod
    def _preset_operation_condition(
        cls, state: AgentState
    ) -> Literal["long_term_memory_recall", "__end__"]:
        message = state["messages"][-1]
        if message.type == "ai":
            return END
        return "long_term_memory_recall"
