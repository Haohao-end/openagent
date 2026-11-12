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
    second_callback.on_tool_start(
        {"name": "private-tool"},
        "PRIVATE TOOL INPUT",
        run_id=uuid4(),
    )

    assert first_context.task_id != second_context.task_id
    assert first_callback is not second_callback
    assert len(first_queue.events) == 1
    assert len(second_queue.events) == 1
    task_id, thought = first_queue.events[0]
    payload = json.loads(thought.observation)
    assert task_id == first_context.task_id
    assert thought.event == QueueEvent.CALLABLE_TRACE
    assert payload["run_id"] == str(run_id)
    assert payload["parent_run_id"] == str(parent_run_id)
    assert payload["inputs"] == {"prompt_count": 1}
    assert "PRIVATE PROMPT" not in thought.observation
    assert "DO-NOT-RECORD" not in thought.observation

    first_context.close()
    first_callback.on_llm_end(object(), run_id=run_id, parent_run_id=parent_run_id)
    second_callback.on_tool_end("PRIVATE TOOL OUTPUT", run_id=uuid4())

    assert len(first_queue.events) == 1
    assert len(second_queue.events) == 2
    second_context.close()
