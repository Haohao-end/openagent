from types import SimpleNamespace
from uuid import uuid4

import pytest
import queue as py_queue
from langchain_core.messages import HumanMessage
from langchain_core.outputs import LLMResult
from pydantic import PrivateAttr

from internal.core.agent.agents.agent_queue_manager import AgentQueueManager
from internal.core.agent.agents.base_agent import BaseAgent
from internal.core.agent.entities.agent_entity import AgentConfig
from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.core.language_model.entities.model_entity import BaseLanguageModel
from internal.entity.conversation_entity import InvokeFrom
from internal.exception import FailException


class _FakeRedis:
    def __init__(self):
        self.store = {}
        self.setex_calls = []

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.setex_calls.append((key, ttl, value))
        self.store[key] = value if isinstance(value, bytes) else str(value).encode("utf-8")


class _FakeInjector:
    def __init__(self, redis_client):
        self.redis_client = redis_client

    def get(self, _cls):
        return self.redis_client


@pytest.mark.parametrize(
    "invoke_from, expected_prefix",
    [
        (InvokeFrom.WEB_APP, "account"),
        (InvokeFrom.SERVICE_API, "end-user"),
    ],
)
def test_agent_queue_manager_queue_should_create_cache_key_and_reuse_queue(monkeypatch, invoke_from, expected_prefix):
    redis_client = _FakeRedis()
    monkeypatch.setattr("app.http.module.injector", _FakeInjector(redis_client))

    user_id = uuid4()
    task_id = uuid4()
    manager = AgentQueueManager(user_id=user_id, invoke_from=invoke_from)

    first_queue = manager.queue(task_id)
    second_queue = manager.queue(task_id)

    assert first_queue is second_queue
    assert len(redis_client.setex_calls) == 1
    cache_key, ttl, cache_value = redis_client.setex_calls[0]
    assert cache_key == manager.generate_task_belong_cache_key(task_id)
    assert ttl == 1800
    assert cache_value == f"{expected_prefix}-{user_id}"


def test_agent_queue_manager_publish_and_publish_error_should_enqueue_and_stop(monkeypatch):
    redis_client = _FakeRedis()
    monkeypatch.setattr("app.http.module.injector", _FakeInjector(redis_client))

    manager = AgentQueueManager(user_id=uuid4(), invoke_from=InvokeFrom.WEB_APP)
    task_id = uuid4()
    stop_calls = []
    monkeypatch.setattr(manager, "stop_listen", lambda _task_id: stop_calls.append(_task_id))

    manager.publish(
        task_id,
        AgentThought(id=uuid4(), task_id=task_id, event=QueueEvent.AGENT_MESSAGE),
    )
    queued = manager.queue(task_id).get_nowait()
    assert queued.event == QueueEvent.AGENT_MESSAGE
    assert stop_calls == []

    manager.publish_error(task_id, RuntimeError("boom"))
    assert stop_calls == [task_id]


def test_agent_queue_manager_listen_should_yield_items_and_emit_ping(monkeypatch):
    redis_client = _FakeRedis()
    monkeypatch.setattr("app.http.module.injector", _FakeInjector(redis_client))
    manager = AgentQueueManager(user_id=uuid4(), invoke_from=InvokeFrom.WEB_APP)
    task_id = uuid4()
    q = manager.queue(task_id)
    payload = AgentThought(id=uuid4(), task_id=task_id, event=QueueEvent.AGENT_MESSAGE, answer="ok")
    q.put(payload)
    q.put(None)

    emitted = []
    monkeypatch.setattr(manager, "publish", lambda _task_id, thought: emitted.append(thought.event))
    monkeypatch.setattr(manager, "_is_stopped", lambda _task_id: False)
    timeline = iter([0, 11, 11])
    monkeypatch.setattr("internal.core.agent.agents.agent_queue_manager.time.time", lambda: next(timeline))

    items = list(manager.listen(task_id))

    assert items == [payload]
    assert emitted == [QueueEvent.PING.value]


def test_agent_queue_manager_listen_should_emit_timeout_and_stop(monkeypatch):
    redis_client = _FakeRedis()
    monkeypatch.setattr("app.http.module.injector", _FakeInjector(redis_client))
    manager = AgentQueueManager(user_id=uuid4(), invoke_from=InvokeFrom.WEB_APP)
    task_id = uuid4()
    manager.queue(task_id).put(None)
    emitted = []

    monkeypatch.setattr(manager, "publish", lambda _task_id, thought: emitted.append(thought.event))
    monkeypatch.setattr(manager, "_is_stopped", lambda _task_id: True)
    timeline = iter([0, 601])
    monkeypatch.setattr("internal.core.agent.agents.agent_queue_manager.time.time", lambda: next(timeline))

    assert list(manager.listen(task_id)) == []
    assert QueueEvent.TIMEOUT.value in emitted
    assert QueueEvent.STOP.value in emitted


