import json
from uuid import uuid4

from internal.core.agent.entities.queue_entity import QueueEvent
from internal.core.agent.trace_context import AgentTraceContext


class _FakeQueueManager:
    def __init__(self):
        self.events = []

    def publish(self, task_id, event):
        self.events.append((task_id, event))


def test_agent_trace_context_is_request_scoped_and_keeps_safe_parent_metadata():
    first_queue = _FakeQueueManager()
    second_queue = _FakeQueueManager()
    first_context = AgentTraceContext(first_queue)
    second_context = AgentTraceContext(second_queue)
    run_id, parent_run_id = uuid4(), uuid4()

    first_callback = first_context.runnable_config["callbacks"][0]
    second_callback = second_context.runnable_config["callbacks"][0]
    first_callback.on_llm_start(
        {"name": "private-model"},
        ["PRIVATE PROMPT api_key=DO-NOT-RECORD"],
        run_id=run_id,
        parent_run_id=parent_run_id,
    )
    first_callback.on_llm_new_token("PRIVATE TOKEN", run_id=run_id)
    tool_run_id = uuid4()
    second_callback.on_tool_start(
        {"name": "private-tool"},
        "PRIVATE TOOL INPUT",
        run_id=tool_run_id,
        parent_run_id=parent_run_id,
    )

    assert first_context.task_id != second_context.task_id
    assert first_callback is not second_callback
    assert len(first_queue.events) == 1
    assert len(second_queue.events) == 1

    first_task_id, llm_thought = first_queue.events[0]
    llm_payload = json.loads(llm_thought.observation)
    assert first_task_id == first_context.task_id == llm_thought.task_id
    assert llm_thought.event == QueueEvent.CALLABLE_TRACE
    assert llm_payload["run_id"] == str(run_id)
    assert llm_payload["parent_run_id"] == str(parent_run_id)
    assert llm_payload["inputs"] == {"prompt_count": 1}
    assert "PRIVATE PROMPT" not in llm_thought.observation
    assert "DO-NOT-RECORD" not in llm_thought.observation
    assert "PRIVATE TOKEN" not in llm_thought.observation

    second_task_id, tool_thought = second_queue.events[0]
    tool_payload = json.loads(tool_thought.observation)
    assert second_task_id == second_context.task_id == tool_thought.task_id
    assert tool_payload["run_id"] == str(tool_run_id)
    assert tool_payload["parent_run_id"] == str(parent_run_id)
    assert tool_payload["inputs"] == {"input": {"type": "string", "size": 18}}
    assert "PRIVATE TOOL INPUT" not in tool_thought.observation

    first_context.close()
    first_callback.on_llm_end(object(), run_id=run_id, parent_run_id=parent_run_id)
    second_callback.on_tool_end("PRIVATE TOOL OUTPUT", run_id=tool_run_id, parent_run_id=parent_run_id)

    assert len(first_queue.events) == 1
    assert len(second_queue.events) == 2
    tool_end = json.loads(second_queue.events[1][1].observation)
    assert tool_end["phase"] == "end"
    assert tool_end["outputs"] == {"type": "string", "size": 19}
    assert "PRIVATE TOOL OUTPUT" not in second_queue.events[1][1].observation
    second_context.close()
