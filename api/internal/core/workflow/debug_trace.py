"""Small, bounded serializer for workflow callable trace events."""

import json
import math
import re
from collections.abc import Mapping
from typing import Any

MAX_JSON_BYTES = 32 * 1024
MAX_STRING_LENGTH = 2048
MAX_COLLECTION_ITEMS = 100
MAX_TOTAL_ITEMS = 2048
MAX_DEPTH = 8
MAX_ID_LENGTH = 128
_REDACTED = "[REDACTED]"
_TRUNCATED = "[TRUNCATED]"
_SENSITIVE = re.compile(r"password|secret|token|api.?key|authorization|cookie|credential", re.I)
_CREDENTIAL = re.compile(
    r"(?i)(?:([\"'](?:authorization|proxy-authorization|cookie|set-cookie|api[_-]?key|"
    r"access[_-]?token|refresh[_-]?token|password|secret|token|credential)[\"']\s*:\s*)"
    r"(\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[^,\r\n}\]]+)"
    r"|((?:authorization|proxy-authorization|cookie|set-cookie)\s*[:=]\s*)"
    r"([^\r\n]+)"
    r"|((?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret|token|credential)\s*[:=]\s*)"
    r"([^\s,;]+))"
)
_RUN_TYPES = {"chain", "llm", "tool"}
_PHASES = {"start", "end", "error"}
_STATUSES = {"running", "success", "error"}
_REQUIRED = ("schema_version", "event_id", "run_id", "parent_run_id", "run_type", "phase", "name", "status", "inputs", "outputs", "error", "latency_ms")


def _clean_text(value: Any, limit: int) -> str:
    def redact(match: re.Match) -> str:
        prefix = next(group for group in (1, 3, 5) if match.group(group) is not None)
        return match.group(prefix) + ('"[REDACTED]"' if prefix == 1 else "[REDACTED]")

    cleaned = _CREDENTIAL.sub(redact, value)
    return cleaned[: limit - len(_TRUNCATED)] + _TRUNCATED if len(cleaned) > limit else cleaned


def _safe(
    value: Any,
    depth: int = 0,
    seen: set[int] | None = None,
    key: str = "",
    budget: list[int] | None = None,
) -> Any:
    if _SENSITIVE.search(key):
        return _REDACTED
    if depth >= MAX_DEPTH:
        return _TRUNCATED
    if budget is None:
        budget = [MAX_TOTAL_ITEMS]
    if budget[0] <= 0:
        return _TRUNCATED
    budget[0] -= 1
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value if value.bit_length() <= 1024 else "[integer truncated]"
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        return _clean_text(value, MAX_STRING_LENGTH)
    if isinstance(value, BaseException):
        return "[error details redacted]"
    if seen is None:
        seen = set()
    if isinstance(value, Mapping) or isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in seen:
            return "[CIRCULAR]"
        seen.add(identity)
        try:
            if isinstance(value, Mapping):
                result = {}
                try:
                    iterator = iter(value.items())
                    for _ in range(MAX_COLLECTION_ITEMS):
                        try:
                            child_key, child = next(iterator)
                        except StopIteration:
                            break
                        # Never call str/repr on arbitrary mapping keys.
                        safe_key = (
                            _REDACTED if _SENSITIVE.search(child_key)
                            else _clean_text(child_key, MAX_ID_LENGTH)
                        ) if isinstance(child_key, str) else "[key]"
                        result[safe_key] = _safe(
                            child,
                            depth + 1,
                            seen,
                            child_key if isinstance(child_key, str) else "",
                            budget,
                        )
                    else:
                        try:
                            next(iterator)
                        except StopIteration:
                            pass
                        else:
                            result["_truncated"] = True
                except Exception:
                    result["_unavailable"] = True
                return result
            result = []
            try:
                iterator = iter(value)
                for _ in range(MAX_COLLECTION_ITEMS):
                    try:
                        item = next(iterator)
                    except StopIteration:
                        break
                    result.append(_safe(item, depth + 1, seen, budget=budget))
                else:
                    try:
                        next(iterator)
                    except StopIteration:
                        pass
                    else:
                        result.append(_TRUNCATED)
            except Exception:
                result.append("[unavailable]")
            return result
        finally:
            seen.remove(identity)
    return f"[unsupported:{type(value).__name__[:64]}]"


def serialize_trace(event: Mapping[str, Any]) -> str:
    """Serialize a trace event as redacted JSON, bounded to 32 KiB."""
    if not isinstance(event, Mapping):
        raise ValueError("trace event must be a mapping")
    schema_version = event.get("schema_version", 1)
    run_type, phase, status = event.get("run_type"), event.get("phase"), event.get("status")
    latency = event.get("latency_ms")
    if type(schema_version) is not int or schema_version != 1:
        raise ValueError("invalid schema_version")
    if not isinstance(run_type, str) or run_type not in _RUN_TYPES:
        raise ValueError("invalid run_type")
    if not isinstance(phase, str) or phase not in _PHASES:
        raise ValueError("invalid phase")
    if not isinstance(status, str) or status not in _STATUSES:
        raise ValueError("invalid trace metadata")
    for identifier in ("event_id", "run_id"):
        value = event.get(identifier)
        if not isinstance(value, str) or not value.strip() or len(value) > MAX_ID_LENGTH:
            raise ValueError(f"invalid {identifier}")
    parent_run_id = event.get("parent_run_id")
    if parent_run_id is not None and (
        not isinstance(parent_run_id, str) or not parent_run_id.strip() or len(parent_run_id) > MAX_ID_LENGTH
    ):
        raise ValueError("invalid parent_run_id")
    if latency is not None:
        if isinstance(latency, bool) or not isinstance(latency, (int, float)) or latency < 0:
            raise ValueError("invalid latency_ms")
        if isinstance(latency, int):
            if latency.bit_length() > 53:
                raise ValueError("invalid latency_ms")
        elif not math.isfinite(latency):
            raise ValueError("invalid latency_ms")

    payload = {
        "schema_version": schema_version,
        "event_id": event.get("event_id", ""),
        "run_id": event.get("run_id", ""),
        "parent_run_id": event.get("parent_run_id"),
        "run_type": run_type,
        "phase": phase,
        "name": event.get("name", ""),
        "status": status,
        "inputs": event.get("inputs"),
        "outputs": event.get("outputs"),
        "error": event.get("error"),
        "latency_ms": latency,
    }
    for key in ("event_id", "run_id", "parent_run_id", "name"):
        value = payload[key]
        limit = MAX_ID_LENGTH if key != "name" else 256
        payload[key] = _clean_text(value, limit) if isinstance(value, str) else None
    budget = [MAX_TOTAL_ITEMS]
    safe = {
        key: _safe(value, key=key, budget=budget) if key in {"inputs", "outputs", "error"} else value
        for key, value in payload.items()
    }
    result = json.dumps(safe, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    if len(result.encode("utf-8")) > MAX_JSON_BYTES:
        safe["inputs"] = _TRUNCATED
        safe["outputs"] = _TRUNCATED
        safe["error"] = _TRUNCATED
        result = json.dumps(safe, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    if len(result.encode("utf-8")) > MAX_JSON_BYTES:
        raise ValueError("trace exceeds size limit")
    return result
