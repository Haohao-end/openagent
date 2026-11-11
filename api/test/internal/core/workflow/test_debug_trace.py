import importlib.util
import json
from pathlib import Path


_MODULE_PATH = Path(__file__).parents[4] / "internal/core/workflow/debug_trace.py"
_SPEC = importlib.util.spec_from_file_location("debug_trace_under_test", _MODULE_PATH)
debug_trace = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(debug_trace)


def event(**updates):
    value = {
        "schema_version": 1,
        "event_id": "event-1",
        "run_id": "run-1",
        "parent_run_id": None,
        "run_type": "llm",
        "phase": "start",
        "name": "model",
        "status": "running",
        "inputs": {},
        "outputs": None,
        "error": None,
        "latency_ms": None,
    }
    value.update(updates)
    return value


def test_metadata_is_complete_bounded_and_validated():
    payload = json.loads(debug_trace.serialize_trace(event(event_id="e" * 128, run_id="r" * 128, name="n" * 1000)))
    assert set(payload) == set(debug_trace._REQUIRED)
    assert len(payload["event_id"]) == len(payload["run_id"]) == 128
    assert len(payload["name"]) == 256
    for field, invalid in (("schema_version", True), ("run_type", "chat_model"), ("phase", "other"), ("status", []), ("run_id", ""), ("event_id", None)):
        with __import__("pytest").raises(ValueError):
            debug_trace.serialize_trace(event(**{field: invalid}))
    with __import__("pytest").raises(ValueError):
        debug_trace.serialize_trace(event(event_id="x" * 129))
    with __import__("pytest").raises(ValueError):
        debug_trace.serialize_trace(event(run_id="prefix" + "x" * 128))
    with __import__("pytest").raises(ValueError):
        debug_trace.serialize_trace(event(run_id="token=first"))
    with __import__("pytest").raises(ValueError):
        debug_trace.serialize_trace(event(event_id="credential=second"))
    with __import__("pytest").raises(ValueError):
        debug_trace.serialize_trace(event(latency_ms=10**10000))


def test_redacts_secret_fields_credentials_and_exception_text():
    secret = "top-secret-token-value"
    quoted_headers = f'{{"Authorization": "Bearer {secret}", "Cookie": "session={secret}", "token": "{secret}"}}'
    message = f'{{"password": "hunter two", "access_token": "{secret}"}} Authorization: Bearer {secret}; Cookie: session={secret}; {quoted_headers}; credential={secret}'
    payload = json.loads(debug_trace.serialize_trace(event(inputs={"api_key": secret, "message": message}, error=ValueError(secret))))
    assert secret not in json.dumps(payload)
    assert "hunter two" not in json.dumps(payload)
    assert "two" not in json.dumps(payload)
    assert payload["inputs"]["[REDACTED]"] == "[REDACTED]"
    assert payload["error"] == "[error details redacted]"
    for label in ("client_secret", "github_token", "x-api-key"):
        value = f'{{"{label}": "PRODSECRET"}}'
        cleaned = json.loads(debug_trace.serialize_trace(event(inputs={"message": value})))
        assert "PRODSECRET" not in json.dumps(cleaned)
    for label in ("database/password", "database password"):
        value = f'{{"{label}": "HUNTER TWO"}}'
        cleaned = json.loads(debug_trace.serialize_trace(event(inputs={"message": value})))
        assert "HUNTER" not in json.dumps(cleaned)
        assert "TWO" not in json.dumps(cleaned)
    for value in ('password="hunter two"', "password=hunter two"):
        cleaned = json.loads(debug_trace.serialize_trace(event(inputs={"message": value})))
        assert "hunter" not in json.dumps(cleaned)
        assert "two" not in json.dumps(cleaned)


def test_bounds_large_mapping_array_and_strings():
    payload = json.loads(debug_trace.serialize_trace(event(inputs={"items": list(range(10000)), "mapping": {str(i): i for i in range(10000)}, "text": "x" * 5000})))
    assert len(payload["inputs"]["items"]) == 101
    assert payload["inputs"]["items"][-1] == "[TRUNCATED]"
    assert payload["inputs"]["mapping"]["_truncated"] is True
    assert len(payload["inputs"]["text"]) <= 2050


