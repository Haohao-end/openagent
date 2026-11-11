"""Small, bounded serializer for workflow callable trace events."""

import json
import math
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import unquote

MAX_JSON_BYTES = 32 * 1024
MAX_STRING_LENGTH = 2048
MAX_COLLECTION_ITEMS = 100
MAX_TOTAL_ITEMS = 2048
MAX_DEPTH = 8
MAX_ID_LENGTH = 128
_MAX_VALUE_BYTES = MAX_JSON_BYTES - 8 * 1024 - 2 * 1024
_MIN_CHILD_BYTES = 2 * 1024
_REDACTED = "[REDACTED]"
_TRUNCATED = "[TRUNCATED]"
_SENSITIVE = re.compile(
    r"password|secret|token|api.?key|authorization|cookie|credential|private.?key|signing.?key|ssh.?key|signature",
    re.I,
)
_SENSITIVE_KEY_NAMES = {
    "access_token", "apikey", "auth", "authorization", "client_secret", "cookie", "key", "password",
    "awsaccesskeyid", "credential", "googleaccessid", "private_key", "refresh_token", "secret", "security_token",
    "signing_key", "ssh_key",
    "sig", "signature", "token", "x_api_key", "api_token", "oauth_token", "x_auth_token", "x_mcp_token",
    "x_amz_credential", "x_amz_security_token", "x_amz_signature", "x_goog_credential", "x_goog_signature",
}
_SENSITIVE_KEY_NAMES_NORMALIZED = {key.replace("_", "").replace("-", "") for key in _SENSITIVE_KEY_NAMES}
_BENIGN_TOKEN_KEYS = {
    "maxtokens", "tokencount", "tokenization", "prompttokens", "completiontokens", "totaltokens",
    "inputtokens", "outputtokens",
}
_SENSITIVE_LABEL = (
    r"[^\"'\r\n,;:=]*(?:(?<![A-Za-z0-9])(?:password|secret|token|api.?key|authorization|cookie|credential|"
    r"private.?key|signing.?key|ssh.?key|signature|awsaccesskeyid|googleaccessid)(?![A-Za-z0-9])|"
    r"(?<![A-Za-z0-9])(?:auth|sig|key)(?![A-Za-z0-9]))[^\"'\r\n,;:=]*"
)
_CREDENTIAL_HINT = re.compile(
    r"(?i)(?<![a-z0-9])(?:password|secret|token|api.?key|authorization|cookie|credential|private.?key|signing.?key|"
    r"ssh.?key|signature|awsaccesskeyid|googleaccessid|auth|sig|key)(?![a-z0-9])"
    r"[^\"'\r\n,;:=]{0,128}[\"']?\s*[:=]"
)
_URL_CREDENTIAL = re.compile(r"(?i)([a-z][a-z0-9+.-]*://)[^/\s?#]+@")
_URL_CREDENTIAL_PREFIX = re.compile(r"(?i)([a-z][a-z0-9+.-]*://)[^/\s?#]*$")
_URL_QUERY_PARAMETER = re.compile(r"(?i)([?&#])([^&#\s]+)")
_HEADER_OBJECT = re.compile(
    r"(?P<prefix>[\"']key[\"']\s*:\s*)(?P<label_quote>[\"'])(?P<label>[^\"'\r\n]{1,128})"
    r"(?P=label_quote)(?P<middle>\s*,\s*[\"']value[\"']\s*:\s*)"
    r"(?P<value>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')",
    re.I,
)
_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----.*?(?:-----END (?:[A-Z0-9 ]+ )?PRIVATE KEY-----|$)",
    re.S,
)
_CREDENTIAL = re.compile(
    r"(?i)(?:([\"']" + _SENSITIVE_LABEL + r"[\"']\s*:\s*)"
    r"(\"(?:\\.|[^\"\\])*(?:\"|$)|'(?:\\.|[^'\\])*(?:'|$)|[^,\r\n}\]]+)"
    r"|((?:authorization|proxy-authorization|cookie|set-cookie)\s*[:=]\s*)"
    r"([^\r\n]+)"
    r"|(" + _SENSITIVE_LABEL + r"\s*[:=]\s*)"
    r"(\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[^;\r\n,]+))"
)
_RUN_TYPES = {"chain", "llm", "tool"}
_PHASES = {"start", "end", "error"}
_STATUSES = {"running", "success", "error"}
_REQUIRED = ("schema_version", "event_id", "run_id", "parent_run_id", "run_type", "phase", "name", "status", "inputs", "outputs", "error", "latency_ms")


