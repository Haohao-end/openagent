from dataclasses import dataclass
import random
import threading
from types import SimpleNamespace
from uuid import uuid4

import pytest

from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.entity.conversation_entity import MessageStatus
from internal.model import Conversation, Message
from internal.service.conversation_service import ConversationService


_CREATE_EVENTS = {
    QueueEvent.LONG_TERM_MEMORY_RECALL.value,
    QueueEvent.AGENT_THOUGHT.value,
    QueueEvent.AGENT_MESSAGE.value,
    QueueEvent.AGENT_ACTION.value,
    QueueEvent.DATASET_RETRIEVAL.value,
}
_TERMINAL_EVENTS = {
    QueueEvent.TIMEOUT.value,
    QueueEvent.STOP.value,
    QueueEvent.ERROR.value,
}
_RANDOM_EVENT_POOL = [
    QueueEvent.LONG_TERM_MEMORY_RECALL.value,
    QueueEvent.AGENT_THOUGHT.value,
    QueueEvent.AGENT_MESSAGE.value,
    QueueEvent.AGENT_ACTION.value,
    QueueEvent.DATASET_RETRIEVAL.value,
    QueueEvent.AGENT_END.value,
    QueueEvent.PING.value,
    QueueEvent.STOP.value,
    QueueEvent.ERROR.value,
    QueueEvent.TIMEOUT.value,
]


@dataclass
class _ExpectedState:
    create_count: int
    message_answers: list[str]
    message_latencies: list[float]
    summary_count: int
    rename_count: int
    terminal_status: str | None
    terminal_error: str


def _build_agent_thought(
    event: str,
    index: int,
    latency: float,
    *,
    answer: str | None = None,
    observation: str | None = None,
) -> AgentThought:
    if answer is None:
        answer = f"answer-{index}" if event == QueueEvent.AGENT_MESSAGE.value else ""
    if observation is None:
        observation = f"obs-{index}" if event in _TERMINAL_EVENTS else ""

    return AgentThought(
        id=uuid4(),
        task_id=uuid4(),
        event=event,
        answer=answer,
        observation=observation,
        message=[{"role": "assistant", "content": answer}] if answer else [],
        latency=latency,
    )


def _build_service(monkeypatch, conversation, message):
    service = ConversationService(db=SimpleNamespace())

    create_calls = []
    update_calls = []
    summary_calls = []
    rename_calls = []
    lock = threading.Lock()

    def _get(model, _id):
        if model is Conversation:
            return conversation
        if model is Message:
            return message
        raise AssertionError(f"unexpected model: {model}")

    def _create(model, **kwargs):
        with lock:
            create_calls.append((model.__name__, dict(kwargs)))
        return SimpleNamespace(id=uuid4(), **kwargs)

    def _update(target, **kwargs):
        with lock:
            update_calls.append((target, dict(kwargs)))
            for key, value in kwargs.items():
                setattr(target, key, value)
        return target

    def _summary(**kwargs):
        with lock:
            summary_calls.append(dict(kwargs))

    def _rename(**kwargs):
        with lock:
            rename_calls.append(dict(kwargs))
        # 对于非新会话，模拟第一次命名后不再满足默认名称分支。
        if not conversation.is_new:
            conversation.name = "Renamed Topic"

    monkeypatch.setattr(service, "get", _get)
    monkeypatch.setattr(service, "create", _create)
    monkeypatch.setattr(service, "update", _update)
    monkeypatch.setattr(service, "_generate_summary_and_update", _summary)
    monkeypatch.setattr(service, "_generate_conversation_name_and_update", _rename)

    return service, create_calls, update_calls, summary_calls, rename_calls


def _simulate_expected_state(
    agent_thoughts: list[AgentThought],
    *,
    long_term_memory_enabled: bool,
    conversation_is_new: bool,
    conversation_name: str,
) -> _ExpectedState:
    create_count = 0
    total_latency = 0.0
    message_answers: list[str] = []
    message_latencies: list[float] = []
    summary_count = 0
    rename_count = 0
    terminal_status = None
    terminal_error = ""
    current_name = conversation_name

    for thought in agent_thoughts:
        event = thought.event

        if event in _CREATE_EVENTS:
            create_count += 1
            total_latency += thought.latency

        if event == QueueEvent.AGENT_MESSAGE.value:
            message_answers.append(thought.answer)
            message_latencies.append(total_latency)
            if long_term_memory_enabled:
                summary_count += 1
            if conversation_is_new or current_name == "New Conversation":
                rename_count += 1
                if not conversation_is_new:
                    current_name = "Renamed Topic"

        if event in _TERMINAL_EVENTS:
            terminal_status = event
            terminal_error = thought.observation
            break

    return _ExpectedState(
        create_count=create_count,
        message_answers=message_answers,
        message_latencies=message_latencies,
        summary_count=summary_count,
        rename_count=rename_count,
        terminal_status=terminal_status,
        terminal_error=terminal_error,
    )


