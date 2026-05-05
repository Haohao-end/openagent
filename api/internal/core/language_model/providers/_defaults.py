import os
from typing import Any


def _resolve_timeout_env(default: float = 120.0) -> float:
    """Resolve timeout env values defensively."""
    raw_value = str(os.getenv("LLM_REQUEST_TIMEOUT", "")).strip()
    if not raw_value:
        return default

    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return default


def apply_default_model_timeout(values: dict[str, Any]) -> dict[str, Any]:
    """Apply a bounded default timeout to OpenAI-compatible model clients."""
    if values.get("timeout") is None and values.get("request_timeout") is None:
        values["timeout"] = _resolve_timeout_env()
    return values
