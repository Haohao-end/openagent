from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage
from langchain_core.outputs import LLMResult

from internal.core.agent.agents.function_call_agent import FunctionCallAgent
from internal.core.agent.agents.react_agent import ReACTAgent
from internal.core.agent.entities.agent_entity import DATASET_RETRIEVAL_TOOL_NAME, AgentConfig, MAX_ITERATION_RESPONSE
from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.core.language_model.entities.model_entity import BaseLanguageModel, ModelFeature
from internal.entity.conversation_entity import InvokeFrom
from internal.exception import FailException


class _Chunk:
    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []

    def __add__(self, other):
        return _Chunk(
            content=f"{self.content}{other.content}",
            tool_calls=self.tool_calls or other.tool_calls,
        )

    def __str__(self):
        return self.content


class _ChunkSetNoneOnAdd:
    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []

    def __iadd__(self, _other):
        # 故意返回 None，用于覆盖 function_call_agent 中 `gathered is None` 分支。
        return None

    def __str__(self):
        return self.content


class _FakeEncoding:
    @staticmethod
    def encode(value):
        return list(str(value))


class _NodeLLM(BaseLanguageModel):
    stream_chunks: list = []
    stream_error: Exception | None = None
    bound_tools: list = []

    def generate_prompt(self, *args, **kwargs):
        return LLMResult(generations=[])

    async def agenerate_prompt(self, *args, **kwargs):
        return LLMResult(generations=[])

    def invoke(self, input, config=None, **kwargs):
        return input

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

    def stream(self, _messages):
        if self.stream_error is not None:
            raise self.stream_error
        for chunk in self.stream_chunks:
            yield chunk


class _FakeQueueManager:
    def __init__(self):
        self.published = []
        self.errors = []

    def publish(self, task_id, thought):
        self.published.append((task_id, thought))

    def publish_error(self, task_id, error):
        self.errors.append((task_id, error))


def _build_agent_config(**overrides):
    base = {
        "user_id": uuid4(),
        "invoke_from": InvokeFrom.WEB_APP,
        "max_iteration_count": 2,
        "preset_prompt": "preset",
        "enable_long_term_memory": False,
        "tools": [],
        "review_config": {
            "enable": False,
            "keywords": [],
            "inputs_config": {"enable": False, "preset_response": ""},
            "outputs_config": {"enable": False},
        },
    }
    base.update(overrides)
    return AgentConfig.model_construct(**base)


def _new_function_call_agent(llm, config=None):
    agent = FunctionCallAgent.model_construct(llm=llm, agent_config=config or _build_agent_config())
    agent._agent_queue_manager = _FakeQueueManager()
    return agent


def _new_react_agent(llm, config=None):
    agent = ReACTAgent.model_construct(llm=llm, agent_config=config or _build_agent_config())
    agent._agent_queue_manager = _FakeQueueManager()
    return agent


def test_function_call_agent_build_agent_should_register_graph(monkeypatch):
    class _FakeGraph:
        def __init__(self, _state):
            self.nodes = []
            self.edges = []
            self.conditional_edges = []
            self.entry = None

        def add_node(self, name, fn):
            self.nodes.append((name, fn))

        def add_edge(self, source, target):
            self.edges.append((source, target))

        def add_conditional_edges(self, source, fn):
            self.conditional_edges.append((source, fn))

        def set_entry_point(self, name):
            self.entry = name

        def compile(self):
            return "compiled-agent"

    monkeypatch.setattr("internal.core.agent.agents.function_call_agent.StateGraph", _FakeGraph)
    agent = object.__new__(FunctionCallAgent)

    compiled = FunctionCallAgent._build_agent(agent)

    assert compiled == "compiled-agent"


def test_function_call_agent_preset_operation_should_short_circuit_when_keyword_hit():
    config = _build_agent_config(
        review_config={
            "enable": True,
            "keywords": ["forbidden"],
            "inputs_config": {"enable": True, "preset_response": "blocked"},
            "outputs_config": {"enable": False},
        }
    )
    agent = _new_function_call_agent(_NodeLLM(features=[]), config)
    task_id = uuid4()
    state = {"task_id": task_id, "messages": [HumanMessage(content="forbidden content")]}

    result = agent._preset_operation_node(state)

    assert result["messages"][0].content == "blocked"
    assert [thought.event for _, thought in agent.agent_queue_manager.published] == [
        QueueEvent.AGENT_MESSAGE,
        QueueEvent.AGENT_END,
    ]