class TestConversationServiceStateMachine:
    @pytest.mark.parametrize("seed", [3, 7, 13, 29, 43, 71])
    def test_save_agent_thoughts_state_machine_should_match_reference_model(self, monkeypatch, seed):
        rng = random.Random(seed)
        conversation = SimpleNamespace(
            id=uuid4(),
            is_new=rng.choice([True, False]),
            name=rng.choice(["New Conversation", "项目讨论", "自定义主题"]),
            summary="old summary",
        )
        message = SimpleNamespace(
            id=uuid4(),
            query="如何补强测试",
            answer="",
            status=MessageStatus.NORMAL.value,
            error="",
            latency=0.0,
        )
        long_term_memory_enabled = rng.choice([True, False])
        service, create_calls, update_calls, summary_calls, rename_calls = _build_service(
            monkeypatch,
            conversation,
            message,
        )

        agent_thoughts = []
        for index in range(rng.randint(20, 80)):
            event = rng.choice(_RANDOM_EVENT_POOL)
            latency = round(rng.uniform(0.01, 1.5), 4)
            agent_thoughts.append(_build_agent_thought(event, index, latency))

        expected = _simulate_expected_state(
            agent_thoughts,
            long_term_memory_enabled=long_term_memory_enabled,
            conversation_is_new=conversation.is_new,
            conversation_name=conversation.name,
        )

        service.save_agent_thoughts(
            account_id=uuid4(),
            app_id=uuid4(),
            app_config={"long_term_memory": {"enable": long_term_memory_enabled}},
            conversation_id=conversation.id,
            message_id=message.id,
            agent_thoughts=agent_thoughts,
        )

        message_create_calls = [
            kwargs
            for model_name, kwargs in create_calls
            if model_name == "MessageAgentThought"
        ]
        assert len(message_create_calls) == expected.create_count
        assert [call["position"] for call in message_create_calls] == list(
            range(1, expected.create_count + 1)
        )

        answer_updates = [
            kwargs
            for target, kwargs in update_calls
            if target is message and "answer" in kwargs
        ]
        assert len(answer_updates) == len(expected.message_answers)
        assert [kwargs["answer"] for kwargs in answer_updates] == expected.message_answers
        assert [
            pytest.approx(kwargs["latency"]) for kwargs in answer_updates
        ] == [pytest.approx(value) for value in expected.message_latencies]

        if expected.message_answers:
            assert message.answer == expected.message_answers[-1]
            assert message.latency == pytest.approx(expected.message_latencies[-1])
        else:
            assert message.answer == ""
            assert message.latency == pytest.approx(0.0)

        assert len(summary_calls) == expected.summary_count
        assert len(rename_calls) == expected.rename_count

        if expected.terminal_status is None:
            assert message.status == MessageStatus.NORMAL.value
            assert message.error == ""
        else:
            assert message.status == expected.terminal_status
            assert message.error == expected.terminal_error

    def test_save_agent_thoughts_concurrent_conflicts_should_end_in_valid_state(self, monkeypatch):
        conversation = SimpleNamespace(
            id=uuid4(),
            is_new=False,
            name="项目讨论",
            summary="old summary",
        )
        message = SimpleNamespace(
            id=uuid4(),
            query="并发测试",
            answer="",
            status=MessageStatus.NORMAL.value,
            error="",
            latency=0.0,
        )
        service, create_calls, update_calls, summary_calls, rename_calls = _build_service(
            monkeypatch,
            conversation,
            message,
        )

        stream_a = [
            _build_agent_thought(QueueEvent.AGENT_THOUGHT.value, 1, 0.4),
            _build_agent_thought(QueueEvent.AGENT_MESSAGE.value, 2, 0.6, answer="A1"),
            _build_agent_thought(QueueEvent.STOP.value, 3, 0.0, observation="manual stop"),
        ]
        stream_b = [
            _build_agent_thought(QueueEvent.DATASET_RETRIEVAL.value, 4, 0.1),
            _build_agent_thought(QueueEvent.AGENT_MESSAGE.value, 5, 0.2, answer="A2"),
            _build_agent_thought(QueueEvent.ERROR.value, 6, 0.0, observation="runtime error"),
        ]

        barrier = threading.Barrier(3)
        errors = []

        def _worker(agent_thoughts):
            try:
                barrier.wait()
                service.save_agent_thoughts(
                    account_id=uuid4(),
                    app_id=uuid4(),
                    app_config={"long_term_memory": {"enable": True}},
                    conversation_id=conversation.id,
                    message_id=message.id,
                    agent_thoughts=agent_thoughts,
                )
            except Exception as exc:  # pragma: no cover - 调试辅助
                errors.append(exc)

        t1 = threading.Thread(target=_worker, args=(stream_a,))
        t2 = threading.Thread(target=_worker, args=(stream_b,))
        t1.start()
        t2.start()
        barrier.wait()
        t1.join()
        t2.join()

        assert errors == []

        assert len(create_calls) == 4
        assert len(summary_calls) == 2
        assert rename_calls == []

        answer_updates = [
            kwargs
            for target, kwargs in update_calls
            if target is message and "answer" in kwargs
        ]
        terminal_updates = [
            kwargs
            for target, kwargs in update_calls
            if target is message and "status" in kwargs
        ]

        assert len(answer_updates) == 2
        assert len(terminal_updates) == 2
        assert {kwargs["answer"] for kwargs in answer_updates} == {"A1", "A2"}
        assert {kwargs["status"] for kwargs in terminal_updates} == {
            QueueEvent.STOP.value,
            QueueEvent.ERROR.value,
        }

        assert message.answer in {"A1", "A2"}
        assert message.status in {QueueEvent.STOP.value, QueueEvent.ERROR.value}
        assert message.error in {"manual stop", "runtime error"}
        assert any(
            message.latency == pytest.approx(value)
            for value in [1.0, 0.3]
        )

    def test_conversation_name_cache_concurrency_should_be_consistent_and_respect_limit(self):
        original_limit = ConversationService._conversation_name_cache_limit
        try:
            with ConversationService._conversation_name_cache_lock:
                ConversationService._conversation_name_cache.clear()

            # 阶段一：大容量下并发写读，验证线程安全和可见性。
            ConversationService._conversation_name_cache_limit = 5000
            barrier = threading.Barrier(9)
            errors: list[Exception] = []

            def _writer(worker_index: int):
                try:
                    barrier.wait()
                    for index in range(100):
                        conversation_id = uuid4()
                        normalized_query = f"q-{worker_index}-{index}"
                        conversation_name = f"name-{worker_index}-{index}"
                        ConversationService._set_cached_conversation_name(
                            conversation_id,
                            normalized_query,
                            conversation_name,
                        )
                        cached_name = ConversationService._get_cached_conversation_name(
                            conversation_id,
                            normalized_query,
                        )
                        if cached_name != conversation_name:
                            errors.append(
                                AssertionError(
                                    f"cache mismatch: expected={conversation_name}, got={cached_name}"
                                )
                            )
                except Exception as exc:  # pragma: no cover - 调试辅助
                    errors.append(exc)

            threads = [
                threading.Thread(target=_writer, args=(worker_index,))
                for worker_index in range(8)
            ]
            for thread in threads:
                thread.start()
            barrier.wait()
            for thread in threads:
                thread.join()

            assert errors == []
            with ConversationService._conversation_name_cache_lock:
                assert len(ConversationService._conversation_name_cache) == 800

            # 阶段二：压低容量，验证淘汰后长度不会超限，且最新写入可读取。
            ConversationService._conversation_name_cache_limit = 50
            for index in range(300):
                ConversationService._set_cached_conversation_name(
                    uuid4(),
                    f"evict-q-{index}",
                    f"evict-name-{index}",
                )

            with ConversationService._conversation_name_cache_lock:
                assert len(ConversationService._conversation_name_cache) <= 50

            final_id = uuid4()
            ConversationService._set_cached_conversation_name(final_id, "final-q", "final-name")
            assert ConversationService._get_cached_conversation_name(final_id, "final-q") == "final-name"
        finally:
            ConversationService._conversation_name_cache_limit = original_limit
            with ConversationService._conversation_name_cache_lock:
                ConversationService._conversation_name_cache.clear()