def test_agent_queue_manager_set_stop_flag_should_validate_task_owner(monkeypatch):
    redis_client = _FakeRedis()
    monkeypatch.setattr("app.http.module.injector", _FakeInjector(redis_client))
    task_id = uuid4()
    user_id = uuid4()

    AgentQueueManager.set_stop_flag(task_id, InvokeFrom.WEB_APP, user_id)
    assert redis_client.setex_calls == []

    belong_key = AgentQueueManager.generate_task_belong_cache_key(task_id)
    redis_client.store[belong_key] = f"account-{uuid4()}".encode("utf-8")
    AgentQueueManager.set_stop_flag(task_id, InvokeFrom.WEB_APP, user_id)
    assert redis_client.setex_calls == []

    redis_client.store[belong_key] = f"account-{user_id}".encode("utf-8")
    AgentQueueManager.set_stop_flag(task_id, InvokeFrom.WEB_APP, user_id)
    assert redis_client.setex_calls[-1][0] == AgentQueueManager.generate_task_stopped_cache_key(task_id)
    assert redis_client.setex_calls[-1][1] == 600


def test_agent_queue_manager_should_cover_stop_listen_is_stopped_and_empty_branch(monkeypatch):
    redis_client = _FakeRedis()
    monkeypatch.setattr("app.http.module.injector", _FakeInjector(redis_client))
    manager = AgentQueueManager(user_id=uuid4(), invoke_from=InvokeFrom.WEB_APP)
    task_id = uuid4()

    manager.stop_listen(task_id)
    assert manager.queue(task_id).get_nowait() is None

    stopped_key = manager.generate_task_stopped_cache_key(task_id)
    assert manager._is_stopped(task_id) is False
    redis_client.store[stopped_key] = b"1"
    assert manager._is_stopped(task_id) is True

    class _RaiseThenStopQueue:
        def __init__(self):
            self._count = 0

        def get(self, timeout):
            if self._count == 0:
                self._count += 1
                raise py_queue.Empty()
            return None

    dummy_queue = _RaiseThenStopQueue()
    monkeypatch.setattr(manager, "queue", lambda _task_id: dummy_queue)
    monkeypatch.setattr(manager, "publish", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(manager, "_is_stopped", lambda _task_id: False)
    timeline = iter([0, 0, 0])
    monkeypatch.setattr("internal.core.agent.agents.agent_queue_manager.time.time", lambda: next(timeline))

    assert list(manager.listen(task_id)) == []


class _DummyLLM(BaseLanguageModel):
    def generate_prompt(self, *args, **kwargs):
        return LLMResult(generations=[])

    async def agenerate_prompt(self, *args, **kwargs):
        return LLMResult(generations=[])

    def invoke(self, input, config=None, **kwargs):
        return input


class _DummyAgent(BaseAgent):
    _invoke_payloads: list = PrivateAttr(default_factory=list)

    def _build_agent(self):
        def _invoke(payload):
            self._invoke_payloads.append(payload)

        return SimpleNamespace(invoke=_invoke)


def test_base_agent_stream_should_prepare_state_and_delegate_to_queue(monkeypatch):
    class _FakeQueueManager:
        def __init__(self, user_id, invoke_from):
            self.user_id = user_id
            self.invoke_from = invoke_from
            self.listen_calls = []

        def listen(self, task_id):
            self.listen_calls.append(task_id)
            yield AgentThought(id=uuid4(), task_id=task_id, event=QueueEvent.AGENT_MESSAGE, answer="A")

    class _FakeThread:
        def __init__(self, target, args):
            self.target = target
            self.args = args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr("internal.core.agent.agents.base_agent.AgentQueueManager", _FakeQueueManager)
    monkeypatch.setattr("internal.core.agent.agents.base_agent.Thread", _FakeThread)
    config = AgentConfig(user_id=uuid4(), invoke_from=InvokeFrom.WEB_APP)
    agent = _DummyAgent(llm=_DummyLLM(features=[]), agent_config=config)
    input_state = {"messages": [HumanMessage(content="hi")]}

    thoughts = list(agent.stream(input_state))

    assert len(thoughts) == 1
    assert "task_id" in input_state
    assert input_state["history"] == []
    assert input_state["iteration_count"] == 0
    assert agent._invoke_payloads[0]["task_id"] == input_state["task_id"]
    assert agent.agent_queue_manager.listen_calls == [input_state["task_id"]]


def test_base_agent_stream_should_raise_when_agent_missing(monkeypatch):
    class _FakeQueueManager:
        def __init__(self, *_args, **_kwargs):
            pass

        @staticmethod
        def listen(_task_id):
            yield from ()

    monkeypatch.setattr("internal.core.agent.agents.base_agent.AgentQueueManager", _FakeQueueManager)
    config = AgentConfig(user_id=uuid4(), invoke_from=InvokeFrom.WEB_APP)
    agent = _DummyAgent(llm=_DummyLLM(features=[]), agent_config=config)
    agent._agent = None

    with pytest.raises(FailException, match="智能体未成功构建"):
        list(agent.stream({"messages": [HumanMessage(content="hi")]}))


def test_base_agent_build_agent_default_should_raise_not_implemented():
    with pytest.raises(NotImplementedError, match="_build_agent\\(\\)未实现"):
        BaseAgent._build_agent(SimpleNamespace())


def test_base_agent_invoke_should_merge_message_events_and_handle_error_status(monkeypatch):
    class _FakeQueueManager:
        def __init__(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr("internal.core.agent.agents.base_agent.AgentQueueManager", _FakeQueueManager)
    config = AgentConfig(user_id=uuid4(), invoke_from=InvokeFrom.WEB_APP)
    agent = _DummyAgent(llm=_DummyLLM(features=[]), agent_config=config)
    shared_id = uuid4()
    image_message = HumanMessage(
        content=[
            {"type": "text", "text": "query"},
            {"type": "image_url", "image_url": {"url": "https://img/a.png"}},
        ]
    )
    task_id = uuid4()
    thoughts = [
        AgentThought(id=uuid4(), task_id=task_id, event=QueueEvent.PING),
        AgentThought(
            id=shared_id,
            task_id=task_id,
            event=QueueEvent.AGENT_MESSAGE,
            thought="hello ",
            answer="hello ",
            message=[{"role": "user"}],
            latency=1.0,
        ),
        AgentThought(
            id=shared_id,
            task_id=task_id,
            event=QueueEvent.AGENT_MESSAGE,
            thought="world",
            answer="world",
            message=[{"role": "user"}],
            latency=2.0,
        ),
        AgentThought(id=uuid4(), task_id=task_id, event=QueueEvent.AGENT_ACTION, latency=0.5),
        AgentThought(id=uuid4(), task_id=task_id, event=QueueEvent.ERROR, observation="failed"),
    ]
    monkeypatch.setattr(_DummyAgent, "stream", lambda self, _input, _config=None: iter(thoughts))

    result = agent.invoke({"messages": [image_message]})

    assert result.query == "query"
    assert result.image_urls == ["https://img/a.png"]
    assert result.answer == "hello world"
    assert result.status == QueueEvent.ERROR.value
    assert result.error == "failed"
    assert result.message == [{"role": "user"}]
    assert len(result.agent_thoughts) == 3
    assert result.latency == pytest.approx(2.5)


def test_base_agent_invoke_should_support_plain_text_query(monkeypatch):
    class _FakeQueueManager:
        def __init__(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr("internal.core.agent.agents.base_agent.AgentQueueManager", _FakeQueueManager)
    config = AgentConfig(user_id=uuid4(), invoke_from=InvokeFrom.WEB_APP)
    agent = _DummyAgent(llm=_DummyLLM(features=[]), agent_config=config)
    monkeypatch.setattr(_DummyAgent, "stream", lambda self, _input, _config=None: iter([]))

    result = agent.invoke({"messages": [HumanMessage(content="plain query")]})

    assert result.query == "plain query"


def test_base_agent_invoke_should_fallback_when_message_content_is_neither_str_nor_list(monkeypatch):
    class _FakeQueueManager:
        def __init__(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr("internal.core.agent.agents.base_agent.AgentQueueManager", _FakeQueueManager)
    config = AgentConfig(user_id=uuid4(), invoke_from=InvokeFrom.WEB_APP)
    agent = _DummyAgent(llm=_DummyLLM(features=[]), agent_config=config)
    monkeypatch.setattr(_DummyAgent, "stream", lambda self, _input, _config=None: iter([]))

    # HumanMessage 对 content 有严格校验，这里用最小对象直达 BaseAgent 分支逻辑。
    result = agent.invoke({"messages": [SimpleNamespace(content={"unknown": True})]})

    assert result.query == ""
    assert result.image_urls == []


def test_base_agent_invoke_should_handle_non_string_non_list_content(monkeypatch):
    class _FakeQueueManager:
        def __init__(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr("internal.core.agent.agents.base_agent.AgentQueueManager", _FakeQueueManager)
    config = AgentConfig(user_id=uuid4(), invoke_from=InvokeFrom.WEB_APP)
    agent = _DummyAgent(llm=_DummyLLM(features=[]), agent_config=config)
    monkeypatch.setattr(_DummyAgent, "stream", lambda self, _input, _config=None: iter([]))

    # 再补一个非 str/list 的标量分支，确保 isinstance(content, list) 的 false path 稳定覆盖。
    result = agent.invoke({"messages": [SimpleNamespace(content=123)]})

    assert result.query == ""
    assert result.image_urls == []