def test_function_call_agent_preset_operation_should_return_empty_when_no_block():
    agent = _new_function_call_agent(_NodeLLM(features=[]), _build_agent_config())
    state = {"task_id": uuid4(), "messages": [HumanMessage(content="normal query")]}

    result = agent._preset_operation_node(state)

    assert result == {"messages": []}
    assert agent.agent_queue_manager.published == []


def test_function_call_agent_preset_operation_should_return_empty_when_review_enabled_but_keyword_not_hit():
    config = _build_agent_config(
        review_config={
            "enable": True,
            "keywords": ["blocked"],
            "inputs_config": {"enable": True, "preset_response": "nope"},
            "outputs_config": {"enable": False},
        }
    )
    agent = _new_function_call_agent(_NodeLLM(features=[]), config)
    state = {"task_id": uuid4(), "messages": [HumanMessage(content="safe text")]}

    result = agent._preset_operation_node(state)

    assert result == {"messages": []}
    assert agent.agent_queue_manager.published == []


def test_function_call_agent_long_term_memory_recall_should_validate_history_shape():
    config = _build_agent_config(enable_long_term_memory=True)
    agent = _new_function_call_agent(_NodeLLM(features=[]), config)
    task_id = uuid4()

    ok_state = {
        "task_id": task_id,
        "messages": [HumanMessage(content="q")],
        "history": [HumanMessage(content="h"), AIMessage(content="a")],
        "long_term_memory": "memory",
    }
    result = agent._long_term_memory_recall_node(ok_state)
    assert isinstance(result["messages"][0], RemoveMessage)
    assert isinstance(result["messages"][1], SystemMessage)
    assert result["messages"][-1].content == "q"
    assert agent.agent_queue_manager.published[0][1].event == QueueEvent.LONG_TERM_MEMORY_RECALL

    bad_state = {
        "task_id": task_id,
        "messages": [HumanMessage(content="q")],
        "history": [HumanMessage(content="odd")],
        "long_term_memory": "memory",
    }
    with pytest.raises(FailException, match="历史消息列表格式错误"):
        agent._long_term_memory_recall_node(bad_state)
    assert agent.agent_queue_manager.errors[-1][1] == "智能体历史消息列表格式错误"

    # 覆盖 enable_long_term_memory=False 与 history 非 list 的分支。
    no_memory_agent = _new_function_call_agent(_NodeLLM(features=[]), _build_agent_config(enable_long_term_memory=False))
    skip_state = {
        "task_id": task_id,
        "messages": [HumanMessage(content="q2")],
        "history": "not-list",
        "long_term_memory": "memory",
    }
    skip_result = no_memory_agent._long_term_memory_recall_node(skip_state)
    assert isinstance(skip_result["messages"][1], SystemMessage)


def test_function_call_agent_llm_node_should_handle_message_and_thought_and_error(monkeypatch):
    monkeypatch.setattr("internal.core.agent.agents.function_call_agent.tiktoken.get_encoding", lambda _name: _FakeEncoding())
    task_id = uuid4()

    config_message = _build_agent_config(
        tools=[SimpleNamespace(name="dummy")],
        review_config={
            "enable": True,
            "keywords": ["world"],
            "inputs_config": {"enable": False, "preset_response": ""},
            "outputs_config": {"enable": True},
        },
    )
    llm_message = _NodeLLM(
        features=[ModelFeature.TOOL_CALL.value],
        metadata={"pricing": {"input": 0.1, "output": 0.2, "unit": 0.001}},
        stream_chunks=[_Chunk("hello "), _Chunk("world")],
    )
    agent_message = _new_function_call_agent(llm_message, config_message)
    state = {"task_id": task_id, "messages": [HumanMessage(content="q")], "iteration_count": 0}
    message_result = agent_message._llm_node(state)
    events = [thought.event for _, thought in agent_message.agent_queue_manager.published]

    assert llm_message.bound_tools == config_message.tools
    assert message_result["iteration_count"] == 1
    assert message_result["messages"][0].content == "hello world"
    assert QueueEvent.AGENT_END in events
    assert any(thought.thought == "**" for _, thought in agent_message.agent_queue_manager.published if thought.event == QueueEvent.AGENT_MESSAGE)

    llm_thought = _NodeLLM(
        features=[],
        metadata={"pricing": {"input": 0.1, "output": 0.2, "unit": 0.001}},
        stream_chunks=[_Chunk("", tool_calls=[{"name": "tool_a", "args": {}}])],
    )
    agent_thought = _new_function_call_agent(llm_thought, _build_agent_config())
    thought_state = {"task_id": task_id, "messages": [HumanMessage(content="q")], "iteration_count": 0}
    thought_result = agent_thought._llm_node(thought_state)
    assert thought_result["iteration_count"] == 1
    assert agent_thought.agent_queue_manager.published[-1][1].event == QueueEvent.AGENT_THOUGHT

    llm_error = _NodeLLM(features=[], stream_error=RuntimeError("llm-broken"))
    agent_error = _new_function_call_agent(llm_error, _build_agent_config())
    with pytest.raises(RuntimeError, match="llm-broken"):
        agent_error._llm_node({"task_id": task_id, "messages": [HumanMessage(content="q")], "iteration_count": 0})
    assert "LLM节点发生错误" in agent_error.agent_queue_manager.errors[0][1]


