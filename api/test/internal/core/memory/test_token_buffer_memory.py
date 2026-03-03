from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage

from internal.core.memory.token_buffer_memory import TokenBufferMemory
import internal.core.memory.token_buffer_memory as memory_module


class _FakeMessageQuery:
    def __init__(self, messages):
        self.messages = messages
        self.limit_count = None

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def all(self):
        return self.messages


class _FakeSession:
    def __init__(self, messages):
        self.query_obj = _FakeMessageQuery(messages)

    def query(self, _model):
        return self.query_obj


class _FakeModelInstance:
    def __init__(self):
        self.calls = []

    def convert_to_human_message(self, query, image_urls):
        self.calls.append((query, image_urls))
        return HumanMessage(content=f"human:{query}")


def test_get_history_prompt_messages_should_return_empty_when_conversation_missing():
    memory = TokenBufferMemory(
        db=SimpleNamespace(session=_FakeSession(messages=[])),
        conversation=None,
        model_instance=_FakeModelInstance(),
    )

    assert memory.get_history_prompt_messages() == []


def test_get_history_prompt_messages_should_build_prompt_and_trim(monkeypatch):
    model_instance = _FakeModelInstance()
    raw_messages = [
        SimpleNamespace(query="q2", image_urls=["u2"], answer="a2"),
        SimpleNamespace(query="q1", image_urls=["u1"], answer="a1"),
    ]
    session = _FakeSession(messages=raw_messages)
    memory = TokenBufferMemory(
        db=SimpleNamespace(session=session),
        conversation=SimpleNamespace(id=1),
        model_instance=model_instance,
    )
    captured = {}

    def _fake_trim_messages(messages, max_tokens, token_counter, strategy, start_on, end_on):
        captured["messages"] = messages
        captured["max_tokens"] = max_tokens
        captured["token_counter"] = token_counter
        captured["strategy"] = strategy
        captured["start_on"] = start_on
        captured["end_on"] = end_on
        return ["trimmed"]

    monkeypatch.setattr(memory_module, "trim_messages", _fake_trim_messages)

    result = memory.get_history_prompt_messages(max_token_limit=321, message_limit=2)

    assert result == ["trimmed"]
    assert session.query_obj.limit_count == 2
    assert model_instance.calls == [("q1", ["u1"]), ("q2", ["u2"])]
    assert isinstance(captured["messages"][0], HumanMessage)
    assert isinstance(captured["messages"][1], AIMessage)
    assert captured["max_tokens"] == 321
    assert captured["token_counter"] is model_instance
    assert captured["strategy"] == "last"
    assert captured["start_on"] == "human"
    assert captured["end_on"] == "ai"
