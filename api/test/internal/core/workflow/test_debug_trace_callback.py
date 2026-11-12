import importlib.util
import json
import sys
import types
from pathlib import Path
from uuid import uuid4

from langchain_core.callbacks import BaseCallbackHandler


API_ROOT = Path(__file__).parents[4]
WORKFLOW_PACKAGE = "_debug_trace_callback_test_package"
WORKFLOW_PATH = API_ROOT / "internal/core/workflow"
package = types.ModuleType(WORKFLOW_PACKAGE)
package.__path__ = [str(WORKFLOW_PATH)]
sys.modules[WORKFLOW_PACKAGE] = package

for module_name in ("debug_trace", "debug_trace_callback"):
    spec = importlib.util.spec_from_file_location(
        f"{WORKFLOW_PACKAGE}.{module_name}", WORKFLOW_PATH / f"{module_name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if module_name == "debug_trace_callback":
        DebugTraceCallbackHandler = module.DebugTraceCallbackHandler

for module_name in ("debug_trace_callback", "debug_trace"):
    sys.modules.pop(f"{WORKFLOW_PACKAGE}.{module_name}", None)
sys.modules.pop(WORKFLOW_PACKAGE, None)


def read_event(handler):
    event = handler.get_event()
    assert event is not None
    return json.loads(event)


def test_handler_inherits_base_handler_and_records_chain_timing_safely():
    handler = DebugTraceCallbackHandler()
    run_id, parent_run_id = uuid4(), uuid4()
    handler.on_chain_start(
        {"name": "outer-chain"},
        {"input": "PRIVATE PROMPT", "api_key": "DO-NOT-RECORD"},
        run_id=run_id,
        parent_run_id=parent_run_id,
    )
    started = read_event(handler)
    assert isinstance(handler, BaseCallbackHandler)
    assert started["run_id"] == str(run_id)
    assert started["parent_run_id"] == str(parent_run_id)
    assert (started["run_type"], started["phase"], started["status"]) == ("chain", "start", "running")
    assert started["name"] == "outer-chain"
    assert started["inputs"] == {"type": "mapping", "size": 2}
    assert "PRIVATE PROMPT" not in json.dumps(started)
    assert "DO-NOT-RECORD" not in json.dumps(started)

    handler.on_chain_end({"answer": "not retained"}, run_id=run_id, parent_run_id=parent_run_id)
    ended = read_event(handler)
    assert ended["phase"] == "end"
    assert ended["name"] == "outer-chain"
    assert ended["inputs"] == started["inputs"]
    assert ended["outputs"] == {"type": "mapping", "size": 1}
    assert ended["latency_ms"] >= 0
    assert handler.dropped_events == 0

    error_run_id = uuid4()
    handler.on_chain_start({"name": "failing-chain"}, {}, run_id=error_run_id)
    read_event(handler)
    handler.on_chain_error(RuntimeError("password=PRIVATE-CHAIN-ERROR"), run_id=error_run_id)
    failed = read_event(handler)
    assert (failed["phase"], failed["status"]) == ("error", "error")
    assert failed["error"] == "[error details redacted]"
    assert "PRIVATE-CHAIN-ERROR" not in json.dumps(failed)


def test_llm_chat_tool_callbacks_capture_lifecycle_without_prompt_or_tokens():
    handler = DebugTraceCallbackHandler()
    llm_run = uuid4()
    handler.on_llm_start(
        {"name": "mock-llm"},
        ["PRIVATE PROMPT", "SECOND PROMPT"],
        run_id=llm_run,
    )
    llm_start = read_event(handler)
    assert llm_start["run_type"] == "llm"
    assert llm_start["inputs"] == {"prompt_count": 2}
    assert "PRIVATE PROMPT" not in json.dumps(llm_start)
    handler.on_llm_end(object(), run_id=llm_run)
    llm_end = read_event(handler)
    assert (llm_end["phase"], llm_end["outputs"]["type"]) == ("end", "object")
    assert llm_end["latency_ms"] >= 0

    chat_run = uuid4()
    handler.on_chat_model_start({"id": ["langchain", "chat_models", "MockChat"]}, [[], []], run_id=chat_run)
    chat_start = read_event(handler)
    assert chat_start["name"] == "MockChat"
    assert chat_start["inputs"] == {"conversation_count": 2}
    handler.on_llm_error(RuntimeError("api_key=PRIVATE-ERROR-SECRET"), run_id=chat_run)
    chat_error = read_event(handler)
    assert chat_error["phase"] == "error"
    assert chat_error["error"] == "[error details redacted]"
    assert "PRIVATE-ERROR-SECRET" not in json.dumps(chat_error)

    tool_run = uuid4()
    handler.on_tool_start({"name": "mock-tool"}, "PRIVATE TOOL INPUT", run_id=tool_run)
    tool_start = read_event(handler)
    assert tool_start["run_type"] == "tool"
    assert tool_start["inputs"] == {"input": {"type": "string", "size": 18}}
    assert "PRIVATE TOOL INPUT" not in json.dumps(tool_start)
    handler.on_tool_end("PRIVATE TOOL OUTPUT", run_id=tool_run)
    tool_end = read_event(handler)
    assert tool_end["outputs"] == {"type": "string", "size": 19}
    failing_run = uuid4()
    handler.on_tool_start({"name": "failing-tool"}, "input", run_id=failing_run)
    read_event(handler)
    handler.on_tool_error(RuntimeError("token=PRIVATE-TOOL-SECRET"), run_id=failing_run)
    tool_error = read_event(handler)
    assert tool_error["phase"] == "error"
    assert tool_error["latency_ms"] >= 0
    assert tool_error["error"] == "[error details redacted]"


def test_queue_is_bounded_nonblocking_and_thread_safe():
    handler = DebugTraceCallbackHandler(max_queue_size=128)

    def record_pair(_):
        run_id = uuid4()
        handler.on_chain_start({}, {}, run_id=run_id)
        handler.on_chain_end({}, run_id=run_id)

    import threading

    workers = [threading.Thread(target=record_pair, args=(index,)) for index in range(20)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    events = [json.loads(item) for item in handler.drain(128)]
    assert len(events) == 40
    assert sum(item["phase"] == "start" for item in events) == 20
    assert sum(item["phase"] == "end" for item in events) == 20

    bounded = DebugTraceCallbackHandler(max_queue_size=1)
    run_id = uuid4()
    bounded.on_chain_start({}, {}, run_id=run_id)
    bounded.on_chain_end({}, run_id=run_id)
    assert json.loads(bounded.get_event())["phase"] == "start"
    assert bounded.get_event() is None
    assert bounded.dropped_events == 1


def test_retriever_callbacks_record_query_shape_and_document_count_only():
    handler = DebugTraceCallbackHandler()
    run_id, parent_run_id = uuid4(), uuid4()
    handler.on_retriever_start(
        None,
        "PRIVATE RETRIEVAL QUERY",
        run_id=run_id,
        parent_run_id=parent_run_id,
        name="vector-search",
    )
    started = read_event(handler)
    assert (started["run_type"], started["phase"], started["name"]) == (
        "tool",
        "start",
        "vector-search",
    )
    assert started["run_id"] == str(run_id)
    assert started["parent_run_id"] == str(parent_run_id)
    assert started["inputs"] == {"query": {"type": "string", "size": 23}}
    assert "PRIVATE RETRIEVAL QUERY" not in json.dumps(started)

    handler.on_retriever_end(
        ["PRIVATE DOCUMENT", "SECOND"],
        run_id=run_id,
        parent_run_id=parent_run_id,
    )
    ended = read_event(handler)
    assert (ended["run_type"], ended["phase"], ended["name"]) == (
        "tool",
        "end",
        "vector-search",
    )
    assert ended["outputs"] == {"type": "sequence", "size": 2}
    assert ended["latency_ms"] >= 0
    assert "PRIVATE DOCUMENT" not in json.dumps(ended)

    failed_run_id = uuid4()
    handler.on_retriever_start({"name": "failing-retriever"}, "query", run_id=failed_run_id)
    read_event(handler)
    handler.on_retriever_error(
        RuntimeError("token=PRIVATE-RETRIEVER-ERROR"),
        run_id=failed_run_id,
    )
    failed = read_event(handler)
    assert (failed["phase"], failed["status"]) == ("error", "error")
    assert failed["error"] == "[error details redacted]"
    assert "PRIVATE-RETRIEVER-ERROR" not in json.dumps(failed)