def test_function_call_agent_llm_node_should_cover_none_chunk_and_no_generation_type(monkeypatch):
    monkeypatch.setattr("internal.core.agent.agents.function_call_agent.tiktoken.get_encoding", lambda _name: _FakeEncoding())
    task_id = uuid4()

    # 1) 覆盖 line170: chunk is None 分支
    llm_with_none = _NodeLLM(
        features=[],
        metadata={"pricing": {"input": 0.1, "output": 0.2, "unit": 0.001}},
        stream_chunks=[None, _Chunk("x")],
    )
    agent_none = _new_function_call_agent(llm_with_none, _build_agent_config())
    result_none = agent_none._llm_node({"task_id": task_id, "messages": [HumanMessage(content="q")], "iteration_count": 0})
    assert result_none["iteration_count"] == 1

    # 2) 覆盖 line176: is_first_chunk=False 且 gathered is None 分支
    llm_gathered_none = _NodeLLM(
        features=[],
        metadata={"pricing": {"input": 0.1, "output": 0.2, "unit": 0.001}},
        stream_chunks=[_ChunkSetNoneOnAdd("a"), _ChunkSetNoneOnAdd("b"), _Chunk("c")],
    )
    agent_gathered_none = _new_function_call_agent(llm_gathered_none, _build_agent_config())
    result_gathered_none = agent_gathered_none._llm_node(
        {"task_id": task_id, "messages": [HumanMessage(content="q")], "iteration_count": 0}
    )
    assert result_gathered_none["messages"][0].content == "c"

    # 3) 覆盖 generation_type 为空，最终既不进 thought 也不进 message
    llm_no_type = _NodeLLM(
        features=[],
        metadata={"pricing": {"input": 0.1, "output": 0.2, "unit": 0.001}},
        stream_chunks=[_Chunk("", tool_calls=[])],
    )
    agent_no_type = _new_function_call_agent(llm_no_type, _build_agent_config())
    result_no_type = agent_no_type._llm_node({"task_id": task_id, "messages": [HumanMessage(content="q")], "iteration_count": 0})
    assert result_no_type["messages"][0].content == ""
    assert agent_no_type.agent_queue_manager.published == []


def test_function_call_agent_llm_node_should_stop_when_iteration_limit_reached():
    agent = _new_function_call_agent(_NodeLLM(features=[]), _build_agent_config(max_iteration_count=0))
    task_id = uuid4()
    result = agent._llm_node({"task_id": task_id, "messages": [HumanMessage(content="q")], "iteration_count": 1})

    assert result["messages"][0].content == MAX_ITERATION_RESPONSE
    assert [thought.event for _, thought in agent.agent_queue_manager.published] == [
        QueueEvent.AGENT_MESSAGE,
        QueueEvent.AGENT_END,
    ]