def _clean_text(value: Any, limit: int) -> str:
    def redact(match: re.Match) -> str:
        group = next(index for index in (1, 3, 5) if match.group(index) is not None)
        prefix = match.group(group)
        label = prefix.strip()
        if label[:1] in {'"', "'"}:
            label = label[1:].split(label[0], 1)[0]
        else:
            label = label.rsplit(":", 1)[0].rsplit("=", 1)[0].strip()
        if label.lower().replace("_", "").replace("-", "") in _BENIGN_TOKEN_KEYS:
            return match.group(0)
        return prefix + ('"[REDACTED]"' if group == 1 else "[REDACTED]")

    truncated = len(value) > limit
    source = value[:limit] if truncated else value
    source = _PRIVATE_KEY_BLOCK.sub(_REDACTED, source)
    source = _URL_CREDENTIAL.sub(r"\1[REDACTED]@", source)
    if truncated:
        source = _URL_CREDENTIAL_PREFIX.sub(r"\1[REDACTED]", source)
    source = _URL_QUERY_PARAMETER.sub(_redact_url_query_parameter, source)
    source = _HEADER_OBJECT.sub(_redact_header_object, source)
    cleaned = _CREDENTIAL.sub(redact, source) if _CREDENTIAL_HINT.search(source) else source
    return cleaned[: limit - len(_TRUNCATED)] + _TRUNCATED if truncated else cleaned


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("_", "").replace("-", "")
    if normalized in _BENIGN_TOKEN_KEYS:
        return False
    if normalized in _SENSITIVE_KEY_NAMES_NORMALIZED:
        return True
    parts = re.findall(r"[A-Za-z0-9]+", key)
    if any(part.lower().replace("_", "").replace("-", "") in _SENSITIVE_KEY_NAMES_NORMALIZED for part in parts):
        return True
    return bool(re.search(r"password|secret|api.?key|authorization|cookie|credential|private.?key|signing.?key|ssh.?key|signature", key, re.I))


def _is_sensitive_pair_label(label: str) -> bool:
    normalized = label.lower().replace("_", "").replace("-", "") if len(label) <= MAX_ID_LENGTH else ""
    if normalized in _BENIGN_TOKEN_KEYS:
        return False
    if normalized in _SENSITIVE_KEY_NAMES_NORMALIZED:
        return True
    sample = label if len(label) <= MAX_ID_LENGTH else label[:MAX_ID_LENGTH] + " " + label[-MAX_ID_LENGTH:]
    return any(
        part.lower().replace("_", "").replace("-", "") in _SENSITIVE_KEY_NAMES_NORMALIZED
        for part in re.findall(r"[A-Za-z0-9]+", sample)
    )


def _redact_url_query_parameter(match: re.Match) -> str:
    prefix, parameter = match.group(1), match.group(2)
    decoded = unquote(parameter)
    raw_key, separator, _ = parameter.partition("=")
    decoded_key = unquote(raw_key) if separator else decoded.partition("=")[0]
    if not _is_sensitive_key(decoded_key):
        return match.group(0)
    if not separator:
        return prefix + "[REDACTED]"
    return prefix + raw_key + "=[REDACTED]"


def _redact_header_object(match: re.Match) -> str:
    if not _is_sensitive_pair_label(match.group("label")):
        return match.group(0)
    quote = match.group("value")[0]
    return (
        match.group("prefix")
        + match.group("label_quote")
        + match.group("label")
        + match.group("label_quote")
        + match.group("middle")
        + quote
        + _REDACTED
        + quote
    )


def _json_char_size(char: str) -> int:
    codepoint = ord(char)
    if char in {'"', "\\"}:
        return 2
    if 32 <= codepoint < 127:
        return 1
    return 6 if codepoint <= 0xFFFF else 12


def _json_string_size(value: str) -> int:
    return 2 + sum(_json_char_size(char) for char in value)


def _take_bytes(size_budget: list[int], size: int) -> bool:
    if size > size_budget[0]:
        return False
    size_budget[0] -= size
    return True


