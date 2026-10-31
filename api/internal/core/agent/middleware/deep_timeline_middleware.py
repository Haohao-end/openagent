from __future__ import annotations

import mimetypes
import json
import re
import time
import uuid
from collections.abc import Callable
from threading import Event
from typing import Any
from uuid import UUID
from urllib.parse import urlparse

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage
from langchain.tools.tool_node import ToolCallRequest
from langgraph.constants import END
from langgraph.types import Command

from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.core.agent.entities.tool_policy_entity import ToolPolicy


def _stringify(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


class DeepTimelineMiddleware(AgentMiddleware):
    """将 deepagents 的内置工具调用转成可直接渲染的时间线事件。"""

    def __init__(
        self,
        *,
        task_id: UUID,
        publisher: Callable[[UUID, AgentThought], None],
        tool_policy: ToolPolicy | None = None,
        cancel_event: Event | None = None,
    ) -> None:
        super().__init__()
        self.task_id = task_id
        self.publisher = publisher
        self.tool_policy = tool_policy or ToolPolicy()
        self.cancel_event = cancel_event
        self._tool_steps: dict[str, UUID] = {}
        self._latest_todo_step_id: UUID | None = None
        self._latest_todos: list[dict[str, Any]] = []

    def publish_step(
        self,
        *,
        step_id: UUID,
        step_type: str,
        status: str,
        title: str,
        detail: str = "",
        technical_detail: str = "",
        tool: str = "",
        tool_input: dict[str, Any] | None = None,
        latency: float = 0,
    ) -> None:
        payload = dict(tool_input or {})
        extra_timeline = dict(payload.pop("timeline", {}) or {})
        payload["timeline"] = {
            "step_type": step_type,
            "status": status,
            "title": title,
            "detail": detail,
            "technical_detail": technical_detail,
            **extra_timeline,
        }
        self.publisher(
            self.task_id,
            AgentThought(
                id=step_id,
                task_id=self.task_id,
                event=QueueEvent.DEEP_STEP,
                thought=detail,
                observation=technical_detail,
                tool=tool,
                tool_input=payload,
                latency=latency,
            ),
        )

    def publish_artifact(
        self,
        *,
        artifact_id: UUID,
        artifact: dict[str, Any],
        group_id: str = "",
        group_name: str = "生成图片",
    ) -> None:
        payload = dict(artifact)
        if group_id and not str(payload.get("group_id", "") or "").strip():
            payload["group_id"] = str(group_id).strip()
        if group_name and not str(payload.get("group_name", "") or "").strip():
            payload["group_name"] = str(group_name).strip()
        self.publisher(
            self.task_id,
            AgentThought(
                id=artifact_id,
                task_id=self.task_id,
                event=QueueEvent.DEEP_ARTIFACT_CREATED,
                thought=str(payload.get("name", "")),
                observation=str(payload.get("url", "")),
                tool="artifact",
                tool_input={"artifact": payload},
                latency=0,
            ),
        )

    @staticmethod
    def _extract_inline_image_urls(text: str) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for pattern in (
            r"!\[[^\]]*]\((https?://[^\s)]+)\)",
            r"图片\s*\d+\s*:\s*(?:\n\s*)?URL\s*:\s*(https?://[^\s)]+)",
            r"https?://[^\s<>()]+?\.(?:png|jpg|jpeg|gif|webp|bmp|svg|tiff|tif|avif)(?:\?[^\s<>()]*)?",
        ):
            for match in re.findall(pattern, text or "", flags=re.IGNORECASE | re.DOTALL):
                normalized = str(match or "").strip().rstrip(".,;)]}")
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                urls.append(normalized)
        return urls

    @staticmethod
    def _build_image_artifact(image_url: str, *, index: int) -> dict[str, Any]:
        normalized_url = str(image_url or "").strip()
        extension = ""
        normalized_path = urlparse(normalized_url).path.lower()
        for candidate in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".tif", ".tiff", ".avif"):
            if normalized_path.endswith(candidate):
                extension = candidate.lstrip(".")
                break
        mime_type = mimetypes.guess_type(normalized_url)[0] or ""
        artifact: dict[str, Any] = {
            "name": "生成图片" if index == 1 else f"生成图片 {index}",
            "url": normalized_url,
        }
        if extension:
            artifact["extension"] = extension
        if mime_type:
            artifact["mime_type"] = mime_type
        return artifact

    @staticmethod
    def _build_tool_timeline_metadata(
        *,
        phase: str,
        preview: str = "",
        preview_kind: str = "",
        result_preview: str = "",
        result_kind: str = "",
        error_kind: str = "",
        recovered: bool = False,
        recoverable: bool = False,
        output_empty: bool = False,
    ) -> dict[str, Any]:
        return {
            "phase": phase,
            "preview": preview,
            "preview_kind": preview_kind,
            "result_preview": result_preview,
            "result_kind": result_kind,
            "error_kind": error_kind,
            "recovered": recovered,
            "recoverable": recoverable,
            "output_empty": output_empty,
        }

    def publish_complete(
        self,
        self_summary: str,
        *,
        latency: float,
        artifact_count: int,
        total_token_count: int = 0,
        total_price: float = 0.0,
    ) -> None:
        self._publish_final_todo_snapshot()
        self.publisher(
            self.task_id,
            AgentThought(
                id=uuid.uuid4(),
                task_id=self.task_id,
                event=QueueEvent.DEEP_COMPLETE,
                thought=self_summary,
                observation=self_summary,
                tool="deep_complete",
                tool_input={
                    "timeline": {
                        "step_type": "reflection",
                        "status": "success",
                        "title": "整理执行结果",
                        "detail": self_summary,
                        "artifact_count": artifact_count,
                    }
                },
                total_token_count=total_token_count,
                total_price=total_price,
                latency=latency,
            ),
        )

    def _get_step_id(self, tool_call: dict[str, Any]) -> UUID:
        call_id = str(tool_call.get("id", "")).strip()
        if call_id:
            if call_id not in self._tool_steps:
                self._tool_steps[call_id] = uuid.uuid5(uuid.NAMESPACE_URL, f"{self.task_id}:{call_id}")
            return self._tool_steps[call_id]
        return uuid.uuid4()

    @staticmethod
    def _normalize_todo_status(status: Any) -> str:
        normalized = str(status or "").strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "completed": "completed",
            "complete": "completed",
            "done": "completed",
            "success": "completed",
            "succeeded": "completed",
            "finished": "completed",
            "error": "error",
            "failed": "error",
            "fail": "error",
            "failure": "error",
            "in_progress": "in_progress",
            "progress": "in_progress",
            "running": "in_progress",
            "working": "in_progress",
            "doing": "in_progress",
            "start": "in_progress",
            "pending": "pending",
            "todo": "pending",
            "to_do": "pending",
            "wait": "pending",
            "waiting": "pending",
            "not_started": "pending",
        }
        return aliases.get(normalized, "pending")

    @classmethod
    def _normalize_todo_items(cls, todos: Any) -> list[dict[str, Any]]:
        if not isinstance(todos, list):
            return []

        normalized_todos: list[dict[str, Any]] = []
        for index, todo in enumerate(todos):
            if isinstance(todo, dict):
                content = str(
                    todo.get("content")
                    or todo.get("text")
                    or todo.get("description")
                    or todo.get("title")
                    or todo.get("name")
                    or ""
                ).strip()
                title = str(todo.get("title") or todo.get("name") or content).strip()
                if not content and not title:
                    continue
                normalized_todos.append({
                    **todo,
                    "content": content or title,
                    "title": title or content,
                    "status": cls._normalize_todo_status(todo.get("status")),
                    "position": index,
                })
                continue

            text = str(todo or "").strip()
            if text:
                normalized_todos.append({
                    "content": text,
                    "title": text,
                    "status": "pending",
                    "position": index,
                })
        return normalized_todos

    def _remember_todos(self, *, step_id: UUID, tool_args: dict[str, Any]) -> None:
        todos = self._normalize_todo_items(tool_args.get("todos", []))
        if not todos:
            return
        self._latest_todo_step_id = step_id
        self._latest_todos = todos

    def _publish_final_todo_snapshot(self) -> None:
        if not self._latest_todo_step_id or not self._latest_todos:
            return

        finalized_todos = []
        for todo in self._latest_todos:
            status = self._normalize_todo_status(todo.get("status"))
            final_status = "error" if status == "error" else "completed"
            finalized_todos.append({
                **todo,
                "status": final_status,
            })

        snapshot_step_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{self.task_id}:{self._latest_todo_step_id}:final_snapshot",
        )
        detail = "待办事项最终快照"
        self.publish_step(
            step_id=snapshot_step_id,
            step_type="reflection",
            status="success",
            title="待办事项归档",
            detail=detail,
            technical_detail="\n".join(
                f"{index + 1}. {todo.get('content') or todo.get('title') or ''} [{todo.get('status')}]"
                for index, todo in enumerate(finalized_todos)
            ),
            tool="write_todos",
            tool_input={
                "todos": finalized_todos,
                "timeline": {
                    "phase": "final_snapshot",
                    "source_step_id": str(self._latest_todo_step_id),
                },
            },
            latency=0,
        )

    @staticmethod
    def _classify_tool(tool_name: str) -> tuple[str, str]:
        if tool_name == "write_todos":
            return "plan", "拆解任务"
        if tool_name == "task":
            return "subagent", "调用子任务"
        if tool_name == "execute":
            return "tool", "执行代码"
        if tool_name in {"write_file", "save_file"}:
            return "artifact", "写文件"
        return "tool", f"调用工具：{tool_name}"

    @staticmethod
    def _build_start_detail(tool_name: str, args: dict[str, Any]) -> str:
        if tool_name == "write_todos":
            todos = args.get("todos", [])
            if isinstance(todos, list) and todos:
                titles = [
                    str(item.get("title", "")).strip()
                    for item in todos
                    if isinstance(item, dict) and str(item.get("title", "")).strip()
                ]
                if titles:
                    return "已规划任务：" + " / ".join(titles[:8])
            return "正在拆解任务并制定执行计划"

        if tool_name == "execute":
            command = _stringify(args.get("command", ""), "")
            return command[:300] if command else "正在执行代码或命令"

        if tool_name == "task":
            description = _stringify(args.get("description", ""), "")
            subagent_type = _stringify(args.get("subagent_type", ""), "")
            prefix = f"子任务类型：{subagent_type}" if subagent_type else "启动子任务"
            if description:
                return f"{prefix}，{description[:240]}"
            return prefix

        path = args.get("file_path") or args.get("path")
        if path:
            return f"{tool_name} -> {path}"
        pattern = args.get("pattern")
        if pattern:
            return f"{tool_name} -> {pattern}"
        return _stringify(args, default="正在执行工具")[:300]

    @staticmethod
    def _extract_result_content(result: ToolMessage | Command[Any]) -> str:
        if isinstance(result, ToolMessage):
            return _stringify(result.content)
        if isinstance(result, Command):
            update = getattr(result, "update", None) or {}
            messages = update.get("messages", [])
            if messages:
                last_message = messages[-1]
                return _stringify(getattr(last_message, "content", ""))
        return _stringify(result)

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        if self.cancel_event is not None and self.cancel_event.is_set():
            return Command(goto=END)

        tool_name = str(request.tool_call.get("name", ""))
        tool_args = dict(request.tool_call.get("args", {}) or {})
        step_type, title = self._classify_tool(tool_name)
        step_id = self._get_step_id(request.tool_call)
        start_at = time.perf_counter()
        preview = self._build_start_detail(tool_name, tool_args)
        preview_kind = "command" if tool_name == "execute" else "protocol" if tool_name in {"write_file", "save_file"} else "summary"
        result_kind = "stdout" if tool_name == "execute" else "output"
        recoverable = tool_name in {"write_file", "save_file"}

        self.publish_step(
            step_id=step_id,
            step_type=step_type,
            status="start",
            title=title,
            detail=self._build_start_detail(tool_name, tool_args),
            tool=tool_name,
            tool_input={
                **tool_args,
                "timeline": self._build_tool_timeline_metadata(
                    phase="start",
                    preview=preview,
                    preview_kind=preview_kind,
                    result_kind=result_kind,
                    recoverable=recoverable,
                ),
            },
            latency=0,
        )

        try:
            result = handler(request)
        except Exception as e:
            status = "warning" if recoverable else "error"
            error_kind = "protocol_error" if recoverable else "tool_error"
            self.publish_step(
                step_id=step_id,
                step_type=step_type,
                status=status,
                title="写文件协议待修复" if recoverable else title,
                detail="检测到可恢复的写文件协议，等待后续恢复" if recoverable else f"{title}失败",
                technical_detail=f"{type(e).__name__}: {e}",
                tool=tool_name,
                tool_input={
                    **tool_args,
                    "timeline": self._build_tool_timeline_metadata(
                        phase="warning" if recoverable else "error",
                        preview=preview,
                        preview_kind=preview_kind,
                        result_kind=result_kind,
                        error_kind=error_kind,
                        recoverable=recoverable,
                    ),
                },
                latency=time.perf_counter() - start_at,
            )
            raise

        result_preview = self._extract_result_content(result)[:1200]
        status = "error" if isinstance(result, ToolMessage) and getattr(result, "status", "") == "error" else "success"
        error_kind = ""
        if recoverable and status == "error":
            status = "warning"
            error_kind = "protocol_error"
        if status == "success" and tool_name == "write_todos":
            self._remember_todos(step_id=step_id, tool_args=tool_args)

        publish_title = title
        publish_detail = result_preview or preview or f"{title}完成"
        if recoverable and status == "warning":
            publish_title = "写文件协议待修复"
            publish_detail = "检测到可恢复的写文件协议，等待后续恢复"

        self.publish_step(
            step_id=step_id,
            step_type=step_type,
            status=status,
            title=publish_title,
            detail=publish_detail,
            technical_detail=result_preview,
            tool=tool_name,
            tool_input={
                **tool_args,
                "timeline": self._build_tool_timeline_metadata(
                    phase="success" if status == "success" else "warning",
                    preview=preview,
                    preview_kind=preview_kind,
                    result_preview=result_preview,
                    result_kind=result_kind,
                    error_kind=error_kind,
                    recovered=False,
                    recoverable=recoverable,
                    output_empty=not bool(result_preview),
                ),
            },
            latency=time.perf_counter() - start_at,
        )

        if status == "success" and self.tool_policy.is_image_result_tool(tool_name):
            image_urls = self._extract_inline_image_urls(result_preview)
            for image_index, image_url in enumerate(image_urls, start=1):
                self.publish_artifact(
                    artifact_id=uuid.uuid4(),
                    artifact=self._build_image_artifact(image_url, index=image_index),
                    group_id=str(step_id),
                    group_name="生成图片",
                )
        return result