def test_function_call_agent_tools_node_and_conditions_should_cover_branches():
    class _Tool:
        def __init__(self, name, result=None, error=None):
            self.name = name
            self._result = result
            self._error = error

        def invoke(self, _args):
            if self._error:
                raise self._error
            return self._result

    config = _build_agent_config(
        tools=[
            _Tool("web_search", result={"ok": True}),
            _Tool(DATASET_RETRIEVAL_TOOL_NAME, error=RuntimeError("dataset fail")),
        ]
    )
    agent = _new_function_call_agent(_NodeLLM(features=[]), config)
    task_id = uuid4()
    ai_message = AIMessage(
        content="",
        tool_calls=[
            {"id": "1", "name": "web_search", "args": {"q": "ai"}},
            {"id": "2", "name": DATASET_RETRIEVAL_TOOL_NAME, "args": {"query": "llm"}},
        ],
    )

    result = agent._tools_node({"task_id": task_id, "messages": [ai_message]})

    assert len(result["messages"]) == 2
    assert [thought.event for _, thought in agent.agent_queue_manager.published] == [
        QueueEvent.AGENT_ACTION,
        QueueEvent.DATASET_RETRIEVAL,
    ]
    assert FunctionCallAgent._tools_condition({"messages": [ai_message]}) == "tools"
    assert FunctionCallAgent._tools_condition({"messages": [AIMessage(content="done")]}) == "__end__"
    assert FunctionCallAgent._preset_operation_condition({"messages": [AIMessage(content="stop")]}) == "__end__"
    assert FunctionCallAgent._preset_operation_condition({"messages": [HumanMessage(content="go")]}) == "long_term_memory_recall"