def _bounded_text(value: str, size_budget: list[int]) -> str:
    if _take_bytes(size_budget, _json_string_size(value)):
        return value
    suffix_size = _json_string_size(_TRUNCATED)
    available = size_budget[0] - suffix_size
    if available < 2:
        return _TRUNCATED
    prefix = []
    used = 2
    for char in value:
        char_size = _json_char_size(char)
        if used + char_size > available:
            break
        prefix.append(char)
        used += char_size
    truncated = "".join(prefix) + _TRUNCATED
    if _take_bytes(size_budget, _json_string_size(truncated)):
        return truncated
    return _TRUNCATED


def _marker(value: str, size_budget: list[int]) -> str:
    if _take_bytes(size_budget, _json_string_size(value)):
        return value
    return _TRUNCATED


def _safe(
    value: Any,
    depth: int = 0,
    seen: set[int] | None = None,
    key: str = "",
    budget: list[int] | None = None,
    size_budget: list[int] | None = None,
) -> Any:
    if budget is None:
        budget = [MAX_TOTAL_ITEMS]
    if size_budget is None:
        size_budget = [_MAX_VALUE_BYTES]
    if key and (len(key) > MAX_ID_LENGTH or _is_sensitive_key(key)):
        return _marker(_REDACTED, size_budget)
    if depth >= MAX_DEPTH:
        return _marker(_TRUNCATED, size_budget)
    if budget[0] <= 0:
        return _marker(_TRUNCATED, size_budget)
    budget[0] -= 1
    if value is None or isinstance(value, bool):
        return value if _take_bytes(size_budget, 5 if value is True else 4) else _TRUNCATED
    if isinstance(value, int):
        if value.bit_length() > 1024:
            return _marker("[integer truncated]", size_budget)
        return value if _take_bytes(size_budget, len(str(value))) else _TRUNCATED
    if isinstance(value, float):
        if not math.isfinite(value):
            return None if _take_bytes(size_budget, 4) else _TRUNCATED
        return value if _take_bytes(size_budget, len(repr(value))) else _TRUNCATED
    if isinstance(value, str):
        return _bounded_text(_clean_text(value, MAX_STRING_LENGTH), size_budget)
    if isinstance(value, BaseException):
        return _marker("[error details redacted]", size_budget)
    if seen is None:
        seen = set()
    if isinstance(value, Mapping) or isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in seen:
            return _marker("[CIRCULAR]", size_budget)
        if not _take_bytes(size_budget, 2):
            return _TRUNCATED
        seen.add(identity)
        try:
            if isinstance(value, Mapping):
                result = {}
                sensitive_header_label = None
                if type(value) is dict:
                    candidate_label = value.get("key")
                    if isinstance(candidate_label, str) and _is_sensitive_pair_label(candidate_label):
                        sensitive_header_label = candidate_label
                try:
                    iterator = iter(value.items())
                    for _ in range(MAX_COLLECTION_ITEMS):
                        if budget[0] <= 0 or size_budget[0] < _MIN_CHILD_BYTES:
                            _add_mapping_marker(result, "_truncated", True, size_budget)
                            break
                        try:
                            child_key, child = next(iterator)
                        except StopIteration:
                            break
                        # Never call str/repr on arbitrary mapping keys.
                        safe_key = _safe_mapping_key(child_key, result, size_budget)
                        if safe_key is None:
                            _add_mapping_marker(result, "_truncated", True, size_budget)
                            break
                        if isinstance(child_key, str):
                            child_label = sensitive_header_label if child_key == "value" else child_key
                            result[safe_key] = _safe(child, depth + 1, seen, child_label, budget, size_budget)
                        else:
                            result[safe_key] = _safe(
                                _REDACTED, depth + 1, seen, budget=budget, size_budget=size_budget
                            )
                    else:
                        try:
                            next(iterator)
                        except StopIteration:
                            pass
                        else:
                            _add_mapping_marker(result, "_truncated", True, size_budget)
                except Exception:
                    _add_mapping_marker(result, "_unavailable", True, size_budget)
                return result
            if type(value) in (list, tuple) and len(value) == 2 and isinstance(value[0], (str, bytes)):
                raw_label, child = value
                if isinstance(raw_label, bytes):
                    if len(raw_label) > MAX_ID_LENGTH:
                        if not _take_bytes(size_budget, 1):
                            return _TRUNCATED
                        return [_marker(_REDACTED, size_budget), _marker(_REDACTED, size_budget)]
                    label = raw_label.decode("utf-8", errors="replace")
                else:
                    label = raw_label
                is_header_label = _is_sensitive_pair_label(label)
                if is_header_label:
                    if not _take_bytes(size_budget, 1):
                        return _TRUNCATED
                    return [
                        _bounded_text(_clean_text(label, MAX_STRING_LENGTH), size_budget),
                        _safe(child, depth + 1, seen, label, budget, size_budget),
                    ]
            result = []
            try:
                iterator = iter(value)
                for _ in range(MAX_COLLECTION_ITEMS):
                    if budget[0] <= 0 or size_budget[0] < _MIN_CHILD_BYTES:
                        if result:
                            _take_bytes(size_budget, 1)
                        result.append(_marker(_TRUNCATED, size_budget))
                        break
                    try:
                        item = next(iterator)
                    except StopIteration:
                        break
                    if result and not _take_bytes(size_budget, 1):
                        result.append(_TRUNCATED)
                        break
                    result.append(_safe(item, depth + 1, seen, budget=budget, size_budget=size_budget))
                else:
                    try:
                        next(iterator)
                    except StopIteration:
                        pass
                    else:
                        if result:
                            _take_bytes(size_budget, 1)
                        result.append(_marker(_TRUNCATED, size_budget))
            except Exception:
                if result:
                    _take_bytes(size_budget, 1)
                result.append(_bounded_text("[unavailable]", size_budget))
            return result
        finally:
            seen.remove(identity)
    return _bounded_text(f"[unsupported:{type(value).__name__[:64]}]", size_budget)


