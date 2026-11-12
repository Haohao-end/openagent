"""Bounded LangChain callback handler for workflow callable traces."""

import queue
import threading
import time
from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

from langchain_core.callbacks import BaseCallbackHandler

from .debug_trace import serialize_trace


class DebugTraceCallbackHandler(BaseCallbackHandler):
    """Collect compact trace events without retaining prompts or model tokens."""

    def __init__(self, max_queue_size: int = 1000):
        if isinstance(max_queue_size, bool) or not isinstance(max_queue_size, int) or max_queue_size < 1:
            raise ValueError("max_queue_size must be a positive integer")
        self._events: queue.Queue[str] = queue.Queue(maxsize=max_queue_size)
        self._lock = threading.Lock()
        self._started_at: dict[str, tuple[float, str, str, Any]] = {}
        self._dropped_events = 0

    @property
    def dropped_events(self) -> int:
        with self._lock:
            return self._dropped_events

    def get_event(self, block: bool = False, timeout: float | None = None) -> str | None:
        """Return one serialized event, or ``None`` when the queue is empty."""
        try:
            return self._events.get(block=block, timeout=timeout if block else None)
        except queue.Empty:
            return None

    def drain(self, limit: int = 100) -> list[str]:
        """Remove at most ``limit`` queued events without blocking."""
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError("limit must be a non-negative integer")
        events = []
        for _ in range(limit):
            event = self.get_event()
            if event is None:
                break
            events.append(event)
        return events

    @staticmethod
    def _id(value: Any) -> str | None:
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, str) and value and len(value) <= 128:
            return value
        return None

    @staticmethod
    def _name(serialized: Any, fallback: str) -> str:
        if isinstance(serialized, Mapping):
            name = serialized.get("name")
            if isinstance(name, str) and name:
                return name
            identifier = serialized.get("id")
            if isinstance(identifier, (list, tuple)) and identifier:
                name = identifier[-1]
                if isinstance(name, str) and name:
                    return name
        return fallback

    @staticmethod
    def _summary(value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            kind = "mapping"
        elif isinstance(value, str):
            kind = "string"
        elif isinstance(value, (list, tuple)):
            kind = "sequence"
        elif value is None:
            kind = "none"
        else:
            kind = type(value).__name__[:64]
        try:
            size = len(value)
        except Exception:
            size = None
        return {"type": kind, "size": size}

    def _publish(
        self,
        run_type: str,
        phase: str,
        name: str,
        run_id: Any,
        parent_run_id: Any,
        inputs: Any = None,
        outputs: Any = None,
        error: Any = None,
        latency_ms: float | None = None,
    ) -> None:
        safe_run_id = self._id(run_id)
        if safe_run_id is None:
            self._drop_event()
            return
        event = {
            "schema_version": 1,
            "event_id": uuid4().hex,
            "run_id": safe_run_id,
            "parent_run_id": self._id(parent_run_id),
            "run_type": run_type,
            "phase": phase,
            "name": name,
            "status": "running" if phase == "start" else "error" if phase == "error" else "success",
            "inputs": inputs,
            "outputs": outputs,
            "error": error,
            "latency_ms": latency_ms,
        }
        try:
            serialized = serialize_trace(event)
            self._events.put_nowait(serialized)
        except Exception:
            self._drop_event()

    def _drop_event(self) -> None:
        with self._lock:
            self._dropped_events += 1

    def _start(self, run_type: str, name: str, run_id: Any, parent_run_id: Any, inputs: Any) -> None:
        safe_run_id = self._id(run_id)
        if safe_run_id is None:
            self._drop_event()
            return
        with self._lock:
            if len(self._started_at) >= self._events.maxsize:
                self._started_at.pop(next(iter(self._started_at)))
            self._started_at[safe_run_id] = (time.monotonic(), run_type, name, inputs)
        self._publish(run_type, "start", name, safe_run_id, parent_run_id, inputs=inputs)

    def _finish(
        self,
        run_type: str,
        phase: str,
        name: str,
        run_id: Any,
        parent_run_id: Any,
        outputs: Any = None,
        error: Any = None,
    ) -> None:
        safe_run_id = self._id(run_id)
        if safe_run_id is None:
            self._drop_event()
            return
        with self._lock:
            run_state = self._started_at.pop(safe_run_id, None)
        if run_state is None:
            latency_ms = None
            inputs = None
        else:
            started_at, run_type, name, inputs = run_state
            latency_ms = max(0.0, (time.monotonic() - started_at) * 1000)
        self._publish(
            run_type,
            phase,
            name,
            safe_run_id,
            parent_run_id,
            inputs=inputs,
            outputs=outputs,
            error=error,
            latency_ms=latency_ms,
        )

    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, **kwargs):
        self._start("chain", self._name(serialized, "chain"), run_id, parent_run_id, self._summary(inputs))

    def on_chain_end(self, outputs, *, run_id, parent_run_id=None, **kwargs):
        self._finish("chain", "end", "chain", run_id, parent_run_id, outputs=self._summary(outputs))

    def on_chain_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        self._finish("chain", "error", "chain", run_id, parent_run_id, error=error)

    def on_llm_start(self, serialized, prompts, *, run_id, parent_run_id=None, **kwargs):
        self._start(
            "llm",
            self._name(serialized, "llm"),
            run_id,
            parent_run_id,
            {"prompt_count": self._summary(prompts).get("size")},
        )

    def on_llm_end(self, response, *, run_id, parent_run_id=None, **kwargs):
        self._finish("llm", "end", "llm", run_id, parent_run_id, outputs=self._summary(response))

    def on_llm_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        self._finish("llm", "error", "llm", run_id, parent_run_id, error=error)

    def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, **kwargs):
        self._start(
            "llm",
            self._name(serialized, "chat_model"),
            run_id,
            parent_run_id,
            {"conversation_count": self._summary(messages).get("size")},
        )

    def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None, **kwargs):
        self._start(
            "tool",
            self._name(serialized, "tool"),
            run_id,
            parent_run_id,
            {"input": self._summary(input_str)},
        )

    def on_tool_end(self, output, *, run_id, parent_run_id=None, **kwargs):
        self._finish("tool", "end", "tool", run_id, parent_run_id, outputs=self._summary(output))

    def on_tool_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        self._finish("tool", "error", "tool", run_id, parent_run_id, error=error)

    def on_retriever_start(self, serialized, query, *, run_id, parent_run_id=None, **kwargs):
        # Keep the existing trace schema/UI contract while exposing retriever runs
        # as tool-like calls. Query text can contain user data, so retain only shape.
        self._start(
            "tool",
            self._name(serialized, "retriever"),
            run_id,
            parent_run_id,
            {"query": self._summary(query)},
        )

    def on_retriever_end(self, documents, *, run_id, parent_run_id=None, **kwargs):
        self._finish("tool", "end", "retriever", run_id, parent_run_id, outputs=self._summary(documents))

    def on_retriever_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        self._finish("tool", "error", "retriever", run_id, parent_run_id, error=error)
