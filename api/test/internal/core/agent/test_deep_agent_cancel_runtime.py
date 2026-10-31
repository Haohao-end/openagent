from threading import Event, Thread
from uuid import uuid4

import pytest
from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from deepagents.backends.protocol import ExecuteResponse, SandboxBackendProtocol
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool

from internal.core.agent.middleware import DeepTimelineMiddleware


def _call(name, call_id, **args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}])

@pytest.mark.parametrize("use_sandbox", [False, True])
def test_deep_agent_cancellation_blocks_later_tools_without_affecting_other_runs(use_sandbox, monkeypatch):
    monkeypatch.setattr(GenericFakeChatModel, "bind_tools", lambda self, *_args, **_kwargs: self)
    started, release, cancel_one = Event(), Event(), Event()
    second_calls, errors = [], []
    @tool
    def first_tool(request_id: str) -> str:
        """Pause the canceled request."""
        if request_id == "cancelled":
            started.set()
            assert release.wait(5)
        return "first"
    @tool
    def second_tool(request_id: str) -> str:
        """Record the request that dispatched this tool."""
        second_calls.append(request_id)
        return "second"
    class Sandbox(StateBackend, SandboxBackendProtocol):
        @property
        def id(self): return "test-sandbox"
        def execute(self, command: str, *, timeout=None):
            if command == "cancelled":
                started.set()
                assert release.wait(5)
            return ExecuteResponse(output="done", exit_code=0)
        async def aexecute(self, command: str, *, timeout=None):
            return self.execute(command, timeout=timeout)
    backend = Sandbox() if use_sandbox else StateBackend()
    first_name = "execute" if use_sandbox else "first_tool"
    tools = [second_tool] if use_sandbox else [first_tool, second_tool]

    def build(request_id, cancel_event):
        first_args = {"command": request_id} if use_sandbox else {"request_id": request_id}
        model = GenericFakeChatModel(messages=iter([
            _call(first_name, "first", **first_args),
            _call("second_tool", "second", request_id=request_id),
            AIMessage(content="done"),
        ]))
        middleware = DeepTimelineMiddleware(task_id=uuid4(), publisher=lambda *_: None, cancel_event=cancel_event)
        return create_deep_agent(model=model, tools=tools, backend=backend, middleware=[middleware])
    def invoke(agent):
        try: agent.invoke({"messages": [HumanMessage(content="run tools")]})
        except Exception as error: errors.append(error)

    cancelled, normal = build("cancelled", cancel_one), build("normal", Event())
    first = Thread(target=invoke, args=(cancelled,)); first.start()
    assert started.wait(5)
    other = Thread(target=invoke, args=(normal,)); other.start()
    cancel_one.set(); release.set()
    first.join(10); other.join(10)
    assert not first.is_alive() and not other.is_alive() and errors == [] and second_calls == ["normal"]