def _safe_mapping_key(key: Any, result: dict[str, Any], size_budget: list[int]) -> str | None:
    if not isinstance(key, str):
        base = "[key]"
    elif len(key) > MAX_ID_LENGTH:
        # _clean_text slices before scanning; long-key values are redacted in _safe.
        base = _clean_text(key, MAX_ID_LENGTH)
    elif _is_sensitive_key(key):
        base = _REDACTED
    else:
        base = _clean_text(key, MAX_ID_LENGTH)
    candidate = base
    suffix_index = 2
    while candidate in result:
        suffix = f"~{suffix_index}"
        candidate = base[: MAX_ID_LENGTH - len(suffix)] + suffix
        suffix_index += 1
    separator_size = 1 if result else 0
    if not _take_bytes(size_budget, _json_string_size(candidate) + 1 + separator_size):
        return None
    return candidate


def _add_mapping_marker(result: dict[str, Any], key: str, value: Any, size_budget: list[int]) -> None:
    safe_key = _safe_mapping_key(key, result, size_budget)
    if safe_key is not None and _take_bytes(size_budget, 4):
        result[safe_key] = value


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
    name = event.get("name", "")
    if not isinstance(name, str):
        raise ValueError("invalid name")
    for identifier in ("event_id", "run_id"):
        value = event.get(identifier)
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value) > MAX_ID_LENGTH
            or _SENSITIVE.search(value)
            or _CREDENTIAL.search(value)
        ):
            raise ValueError(f"invalid {identifier}")
    parent_run_id = event.get("parent_run_id")
    if parent_run_id is not None and (
        not isinstance(parent_run_id, str)
        or not parent_run_id.strip()
        or len(parent_run_id) > MAX_ID_LENGTH
        or _SENSITIVE.search(parent_run_id)
        or _CREDENTIAL.search(parent_run_id)
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
        "name": name,
        "status": status,
        "inputs": event.get("inputs"),
        "outputs": event.get("outputs"),
        "error": event.get("error"),
        "latency_ms": latency,
    }
    for key in ("event_id", "run_id", "parent_run_id", "name"):
        value = payload[key]
        limit = 256 if key == "name" else MAX_ID_LENGTH
        payload[key] = _clean_text(value, limit) if key == "name" and isinstance(value, str) else value
    budget = [MAX_TOTAL_ITEMS]
    size_budget = [_MAX_VALUE_BYTES]
    safe = {
        key: _safe(value, key=key, budget=budget, size_budget=size_budget)
        if key in {"inputs", "outputs", "error"}
        else value
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