def test_sensitive_quoted_value_crossing_string_limit_is_fully_redacted():
    value = '{"password":"' + "x" * 2025 + ",LEAKED-SECRET-value-that-continues"
    payload = json.loads(debug_trace.serialize_trace(event(inputs={"message": value})))
    assert "LEAKED" not in json.dumps(payload)


def test_exact_collection_limit_is_not_marked_truncated():
    payload = json.loads(debug_trace.serialize_trace(event(inputs={"array": list(range(100)), "mapping": {str(i): i for i in range(100)}})))
    assert len(payload["inputs"]["array"]) == 100
    assert "_truncated" not in payload["inputs"]["mapping"]


def test_shared_nested_values_obey_global_traversal_budget():
    shared = [list(range(20)) for _ in range(20)]
    payload = debug_trace.serialize_trace(event(inputs=[shared] * 100))
    assert len(payload.encode("utf-8")) <= debug_trace.MAX_JSON_BYTES
    assert "[TRUNCATED]" in payload


def test_long_sensitive_mapping_key_is_redacted_before_truncation():
    key = "x" * 128 + "password"
    payload = json.loads(debug_trace.serialize_trace(event(inputs={key: "credential-value"})))
    assert "credential-value" not in json.dumps(payload)


def test_redacts_credentials_from_mapping_keys_and_names():
    secret = "secret-value-123"
    payload = json.loads(debug_trace.serialize_trace(event(
        name=f"Authorization: Bearer {secret}",
        inputs={f"Authorization: Bearer {secret}": True},
    )))
    assert secret not in json.dumps(payload)
    assert payload["name"] == "Authorization: [REDACTED]"
    assert "[REDACTED]" in payload["inputs"]


def test_unknown_mapping_key_types_redact_associated_values():
    payload = json.loads(debug_trace.serialize_trace(event(inputs={b"password": "hunter2", 1: "secret-value"})))
    assert "hunter2" not in json.dumps(payload)
    assert "secret-value" not in json.dumps(payload)
    assert payload["inputs"]["[key]"] == "[REDACTED]"


def test_truncated_mapping_keys_do_not_overwrite_entries():
    prefix = "generated-parameter-" + "x" * 130
    payload = json.loads(debug_trace.serialize_trace(event(inputs={prefix + "A": 1, prefix + "B": 2})))
    assert len(payload["inputs"]) == 2
    assert sorted(payload["inputs"].values()) == [1, 2]


def test_handles_self_reference_deep_values_nan_and_infinity():
    circular = []
    circular.append(circular)
    nested = current = {}
    for _ in range(20):
        current["next"] = {}
        current = current["next"]
    payload = json.loads(debug_trace.serialize_trace(event(inputs={"cycle": circular, "deep": nested, "nan": float("nan"), "inf": float("inf")})))
    assert payload["inputs"]["cycle"] == ["[CIRCULAR]"]
    assert payload["inputs"]["nan"] is payload["inputs"]["inf"] is None
    assert "[TRUNCATED]" in json.dumps(payload["inputs"]["deep"])


def test_unknown_objects_are_not_stringified_and_output_obeys_byte_limit():
    class Unsafe:
        def __str__(self):
            raise AssertionError("must not call str")

        __repr__ = __str__

    payload = debug_trace.serialize_trace(event(inputs={"object": Unsafe(), "huge": "x" * 100000, "integer": 10**10000}, outputs="y" * 100000))
    assert len(payload.encode("utf-8")) <= debug_trace.MAX_JSON_BYTES
    assert "[unsupported:Unsafe]" in payload
    assert "[integer truncated]" in payload


def test_large_error_is_truncated_without_losing_trace_identifiers():
    payload = json.loads(debug_trace.serialize_trace(event(error={"diagnostic": ["x" * 2000 for _ in range(100)]})))
    assert payload["event_id"] == "event-1"
    assert payload["run_id"] == "run-1"
    assert payload["error"] == "[TRUNCATED]"


def test_non_string_trace_name_is_rejected():
    with __import__("pytest").raises(ValueError):
        debug_trace.serialize_trace(event(name=["too", "large", "to", "encode"] * 10000))