def test_react_agent_should_delegate_and_cover_message_and_tool_json_branches(monkeypatch):
    monkeypatch.setattr("internal.core.agent.agents.react_agent.tiktoken.get_encoding", lambda _name: _FakeEncoding())
    task_id = uuid4()

    delegated = _new_react_agent(_NodeLLM(features=[ModelFeature.TOOL_CALL.value]))
    original_recall = FunctionCallAgent._long_term_memory_recall_node
    monkeypatch.setattr(
        "internal.core.agent.agents.react_agent.FunctionCallAgent._long_term_memory_recall_node",
        lambda self, state: {"delegated": state["task_id"]},
    )
    assert delegated._long_term_memory_recall_node({"task_id": task_id}) == {"delegated": task_id}
    monkeypatch.setattr(
        "internal.core.agent.agents.react_agent.FunctionCallAgent._long_term_memory_recall_node",
        original_recall,
    )

    monkeypatch.setattr(
        "internal.core.agent.agents.react_agent.render_text_description_and_args",
        lambda _tools: "tool-desc",
    )
    llm_react = _NodeLLM(features=[ModelFeature.AGENT_THOUGHT.value])
    react_agent = _new_react_agent(
        llm_react,
        _build_agent_config(tools=[SimpleNamespace(name="t1")], enable_long_term_memory=True),
    )
    recall = react_agent._long_term_memory_recall_node(
        {
            "task_id": task_id,
            "messages": [HumanMessage(content="q")],
            "history": [],
            "long_term_memory": "",
        }
    )
    assert isinstance(recall["messages"][1], SystemMessage)
    assert "tool-desc" in recall["messages"][1].content

    # 覆盖 react long_term_memory 分支与 history extend 分支。
    recall_with_memory = react_agent._long_term_memory_recall_node(
        {
            "task_id": task_id,
            "messages": [HumanMessage(content="q")],
            "history": [HumanMessage(content="h"), AIMessage(content="a")],
            "long_term_memory": "remember this",
        }
    )
    assert isinstance(recall_with_memory["messages"][1], SystemMessage)
    assert isinstance(recall_with_memory["messages"][2], HumanMessage)
    assert react_agent.agent_queue_manager.published[0][1].event == QueueEvent.LONG_TERM_MEMORY_RECALL

    no_tool_llm = _NodeLLM(
        features=[],
        metadata={"pricing": {"input": 0.1, "output": 0.2, "unit": 0.001}},
        stream_chunks=[_Chunk("```json{\"name\":\"search\",\"args\":{\"q\":\"ai\"}}```")],
    )
    react_json = _new_react_agent(no_tool_llm, _build_agent_config())
    json_result = react_json._llm_node({"task_id": task_id, "messages": [HumanMessage(content="q")], "iteration_count": 0})
    assert json_result["messages"][0].tool_calls[0]["name"] == "search"
    assert react_json.agent_queue_manager.published[-1][1].event == QueueEvent.AGENT_THOUGHT

    bad_json_llm = _NodeLLM(
        features=[],
        metadata={"pricing": {"input": 0.1, "output": 0.2, "unit": 0.001}},
        stream_chunks=[_Chunk("```jsonnot-a-json```")],
    )
    react_bad_json = _new_react_agent(bad_json_llm, _build_agent_config())
    bad_json_result = react_bad_json._llm_node(
        {"task_id": task_id, "messages": [HumanMessage(content="q")], "iteration_count": 0}
    )
    assert bad_json_result["messages"][0].content.startswith("```json")
    assert any(thought.event == QueueEvent.AGENT_MESSAGE for _, thought in react_bad_json.agent_queue_manager.published)

    plain_llm = _NodeLLM(
        features=[],
        metadata={"pricing": {"input": 0.1, "output": 0.2, "unit": 0.001}},
        stream_chunks=[_Chunk("hello world"), _Chunk(" tail")],
    )
    plain_agent = _new_react_agent(
        plain_llm,
        _build_agent_config(
            review_config={
                "enable": True,
                "keywords": ["world"],
                "inputs_config": {"enable": False, "preset_response": ""},
                "outputs_config": {"enable": True},
            }
        ),
    )
    plain_result = plain_agent._llm_node({"task_id": task_id, "messages": [HumanMessage(content="q")], "iteration_count": 0})
    assert plain_result["messages"][0].content == "hello world tail"
    assert any(thought.thought == "hello world" for _, thought in plain_agent.agent_queue_manager.published)

    # 覆盖 react 中 generation_type 已是 message 且 review 关闭分支（134->138）。
    plain_no_review = _new_react_agent(
        _NodeLLM(
            features=[],
            metadata={"pricing": {"input": 0.1, "output": 0.2, "unit": 0.001}},
            stream_chunks=[_Chunk("plain message"), _Chunk(" next")],
        ),
        _build_agent_config(),
    )
    plain_no_review_result = plain_no_review._llm_node(
        {"task_id": task_id, "messages": [HumanMessage(content="q")], "iteration_count": 0}
    )
    assert plain_no_review_result["messages"][0].content == "plain message next"

    # 覆盖 react 中短内容(<7)导致 generation_type 一直为空的路径（151->121, 228->250）。
    short_content_agent = _new_react_agent(
        _NodeLLM(
            features=[],
            metadata={"pricing": {"input": 0.1, "output": 0.2, "unit": 0.001}},
            stream_chunks=[_Chunk("a"), _Chunk("b")],
        ),
        _build_agent_config(),
    )
    short_result = short_content_agent._llm_node(
        {"task_id": task_id, "messages": [HumanMessage(content="q")], "iteration_count": 0}
    )
    assert short_result["messages"][0].content == "ab"

    limit_agent = _new_react_agent(_NodeLLM(features=[]), _build_agent_config(max_iteration_count=0))
    limit_result = limit_agent._llm_node(
        {"task_id": task_id, "messages": [HumanMessage(content="q")], "iteration_count": 1}
    )
    assert limit_result["messages"][0].content == MAX_ITERATION_RESPONSE

    delegated_llm = _new_react_agent(_NodeLLM(features=[ModelFeature.TOOL_CALL.value]), _build_agent_config())
    monkeypatch.setattr(
        "internal.core.agent.agents.react_agent.FunctionCallAgent._llm_node",
        lambda self, state: {"delegated": state["iteration_count"]},
    )
    assert delegated_llm._llm_node({"task_id": task_id, "messages": [HumanMessage(content="q")], "iteration_count": 3}) == {
        "delegated": 3
    }


def test_react_agent_long_term_memory_recall_should_raise_for_odd_history():
    agent = _new_react_agent(_NodeLLM(features=[]))
    with pytest.raises(FailException, match="历史消息列表格式错误"):
        agent._long_term_memory_recall_node(
            {
                "task_id": uuid4(),
                "messages": [HumanMessage(content="q")],
                "history": [HumanMessage(content="odd")],
                "long_term_memory": "",
            }
        )
    assert agent.agent_queue_manager.errors[-1][1] == "智能体历史消息列表格式错误"
