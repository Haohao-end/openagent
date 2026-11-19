from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from flask import Flask

from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.entity.conversation_entity import InvokeFrom
from internal.exception import NotFoundException, ValidateErrorException
from internal.model import App, Conversation, Message
from internal.service.conversation_service import ConversationService


def _build_agent_message_thought(answer: str = "hello") -> AgentThought:
    return AgentThought(
        id=uuid4(),
        task_id=uuid4(),
        event=QueueEvent.AGENT_MESSAGE.value,
        answer=answer,
        message=[{"role": "assistant", "content": answer}],
        latency=0.1,
    )


def _build_error_thought(observation: str = "boom") -> AgentThought:
    return AgentThought(
        id=uuid4(),
        task_id=uuid4(),
        event=QueueEvent.ERROR.value,
        observation=observation,
        latency=0.1,
    )


def _build_service(monkeypatch, conversation, message):
    service = ConversationService(db=SimpleNamespace())

    def fake_get(model, _id):
        if model is Conversation:
            return conversation
        if model is Message:
            return message
        raise AssertionError(f"unexpected model: {model}")

    def fake_update(target, **kwargs):
        for key, value in kwargs.items():
            setattr(target, key, value)
        return target

    monkeypatch.setattr(service, "get", fake_get)
    monkeypatch.setattr(service, "create", lambda *_args, **_kwargs: SimpleNamespace())
    monkeypatch.setattr(service, "update", fake_update)

    return service


class TestConversationServiceSaveAgentThoughts:
    def test_should_rename_when_conversation_is_new(self, monkeypatch):
        conversation = SimpleNamespace(id=uuid4(), is_new=True, name="自定义会话", summary="")
        message = SimpleNamespace(id=uuid4(), query="你好", answer="")
        service = _build_service(monkeypatch, conversation, message)

        rename_calls = []
        monkeypatch.setattr(
            service,
            "_generate_conversation_name_and_update",
            lambda **kwargs: rename_calls.append(kwargs),
        )
        monkeypatch.setattr(service, "_generate_summary_and_update", lambda **_kwargs: None)

        service.save_agent_thoughts(
            account_id=uuid4(),
            app_id=uuid4(),
            app_config={"long_term_memory": {"enable": False}},
            conversation_id=conversation.id,
            message_id=message.id,
            agent_thoughts=[_build_agent_message_thought()],
        )

        assert len(rename_calls) == 1
        assert rename_calls[0]["conversation_id"] == conversation.id
        assert rename_calls[0]["query"] == "你好"

    def test_should_rename_when_name_is_default_even_if_not_new(self, monkeypatch):
        conversation = SimpleNamespace(id=uuid4(), is_new=False, name="New Conversation", summary="")
        message = SimpleNamespace(id=uuid4(), query="hello", answer="")
        service = _build_service(monkeypatch, conversation, message)

        rename_calls = []
        monkeypatch.setattr(
            service,
            "_generate_conversation_name_and_update",
            lambda **kwargs: rename_calls.append(kwargs),
        )
        monkeypatch.setattr(service, "_generate_summary_and_update", lambda **_kwargs: None)

        service.save_agent_thoughts(
            account_id=uuid4(),
            app_id=uuid4(),
            app_config={"long_term_memory": {"enable": False}},
            conversation_id=conversation.id,
            message_id=message.id,
            agent_thoughts=[_build_agent_message_thought()],
        )

        assert len(rename_calls) == 1
        assert rename_calls[0]["conversation_id"] == conversation.id

    def test_should_not_rename_when_not_new_and_name_is_not_default(self, monkeypatch):
        conversation = SimpleNamespace(id=uuid4(), is_new=False, name="项目讨论", summary="")
        message = SimpleNamespace(id=uuid4(), query="hello", answer="")
        service = _build_service(monkeypatch, conversation, message)

        rename_calls = []
        monkeypatch.setattr(
            service,
            "_generate_conversation_name_and_update",
            lambda **kwargs: rename_calls.append(kwargs),
        )
        monkeypatch.setattr(service, "_generate_summary_and_update", lambda **_kwargs: None)

        service.save_agent_thoughts(
            account_id=uuid4(),
            app_id=uuid4(),
            app_config={"long_term_memory": {"enable": False}},
            conversation_id=conversation.id,
            message_id=message.id,
            agent_thoughts=[_build_agent_message_thought()],
        )

        assert rename_calls == []

    def test_should_update_summary_when_long_term_memory_enabled(self, monkeypatch):
        conversation = SimpleNamespace(id=uuid4(), is_new=False, name="自定义", summary="old")
        message = SimpleNamespace(id=uuid4(), query="这个问题", answer="")
        service = _build_service(monkeypatch, conversation, message)

        summary_calls = []
        monkeypatch.setattr(
            service,
            "_generate_summary_and_update",
            lambda **kwargs: summary_calls.append(kwargs),
        )
        monkeypatch.setattr(service, "_generate_conversation_name_and_update", lambda **_kwargs: None)

        service.save_agent_thoughts(
            account_id=uuid4(),
            app_id=uuid4(),
            app_config={"long_term_memory": {"enable": True}},
            conversation_id=conversation.id,
            message_id=message.id,
            agent_thoughts=[_build_agent_message_thought(answer="这是答案")],
        )

        assert len(summary_calls) == 1
        assert summary_calls[0]["conversation_id"] == conversation.id
        assert summary_calls[0]["query"] == "这个问题"
        assert summary_calls[0]["answer"] == "这是答案"

    def test_should_not_log_agent_answer_content(self, monkeypatch, caplog):
        answer = "PRIVATE_CONVERSATION_ANSWER_V47"
        conversation = SimpleNamespace(id=uuid4(), is_new=False, name="existing", summary="")
        message = SimpleNamespace(id=uuid4(), query="question", answer="")
        service = _build_service(monkeypatch, conversation, message)
        caplog.set_level("INFO")

        service.save_agent_thoughts(
            account_id=uuid4(), app_id=uuid4(),
            app_config={"long_term_memory": {"enable": False}},
            conversation_id=conversation.id, message_id=message.id,
            agent_thoughts=[_build_agent_message_thought(answer=answer)],
        )

        assert answer not in caplog.text

    def test_should_mark_message_error_on_error_event(self, monkeypatch):
        conversation = SimpleNamespace(id=uuid4(), is_new=False, name="自定义", summary="")
        message = SimpleNamespace(id=uuid4(), query="hello", answer="", status="", error="")
        service = _build_service(monkeypatch, conversation, message)

        monkeypatch.setattr(service, "_generate_summary_and_update", lambda **_kwargs: None)
        monkeypatch.setattr(service, "_generate_conversation_name_and_update", lambda **_kwargs: None)

        service.save_agent_thoughts(
            account_id=uuid4(),
            app_id=uuid4(),
            app_config={"long_term_memory": {"enable": False}},
            conversation_id=conversation.id,
            message_id=message.id,
            agent_thoughts=[_build_error_thought("agent error")],
        )

        assert message.status == QueueEvent.ERROR.value
        assert message.error == "agent error"


class TestConversationServiceBasics:
    @pytest.fixture
    def app_ctx(self, app):
        app.config["ASSISTANT_AGENT_ID"] = uuid4()
        with app.app_context():
            yield app

    def _build_service(self) -> ConversationService:
        return ConversationService(db=SimpleNamespace(session=SimpleNamespace()))

    @pytest.fixture(autouse=True)
    def _clear_conversation_name_cache(self):
        with ConversationService._conversation_name_cache_lock:
            ConversationService._conversation_name_cache.clear()
        yield
        with ConversationService._conversation_name_cache_lock:
            ConversationService._conversation_name_cache.clear()

    def test_set_cached_conversation_name_should_evict_oldest_when_limit_exceeded(self):
        original_limit = ConversationService._conversation_name_cache_limit
        ConversationService._conversation_name_cache_limit = 1
        try:
            first_id = uuid4()
            second_id = uuid4()
            ConversationService._set_cached_conversation_name(first_id, "q1", "n1")
            ConversationService._set_cached_conversation_name(second_id, "q2", "n2")

            assert ConversationService._get_cached_conversation_name(first_id, "q1") is None
            assert ConversationService._get_cached_conversation_name(second_id, "q2") == "n2"
        finally:
            ConversationService._conversation_name_cache_limit = original_limit

    def test_generate_conversation_name_should_truncate_long_query_and_remove_newline(self, monkeypatch):
        captured_query = {}

        class _Prompt:
            def __or__(self, other):
                return other

        class _StructuredLLM:
            def invoke(self, payload):
                captured_query["value"] = payload["query"]
                return SimpleNamespace(subject="会话标题")

        monkeypatch.setattr(
            "internal.service.conversation_service.ChatPromptTemplate.from_messages",
            lambda _messages: _Prompt(),
        )
        monkeypatch.setattr(
            "internal.service.conversation_service.Chat",
            lambda **_kwargs: SimpleNamespace(
                with_structured_output=lambda _schema: _StructuredLLM(),
            ),
        )

        query = ("a" * 1200) + "\n" + ("b" * 1201)
        name = ConversationService.generate_conversation_name(query)

        normalized_query = captured_query["value"]
        assert name == "会话标题"
        assert "\n" not in normalized_query
        assert "...[TRUNCATED]..." in normalized_query
        assert normalized_query.startswith("a" * 300)
        assert normalized_query.endswith("b" * 300)

    def test_summary_should_build_chain_and_return_new_summary(self, monkeypatch):
        captured = {}

        class _ChainAfterLLM:
            def __or__(self, parser):
                captured["parser"] = parser
                return self

            def invoke(self, payload):
                captured["payload"] = payload
                return "新的摘要结果"

        class _Prompt:
            def __or__(self, llm):
                captured["llm"] = llm
                return _ChainAfterLLM()

        monkeypatch.setattr(
            "internal.service.conversation_service.ChatPromptTemplate.from_template",
            lambda _template: _Prompt(),
        )
        monkeypatch.setattr(
            "internal.service.conversation_service.Chat",
            lambda **kwargs: SimpleNamespace(**kwargs),
        )
        monkeypatch.setattr(
            "internal.service.conversation_service.StrOutputParser",
            lambda: "output-parser",
        )

        summary = ConversationService.summary(
            human_message="用户问题",
            ai_message="模型回答",
            old_summary="旧摘要",
        )

        assert summary == "新的摘要结果"
        assert captured["payload"] == {
            "summary": "旧摘要",
            "new_lines": "Human: 用户问题\nAI: 模型回答",
        }
        assert captured["llm"].model == "deepseek-chat"
        assert captured["parser"] == "output-parser"

    def test_generate_conversation_name_should_fallback_when_subject_extract_failed(self, monkeypatch, caplog):
        class _Prompt:
            def __or__(self, other):
                return other

        class _ConversationInfo:
            def __init__(self):
                self._read_count = 0

            def __repr__(self):
                return "<ConversationInfo synthetic-private-conversation>"

            @property
            def subject(self):
                # 第一次读取用于 hasattr，第二次读取模拟运行期异常，覆盖异常兜底分支。
                self._read_count += 1
                if self._read_count == 1:
                    return "中间值"
                raise RuntimeError("subject read failed")

        class _StructuredLLM:
            def invoke(self, _payload):
                return _ConversationInfo()

        monkeypatch.setattr(
            "internal.service.conversation_service.ChatPromptTemplate.from_messages",
            lambda _messages: _Prompt(),
        )
        monkeypatch.setattr(
            "internal.service.conversation_service.Chat",
            lambda **_kwargs: SimpleNamespace(
                with_structured_output=lambda _schema: _StructuredLLM(),
            ),
        )
        name = ConversationService.generate_conversation_name("hello")

        assert name == "新的会话"
        assert "synthetic-private-conversation" not in caplog.text
        assert "subject read failed" not in caplog.text
        assert "error_type=RuntimeError" in caplog.text

    def test_generate_conversation_name_should_truncate_long_subject(self, monkeypatch):
        class _Prompt:
            def __or__(self, other):
                return other

        class _StructuredLLM:
            def invoke(self, _payload):
                return SimpleNamespace(subject="x" * 130)

        monkeypatch.setattr(
            "internal.service.conversation_service.ChatPromptTemplate.from_messages",
            lambda _messages: _Prompt(),
        )
        monkeypatch.setattr(
            "internal.service.conversation_service.Chat",
            lambda **_kwargs: SimpleNamespace(
                with_structured_output=lambda _schema: _StructuredLLM(),
            ),
        )

        name = ConversationService.generate_conversation_name("hello")

        assert name.endswith("...")
        assert len(name) == 123

    def test_generate_conversation_name_should_return_default_when_subject_missing(self, monkeypatch):
        class _Prompt:
            def __or__(self, other):
                return other

        class _StructuredLLM:
            def invoke(self, _payload):
                return SimpleNamespace()

        monkeypatch.setattr(
            "internal.service.conversation_service.ChatPromptTemplate.from_messages",
            lambda _messages: _Prompt(),
        )
        monkeypatch.setattr(
            "internal.service.conversation_service.Chat",
            lambda **_kwargs: SimpleNamespace(
                with_structured_output=lambda _schema: _StructuredLLM(),
            ),
        )

        name = ConversationService.generate_conversation_name("hello")

        assert name == "新的会话"

    def test_generate_suggested_questions_should_limit_to_three(self, monkeypatch):
        captured_histories = {}

        class _Prompt:
            def __or__(self, other):
                return other

        class _StructuredLLM:
            def invoke(self, payload):
                captured_histories["value"] = payload["histories"]
                return SimpleNamespace(questions=["q1", "q2", "q3", "q4"])

        monkeypatch.setattr(
            "internal.service.conversation_service.ChatPromptTemplate.from_messages",
            lambda _messages: _Prompt(),
        )
        monkeypatch.setattr(
            "internal.service.conversation_service.Chat",
            lambda **_kwargs: SimpleNamespace(
                with_structured_output=lambda _schema: _StructuredLLM(),
            ),
        )

        questions = ConversationService.generate_suggested_questions("Human: hi\nAI: hello")

        assert captured_histories["value"] == "Human: hi\nAI: hello"
        assert questions == ["q1", "q2", "q3"]

    def test_generate_suggested_questions_should_fallback_on_extract_error(self, monkeypatch, caplog):
        class _Prompt:
            def __or__(self, other):
                return other

        class _SuggestedQuestions:
            def __init__(self):
                self._read_count = 0

            def __repr__(self):
                return "<SuggestedQuestions synthetic-private-suggestion>"

            @property
            def questions(self):
                # 与会话命名一致，第一次用于 hasattr，第二次故障触发异常兜底。
                self._read_count += 1
                if self._read_count == 1:
                    return ["候选问题"]
                raise RuntimeError("questions read failed")

        class _StructuredLLM:
            def invoke(self, _payload):
                return _SuggestedQuestions()

        monkeypatch.setattr(
            "internal.service.conversation_service.ChatPromptTemplate.from_messages",
            lambda _messages: _Prompt(),
        )
        monkeypatch.setattr(
            "internal.service.conversation_service.Chat",
            lambda **_kwargs: SimpleNamespace(
                with_structured_output=lambda _schema: _StructuredLLM(),
            ),
        )
        questions = ConversationService.generate_suggested_questions("history")

        assert questions == []
        assert "synthetic-private-suggestion" not in caplog.text
        assert "questions read failed" not in caplog.text
        assert "error_type=RuntimeError" in caplog.text

    def test_generate_suggested_questions_should_return_empty_when_questions_missing(self, monkeypatch):
        class _Prompt:
            def __or__(self, other):
                return other

        class _StructuredLLM:
            def invoke(self, _payload):
                return SimpleNamespace()

        monkeypatch.setattr(
            "internal.service.conversation_service.ChatPromptTemplate.from_messages",
            lambda _messages: _Prompt(),
        )
        monkeypatch.setattr(
            "internal.service.conversation_service.Chat",
            lambda **_kwargs: SimpleNamespace(
                with_structured_output=lambda _schema: _StructuredLLM(),
            ),
        )

        questions = ConversationService.generate_suggested_questions("history")

        assert questions == []

    def test_generate_summary_and_update_should_update_conversation_summary(self, monkeypatch):
        service = self._build_service()
        conversation = SimpleNamespace(id=uuid4(), summary="旧摘要")
        captured = {}
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: conversation)
        monkeypatch.setattr(
            service,
            "summary",
            lambda query, answer, old_summary: captured.update(
                {"query": query, "answer": answer, "old_summary": old_summary}
            )
            or "新摘要",
        )
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        service._generate_summary_and_update(
            conversation_id=conversation.id,
            query="Q",
            answer="A",
        )

        assert captured == {"query": "Q", "answer": "A", "old_summary": "旧摘要"}
        assert updates == [(conversation, {"summary": "新摘要"})]

    def test_generate_conversation_name_and_update_should_update_name(self, monkeypatch):
        service = self._build_service()
        conversation = SimpleNamespace(id=uuid4(), name="旧名字")
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: conversation)
        monkeypatch.setattr(service, "generate_conversation_name", lambda _query: "新名字")
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        service._generate_conversation_name_and_update(
            conversation_id=conversation.id,
            query="如何写测试",
        )

        assert updates == [(conversation, {"name": "新名字"})]

    def test_generate_conversation_name_and_update_should_reuse_cached_name_for_same_query(self, monkeypatch):
        service = self._build_service()
        conversation = SimpleNamespace(id=uuid4(), name="旧名字")
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: conversation)

        generate_calls = []
        monkeypatch.setattr(
            service,
            "generate_conversation_name",
            lambda query: generate_calls.append(query) or "缓存主题",
        )
        updates = []

        def _fake_update(target, **kwargs):
            updates.append((target, kwargs))
            for key, value in kwargs.items():
                setattr(target, key, value)
            return target

        monkeypatch.setattr(service, "update", _fake_update)

        service._generate_conversation_name_and_update(
            conversation_id=conversation.id,
            query="你好\n世界",
        )
        service._generate_conversation_name_and_update(
            conversation_id=conversation.id,
            query="你好\n世界",
        )

        assert len(generate_calls) == 1
        assert updates == [(conversation, {"name": "缓存主题"})]

    def test_generate_conversation_name_and_update_should_update_when_cache_hit_with_different_name(self, monkeypatch):
        service = self._build_service()
        conversation = SimpleNamespace(id=uuid4(), name="旧名字")
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: conversation)

        normalized_query = ConversationService._normalize_conversation_name_query("同一个问题")
        ConversationService._set_cached_conversation_name(conversation.id, normalized_query, "缓存主题")
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        service._generate_conversation_name_and_update(
            conversation_id=conversation.id,
            query="同一个问题",
        )

        assert updates == [(conversation, {"name": "缓存主题"})]

    def test_generate_conversation_name_and_update_should_regenerate_when_query_changed(self, monkeypatch):
        service = self._build_service()
        conversation = SimpleNamespace(id=uuid4(), name="旧名字")
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: conversation)

        generate_calls = []

        def _fake_generate(query):
            generate_calls.append(query)
            return f"主题:{query}"

        monkeypatch.setattr(service, "generate_conversation_name", _fake_generate)
        updates = []

        def _fake_update(target, **kwargs):
            updates.append((target, kwargs))
            for key, value in kwargs.items():
                setattr(target, key, value)
            return target

        monkeypatch.setattr(service, "update", _fake_update)

        service._generate_conversation_name_and_update(
            conversation_id=conversation.id,
            query="第一个问题",
        )
        service._generate_conversation_name_and_update(
            conversation_id=conversation.id,
            query="第二个问题",
        )

        assert len(generate_calls) == 2
        assert updates == [
            (conversation, {"name": "主题:第一个问题"}),
            (conversation, {"name": "主题:第二个问题"}),
        ]

    def test_generate_conversation_name_and_update_should_skip_update_when_generated_name_unchanged(self, monkeypatch):
        service = self._build_service()
        conversation = SimpleNamespace(id=uuid4(), name="固定主题")
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: conversation)
        monkeypatch.setattr(service, "generate_conversation_name", lambda _query: "固定主题")
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        service._generate_conversation_name_and_update(
            conversation_id=conversation.id,
            query="新问题",
        )

        assert updates == []

    def test_set_cached_conversation_name_should_evict_oldest_when_exceeding_limit(self):
        original_limit = ConversationService._conversation_name_cache_limit
        try:
            ConversationService._conversation_name_cache_limit = 1
            first_id = uuid4()
            second_id = uuid4()

            ConversationService._set_cached_conversation_name(first_id, "q1", "n1")
            ConversationService._set_cached_conversation_name(second_id, "q2", "n2")

            assert ConversationService._get_cached_conversation_name(first_id, "q1") is None
            assert ConversationService._get_cached_conversation_name(second_id, "q2") == "n2"
        finally:
            ConversationService._conversation_name_cache_limit = original_limit

    def test_get_message_should_raise_when_message_not_owned(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        message = SimpleNamespace(created_by=uuid4(), is_deleted=False)
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: message)

        with pytest.raises(NotFoundException):
            service.get_message(uuid4(), account)

    def test_get_message_should_return_when_message_owned_and_not_deleted(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        message = SimpleNamespace(created_by=account.id, is_deleted=False)
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: message)

        result = service.get_message(uuid4(), account)

        assert result is message

    def test_get_conversation_should_raise_when_not_owned_or_deleted(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        conversation = SimpleNamespace(created_by=uuid4(), is_deleted=False)
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: conversation)

        with pytest.raises(NotFoundException):
            service.get_conversation(uuid4(), account)

    def test_get_conversation_should_return_when_owned_and_not_deleted(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        conversation = SimpleNamespace(id=uuid4(), created_by=account.id, is_deleted=False)
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: conversation)

        result = service.get_conversation(conversation.id, account)

        assert result is conversation

    def test_delete_message_should_mark_message_deleted_when_conversation_matched(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        conversation = SimpleNamespace(id=uuid4(), created_by=account.id, is_deleted=False)
        message = SimpleNamespace(id=uuid4(), conversation_id=conversation.id, created_by=account.id, is_deleted=False)

        monkeypatch.setattr(service, "get_conversation", lambda *_args, **_kwargs: conversation)
        monkeypatch.setattr(service, "get_message", lambda *_args, **_kwargs: message)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.delete_message(conversation.id, message.id, account)

        assert result is message
        assert updates == [(message, {"is_deleted": True})]

    def test_delete_message_should_raise_when_message_not_in_conversation(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        conversation = SimpleNamespace(id=uuid4(), created_by=account.id, is_deleted=False)
        message = SimpleNamespace(id=uuid4(), conversation_id=uuid4(), created_by=account.id, is_deleted=False)

        monkeypatch.setattr(service, "get_conversation", lambda *_args, **_kwargs: conversation)
        monkeypatch.setattr(service, "get_message", lambda *_args, **_kwargs: message)

        with pytest.raises(NotFoundException):
            service.delete_message(conversation.id, message.id, account)

    def test_update_conversation_should_delegate_update(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        conversation = SimpleNamespace(id=uuid4(), created_by=account.id, is_deleted=False, name="旧名字")

        monkeypatch.setattr(service, "get_conversation", lambda *_args, **_kwargs: conversation)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        cleared_cache = []
        monkeypatch.setattr(service, "_clear_cached_conversation_name", lambda cid: cleared_cache.append(cid))

        result = service.update_conversation(
            conversation.id,
            account,
            name="  新名字  ",
            is_pinned=True,
            created_by=uuid4(),
            is_deleted=True,
        )

        assert result is conversation
        assert updates == [(conversation, {"name": "新名字", "is_pinned": True})]
        assert cleared_cache == [conversation.id]

    def test_update_conversation_should_raise_when_name_invalid(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        conversation = SimpleNamespace(id=uuid4(), created_by=account.id, is_deleted=False, name="旧名字")
        monkeypatch.setattr(service, "get_conversation", lambda *_args, **_kwargs: conversation)

        with pytest.raises(ValidateErrorException, match="会话名字不能为空"):
            service.update_conversation(conversation.id, account, name="   ")

        with pytest.raises(ValidateErrorException, match="会话名字长度不能超过100个字符"):
            service.update_conversation(conversation.id, account, name="a" * 101)

    def test_update_conversation_no_update_called_when_all_fields_unallowed(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        conversation = SimpleNamespace(id=uuid4(), created_by=account.id, is_deleted=False, name="旧名字")
        monkeypatch.setattr(service, "get_conversation", lambda *_args, **_kwargs: conversation)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.update_conversation(conversation.id, account, created_by=uuid4(), is_deleted=True)

        assert result is conversation
        assert updates == []

    def test_get_conversation_messages_with_page_should_paginate_and_load_messages(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        conversation_id = uuid4()
        conversation = SimpleNamespace(id=conversation_id, created_by=account.id, is_deleted=False)
        message_1 = SimpleNamespace(id=uuid4())
        message_2 = SimpleNamespace(id=uuid4())

        class _Query:
            def __init__(self, all_result=None):
                self._all_result = all_result if all_result is not None else []
                self.filter_calls = []
                self.order_by_calls = []

            def filter(self, *args, **_kwargs):
                self.filter_calls.append(args)
                return self

            def order_by(self, *_args, **_kwargs):
                self.order_by_calls.append(_args)
                return self

            def options(self, *_args, **_kwargs):
                return self

            def all(self):
                return self._all_result

        id_query = _Query()
        message_query = _Query(all_result=[message_1, message_2])

        class _Session:
            def query(self, model):
                if getattr(model, "key", "") == "id":
                    return id_query
                return message_query

        class _Paginator:
            def __init__(self, db, req):
                self.db = db
                self.req = req
                self.paginate_called = False

            def paginate(self, query):
                self.paginate_called = True
                assert query is id_query
                return [message_1.id, message_2.id]

        service.db = SimpleNamespace(session=_Session())
        req = SimpleNamespace(created_at=SimpleNamespace(data=1704067200))
        monkeypatch.setattr(service, "get_conversation", lambda *_args, **_kwargs: conversation)
        monkeypatch.setattr("internal.service.conversation_service.Paginator", _Paginator)

        messages, paginator = service.get_conversation_messages_with_page(
            conversation_id=conversation_id,
            req=req,
            account=account,
        )

        assert messages == [message_1, message_2]
        assert isinstance(paginator, _Paginator)
        assert paginator.paginate_called is True
        assert len(id_query.filter_calls[0]) == 5
        assert message_query.filter_calls[0][0].right.value == [message_1.id, message_2.id]
        assert tuple(str(arg) for arg in id_query.order_by_calls[0]) == (
            "message.created_at DESC",
            "message.id DESC",
        )
        assert tuple(str(arg) for arg in message_query.order_by_calls[0]) == (
            "message.created_at DESC",
            "message.id DESC",
        )

    def test_get_conversation_messages_with_page_should_normalize_row_like_paginated_ids(
        self, monkeypatch
    ):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        conversation_id = uuid4()
        conversation = SimpleNamespace(id=conversation_id, created_by=account.id, is_deleted=False)
        message = SimpleNamespace(id=uuid4())

        class _RowLike:
            def __init__(self, value):
                self._mapping = {"id": value}

        class _Query:
            def __init__(self, all_result=None):
                self._all_result = all_result if all_result is not None else []
                self.filter_calls = []

            def filter(self, *args, **_kwargs):
                self.filter_calls.append(args)
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def options(self, *_args, **_kwargs):
                return self

            def all(self):
                return self._all_result

        id_query = _Query()
        message_query = _Query(all_result=[message])

        class _Session:
            def query(self, model):
                if getattr(model, "key", "") == "id":
                    return id_query
                return message_query

        class _Paginator:
            def __init__(self, db, req):
                pass

            def paginate(self, query):
                assert query is id_query
                return [_RowLike(message.id)]

        service.db = SimpleNamespace(session=_Session())
        req = SimpleNamespace(created_at=SimpleNamespace(data=None))
        monkeypatch.setattr(service, "get_conversation", lambda *_args, **_kwargs: conversation)
        monkeypatch.setattr("internal.service.conversation_service.Paginator", _Paginator)

        messages, _paginator = service.get_conversation_messages_with_page(
            conversation_id=conversation_id,
            req=req,
            account=account,
        )

        assert messages == [message]
        assert message_query.filter_calls[0][0].right.value == [message.id]

    def test_get_conversation_messages_with_page_should_skip_created_at_filter_when_absent(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        conversation_id = uuid4()
        conversation = SimpleNamespace(id=conversation_id, created_by=account.id, is_deleted=False)
        message = SimpleNamespace(id=uuid4())

        class _Query:
            def __init__(self, all_result=None):
                self._all_result = all_result if all_result is not None else []
                self.filter_calls = []

            def filter(self, *args, **_kwargs):
                self.filter_calls.append(args)
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def options(self, *_args, **_kwargs):
                return self

            def all(self):
                return self._all_result

        id_query = _Query()
        message_query = _Query(all_result=[message])

        class _Session:
            def query(self, model):
                if getattr(model, "key", "") == "id":
                    return id_query
                return message_query

        class _Paginator:
            def __init__(self, db, req):
                pass

            def paginate(self, query):
                assert query is id_query
                return [message.id]

        service.db = SimpleNamespace(session=_Session())
        req = SimpleNamespace(created_at=SimpleNamespace(data=None))
        monkeypatch.setattr(service, "get_conversation", lambda *_args, **_kwargs: conversation)
        monkeypatch.setattr("internal.service.conversation_service.Paginator", _Paginator)

        messages, _paginator = service.get_conversation_messages_with_page(
            conversation_id=conversation_id,
            req=req,
            account=account,
        )

        assert messages == [message]
        assert len(id_query.filter_calls[0]) == 4

    def test_delete_conversation_should_mark_deleted(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4(), assistant_agent_conversation_id=None)
        conversation = SimpleNamespace(
            id=uuid4(),
            created_by=account.id,
            is_deleted=False,
            invoke_from=InvokeFrom.WEB_APP.value,
            app_id=uuid4(),
        )
        monkeypatch.setattr(service, "get_conversation", lambda *_args, **_kwargs: conversation)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        result = service.delete_conversation(conversation.id, account)

        assert result is conversation
        assert updates == [(conversation, {"is_deleted": True})]

    def test_get_recent_conversations_should_return_assistant_and_debugger_items(self, app_ctx):
        service = self._build_service()
        account_id = uuid4()
        now = datetime(2026, 3, 1, tzinfo=UTC)
        assistant_conversation = SimpleNamespace(
            id=uuid4(),
            name="助手会话",
            created_by=account_id,
            is_deleted=False,
            created_at=now,
        )
        debugger_conversation = SimpleNamespace(
            id=uuid4(),
            name="调试会话",
            created_by=account_id,
            is_deleted=False,
            created_at=now,
        )
        app = SimpleNamespace(
            id=uuid4(),
            name="调试应用",
            account_id=account_id,
            debug_conversation_id=debugger_conversation.id,
        )
        message_assistant = SimpleNamespace(
            id=UUID(int=3),
            conversation_id=assistant_conversation.id,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=None,
            query="你好",
            answer="你好，我是助手",
            created_at=now,
        )
        message_debugger = SimpleNamespace(
            id=UUID(int=2),
            conversation_id=debugger_conversation.id,
            invoke_from=InvokeFrom.DEBUGGER.value,
            app_id=app.id,
            query="调试问题",
            answer="调试结果",
            created_at=now,
        )
        duplicated_old_message = SimpleNamespace(
            id=UUID(int=1),
            conversation_id=assistant_conversation.id,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=None,
            query="旧问题",
            answer="旧答案",
            created_at=now,
        )

        class _Query:
            def __init__(self, all_result):
                self._all_result = all_result

            def filter(self, *_args, **_kwargs):
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def all(self):
                return self._all_result

        class _Session:
            def query(self, model):
                model_name = getattr(model, "__name__", "")
                if model_name == "Message":
                    return _Query([message_assistant, message_debugger, duplicated_old_message])
                if model_name == "Conversation":
                    return _Query([assistant_conversation, debugger_conversation])
                if model_name == "App":
                    return _Query([app])
                raise AssertionError(f"unexpected query model: {model_name}")

        service.db = SimpleNamespace(session=_Session())
        account = SimpleNamespace(
            id=account_id,
            assistant_agent_conversation_id=assistant_conversation.id,
        )

        conversations = service.get_recent_conversations(account, limit=20)

        assert len(conversations) == 2
        assert conversations[0]["source_type"] == "assistant_agent"
        assert conversations[0]["is_active"] is True
        assert conversations[1]["source_type"] == "app_debugger"
        assert conversations[1]["app_name"] == "调试应用"
        assert conversations[1]["app_id"] == str(app.id)
        assert conversations[1]["is_active"] is True

    def test_get_recent_conversations_should_return_empty_when_no_recent_messages(self):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4(), assistant_agent_conversation_id=None)

        class _Query:
            def filter(self, *_args, **_kwargs):
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            @staticmethod
            def all():
                return []

        service.db = SimpleNamespace(session=SimpleNamespace(query=lambda _model: _Query()))

        assert service.get_recent_conversations(account, limit=20) == []

    def test_get_recent_conversations_should_break_after_reaching_limit(self, app_ctx):
        service = self._build_service()
        account_id = uuid4()
        now = datetime(2026, 3, 1, tzinfo=UTC)
        conversation_a = SimpleNamespace(id=uuid4(), name="A", created_at=now, created_by=account_id, is_deleted=False)
        conversation_b = SimpleNamespace(id=uuid4(), name="B", created_at=now, created_by=account_id, is_deleted=False)
        message_a = SimpleNamespace(id=UUID(int=1), conversation_id=conversation_a.id, invoke_from=InvokeFrom.ASSISTANT_AGENT.value, app_id=None, query="A", answer="A-answer", created_at=now)
        message_b = SimpleNamespace(id=UUID(int=2), conversation_id=conversation_b.id, invoke_from=InvokeFrom.ASSISTANT_AGENT.value, app_id=None, query="B", answer="B-answer", created_at=now)
        ordered_columns = []

        class _Query:
            def __init__(self, all_result):
                self._all_result = all_result

            def filter(self, *_args, **_kwargs):
                return self

            def order_by(self, *columns):
                ordered_columns.append(tuple(map(str, columns)))
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def all(self):
                return self._all_result

        class _Session:
            def __init__(self):
                self.message_query_count = 0

            def query(self, model):
                model_name = getattr(model, "__name__", "")
                if model_name == "Message":
                    self.message_query_count += 1
                    rows = [message_a] if self.message_query_count == 1 else [message_b]
                    return _Query(rows)
                if model_name == "Conversation":
                    return _Query([conversation_a, conversation_b])
                if model_name == "App":
                    return _Query([])
                raise AssertionError(f"unexpected model: {model_name}")

        service.db = SimpleNamespace(session=_Session())
        account = SimpleNamespace(id=account_id, assistant_agent_conversation_id=conversation_a.id)

        conversations = service.get_recent_conversations(account, limit=1)

        assert len(conversations) == 1
        assert conversations[0]["id"] == str(conversation_b.id)
        assert ordered_columns == [
            ("message.created_at DESC", "message.id DESC"),
            ("message.created_at DESC", "message.id DESC"),
        ]

    def test_get_recent_conversations_should_merge_sources_by_recency(self, app_ctx):
        service = self._build_service()
        account_id = uuid4()
        old_time = datetime(2026, 1, 1, tzinfo=UTC)
        new_time = datetime(2026, 1, 2, tzinfo=UTC)
        older_conversation = SimpleNamespace(id=uuid4(), name="Older", created_by=account_id,
                                              is_deleted=False, created_at=old_time)
        newer_conversation = SimpleNamespace(id=uuid4(), name="Newer", created_by=uuid4(),
                                              is_deleted=False, created_at=new_time)
        public_app = SimpleNamespace(id=uuid4(), name="Owned app", account_id=account_id)
        older_message = SimpleNamespace(
            id=uuid4(), conversation_id=older_conversation.id,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value, app_id=None,
            query="older", answer="answer", created_at=old_time,
        )
        newer_message = SimpleNamespace(
            id=uuid4(), conversation_id=newer_conversation.id,
            invoke_from=InvokeFrom.SERVICE_API.value, app_id=public_app.id,
            query="newer", answer="answer", created_at=new_time,
        )

        class _Query:
            def __init__(self, rows):
                self.rows = rows

            def filter(self, *_args, **_kwargs):
                return self

            order_by = limit = filter

            def all(self):
                return self.rows

        query_results = iter([
            _Query([older_message]), _Query([newer_message]),
            _Query([older_conversation, newer_conversation]), _Query([public_app]),
        ])
        service.db = SimpleNamespace(session=SimpleNamespace(query=lambda _model: next(query_results)))
        account = SimpleNamespace(id=account_id, assistant_agent_conversation_id=None)

        conversations = service.get_recent_conversations(account, limit=1)

        assert (conversations[0]["id"], conversations[0]["source_type"]) == (str(newer_conversation.id), "public_app")

    def test_get_recent_conversations_should_skip_message_when_conversation_not_found(self, app_ctx):
        service = self._build_service()
        account_id = uuid4()
        now = datetime(2026, 3, 1, tzinfo=UTC)
        message = SimpleNamespace(
            id=uuid4(),
            conversation_id=uuid4(),
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=None,
            query="missing",
            answer="missing-answer",
            created_at=now,
        )

        class _Query:
            def __init__(self, all_result):
                self._all_result = all_result

            def filter(self, *_args, **_kwargs):
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def all(self):
                return self._all_result

        class _Session:
            def query(self, model):
                model_name = getattr(model, "__name__", "")
                if model_name == "Message":
                    return _Query([message])
                if model_name == "Conversation":
                    return _Query([])
                if model_name == "App":
                    return _Query([])
                raise AssertionError(f"unexpected model: {model_name}")

        service.db = SimpleNamespace(session=_Session())
        account = SimpleNamespace(id=account_id, assistant_agent_conversation_id=None)

        assert service.get_recent_conversations(account, limit=20) == []

    def test_get_recent_conversations_should_skip_debugger_message_when_app_not_found(self, app_ctx):
        service = self._build_service()
        account_id = uuid4()
        now = datetime(2026, 3, 1, tzinfo=UTC)
        conversation = SimpleNamespace(id=uuid4(), name="debug", created_by=account_id, is_deleted=False, created_at=now)
        message = SimpleNamespace(
            id=uuid4(),
            conversation_id=conversation.id,
            invoke_from=InvokeFrom.DEBUGGER.value,
            app_id=uuid4(),
            query="debug",
            answer="debug-answer",
            created_at=now,
        )

        class _Query:
            def __init__(self, all_result):
                self._all_result = all_result

            def filter(self, *_args, **_kwargs):
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def all(self):
                return self._all_result

        class _Session:
            def query(self, model):
                model_name = getattr(model, "__name__", "")
                if model_name == "Message":
                    return _Query([message])
                if model_name == "Conversation":
                    return _Query([conversation])
                if model_name == "App":
                    return _Query([])
                raise AssertionError(f"unexpected model: {model_name}")

        service.db = SimpleNamespace(session=_Session())
        account = SimpleNamespace(id=account_id, assistant_agent_conversation_id=None)

        assert service.get_recent_conversations(account, limit=20) == []

    def test_delete_conversation_should_clear_assistant_agent_pointer(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4(), assistant_agent_conversation_id=uuid4())
        conversation = SimpleNamespace(
            id=account.assistant_agent_conversation_id,
            created_by=account.id,
            is_deleted=False,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=None,
        )
        monkeypatch.setattr(service, "get_conversation", lambda *_args, **_kwargs: conversation)
        clear_calls = []
        monkeypatch.setattr(service, "_clear_cached_conversation_name", lambda conversation_id: clear_calls.append(conversation_id))
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        service.delete_conversation(conversation.id, account)

        assert updates[0] == (account, {"assistant_agent_conversation_id": None})
        assert updates[1] == (conversation, {"is_deleted": True})
        assert clear_calls == [conversation.id]

    def test_delete_conversation_should_clear_debugger_app_pointer(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4(), assistant_agent_conversation_id=None)
        app = SimpleNamespace(id=uuid4(), account_id=account.id, debug_conversation_id=uuid4())
        conversation = SimpleNamespace(
            id=app.debug_conversation_id,
            created_by=account.id,
            is_deleted=False,
            invoke_from=InvokeFrom.DEBUGGER.value,
            app_id=app.id,
        )
        monkeypatch.setattr(service, "get_conversation", lambda *_args, **_kwargs: conversation)
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: app)
        clear_calls = []
        monkeypatch.setattr(service, "_clear_cached_conversation_name", lambda conversation_id: clear_calls.append(conversation_id))
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        service.delete_conversation(conversation.id, account)

        assert updates[0] == (app, {"debug_conversation_id": None})
        assert updates[1] == (conversation, {"is_deleted": True})
        assert clear_calls == [conversation.id]

    def test_delete_conversation_should_not_update_debugger_pointer_when_app_not_owned(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4(), assistant_agent_conversation_id=None)
        conversation = SimpleNamespace(
            id=uuid4(),
            created_by=account.id,
            is_deleted=False,
            invoke_from=InvokeFrom.DEBUGGER.value,
            app_id=uuid4(),
        )
        foreign_app = SimpleNamespace(
            id=conversation.app_id,
            account_id=uuid4(),
            debug_conversation_id=conversation.id,
        )
        monkeypatch.setattr(service, "get_conversation", lambda *_args, **_kwargs: conversation)
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: foreign_app)
        clear_calls = []
        monkeypatch.setattr(service, "_clear_cached_conversation_name", lambda conversation_id: clear_calls.append(conversation_id))
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        service.delete_conversation(conversation.id, account)

        assert updates == [(conversation, {"is_deleted": True})]
        assert clear_calls == [conversation.id]

    def test_generate_conversation_name_and_update_should_update_when_cache_hit_but_name_different(self, monkeypatch):
        service = self._build_service()
        conversation = SimpleNamespace(id=uuid4(), name="旧名字")
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: conversation)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )
        query = "缓存命中的问题"
        normalized_query = ConversationService._normalize_conversation_name_query(query)
        ConversationService._set_cached_conversation_name(
            conversation_id=conversation.id,
            normalized_query=normalized_query,
            conversation_name="缓存主题",
        )

        service._generate_conversation_name_and_update(
            conversation_id=conversation.id,
            query=query,
        )

        assert updates == [(conversation, {"name": "缓存主题"})]

    def test_get_recent_conversations_should_return_empty_when_no_messages(self):
        service = self._build_service()

        class _Query:
            def filter(self, *_args, **_kwargs):
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            @staticmethod
            def all():
                return []

        class _Session:
            def query(self, _model):
                return _Query()

        service.db = SimpleNamespace(session=_Session())
        account = SimpleNamespace(id=uuid4(), assistant_agent_conversation_id=None)

        assert service.get_recent_conversations(account, limit=10) == []

    def test_get_recent_conversations_should_break_when_reach_limit(self, app_ctx):
        service = self._build_service()
        account_id = uuid4()
        now = datetime(2026, 3, 1, tzinfo=UTC)
        conversation_1 = SimpleNamespace(id=uuid4(), name="会话1", created_by=account_id, is_deleted=False, created_at=now)
        conversation_2 = SimpleNamespace(id=uuid4(), name="会话2", created_by=account_id, is_deleted=False, created_at=now)
        message_1 = SimpleNamespace(
            id=UUID(int=1),
            conversation_id=conversation_1.id,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=None,
            query="会话1",
            answer="会话1-answer",
            created_at=now,
        )
        message_2 = SimpleNamespace(
            id=UUID(int=2),
            conversation_id=conversation_2.id,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=None,
            query="会话2",
            answer="会话2-answer",
            created_at=now,
        )

        class _Query:
            def __init__(self, all_result):
                self._all_result = all_result

            def filter(self, *_args, **_kwargs):
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def all(self):
                return self._all_result

        class _Session:
            def query(self, model):
                model_name = getattr(model, "__name__", "")
                if model_name == "Message":
                    return _Query([message_1, message_2])
                if model_name == "Conversation":
                    return _Query([conversation_1, conversation_2])
                if model_name == "App":
                    return _Query([])
                raise AssertionError(f"unexpected query model: {model_name}")

        service.db = SimpleNamespace(session=_Session())
        account = SimpleNamespace(id=account_id, assistant_agent_conversation_id=conversation_1.id)

        conversations = service.get_recent_conversations(account, limit=1)

        assert len(conversations) == 1
        assert conversations[0]["id"] == str(conversation_2.id)

    def test_get_recent_conversations_should_allow_more_than_fifty_items(self, app_ctx):
        service = self._build_service()
        account_id = uuid4()
        now = datetime(2026, 3, 1, tzinfo=UTC)
        conversations_data = [
            SimpleNamespace(
                id=uuid4(),
                name=f"会话{index + 1}",
                created_by=account_id,
                is_deleted=False,
                created_at=now,
            )
            for index in range(60)
        ]
        messages_data = [
            SimpleNamespace(
                id=uuid4(),
                conversation_id=conversation.id,
                invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
                app_id=None,
                query=f"会话{index + 1}",
                answer=f"会话{index + 1}-answer",
                created_at=now,
            )
            for index, conversation in enumerate(conversations_data)
        ]

        class _Query:
            def __init__(self, all_result):
                self._all_result = all_result

            def filter(self, *_args, **_kwargs):
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def all(self):
                return self._all_result

        class _Session:
            def query(self, model):
                model_name = getattr(model, "__name__", "")
                if model_name == "Message":
                    return _Query(messages_data)
                if model_name == "Conversation":
                    return _Query(conversations_data)
                if model_name == "App":
                    return _Query([])
                raise AssertionError(f"unexpected query model: {model_name}")

        service.db = SimpleNamespace(session=_Session())
        account = SimpleNamespace(id=account_id, assistant_agent_conversation_id=None)

        conversations = service.get_recent_conversations(account, limit=60)

        assert len(conversations) == 60
        expected_conversation_ids = [
            str(message.conversation_id)
            for message in sorted(messages_data, key=lambda item: str(item.id), reverse=True)
        ]
        assert [item["id"] for item in conversations] == expected_conversation_ids

    def test_get_recent_conversations_should_skip_missing_conversation_and_missing_debugger_app(self, app_ctx):
        service = self._build_service()
        account_id = uuid4()
        now = datetime(2026, 3, 1, tzinfo=UTC)
        missing_conversation_id = uuid4()
        existing_conversation = SimpleNamespace(
            id=uuid4(),
            name="调试会话",
            created_by=account_id,
            is_deleted=False,
            created_at=now,
        )
        message_missing_conversation = SimpleNamespace(
            id=uuid4(),
            conversation_id=missing_conversation_id,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=None,
            query="missing-conversation",
            answer="missing-conversation-answer",
            created_at=now,
        )
        message_missing_app = SimpleNamespace(
            id=uuid4(),
            conversation_id=existing_conversation.id,
            invoke_from=InvokeFrom.DEBUGGER.value,
            app_id=uuid4(),
            query="missing-app",
            answer="missing-app-answer",
            created_at=now,
        )

        class _Query:
            def __init__(self, all_result):
                self._all_result = all_result

            def filter(self, *_args, **_kwargs):
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def all(self):
                return self._all_result

        class _Session:
            def query(self, model):
                model_name = getattr(model, "__name__", "")
                if model_name == "Message":
                    return _Query([message_missing_conversation, message_missing_app])
                if model_name == "Conversation":
                    return _Query([existing_conversation])
                if model_name == "App":
                    return _Query([])
                raise AssertionError(f"unexpected query model: {model_name}")

        service.db = SimpleNamespace(session=_Session())
        account = SimpleNamespace(id=account_id, assistant_agent_conversation_id=None)

        conversations = service.get_recent_conversations(account, limit=10)

        assert conversations == []

    def test_get_recent_conversations_should_backfill_when_newer_candidate_is_deleted(self, app_ctx):
        service = self._build_service()
        account_id = uuid4()
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
        older = datetime(2026, 3, 1, 11, 0, 0, tzinfo=UTC)

        deleted_conv = SimpleNamespace(
            id=uuid4(),
            name="已删除会话",
            created_by=account_id,
            is_deleted=True,
            created_at=now,
        )
        active_conv = SimpleNamespace(
            id=uuid4(),
            name="有效会话",
            created_by=account_id,
            is_deleted=False,
            created_at=older,
        )

        msg_deleted = SimpleNamespace(
            id=UUID(int=2),
            conversation_id=deleted_conv.id,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=None,
            query="deleted query",
            answer="deleted answer",
            created_at=now,
        )
        msg_active = SimpleNamespace(
            id=UUID(int=1),
            conversation_id=active_conv.id,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=None,
            query="active query",
            answer="active answer",
            created_at=older,
        )

        class _Query:
            def __init__(self, all_result):
                self._all_result = all_result

            def filter(self, *_args, **_kwargs):
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def all(self):
                return self._all_result

        class _Session:
            def query(self, model):
                model_name = getattr(model, "__name__", "")
                if model_name == "Message":
                    return _Query([msg_deleted, msg_active])
                if model_name == "Conversation":
                    return _Query([active_conv])
                if model_name == "App":
                    return _Query([])
                raise AssertionError(f"unexpected model: {model_name}")

        service.db = SimpleNamespace(session=_Session())
        account = SimpleNamespace(id=account_id, assistant_agent_conversation_id=None)

        # limit=1 must skip deleted_conv and return the active_conv
        conversations = service.get_recent_conversations(account, limit=1)

        assert len(conversations) == 1
        assert conversations[0]["id"] == str(active_conv.id)
        assert conversations[0]["name"] == "有效会话"

    def test_get_recent_conversations_should_handle_mixed_aware_and_naive_message_timestamps(self, app_ctx):
        service = self._build_service()
        account_id = uuid4()
        dt_aware = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
        dt_naive = datetime(2026, 3, 1, 11, 0, 0)

        conv_aware = SimpleNamespace(id=uuid4(), name="Aware", created_by=account_id, is_deleted=False, created_at=dt_aware)
        conv_naive = SimpleNamespace(id=uuid4(), name="Naive", created_by=account_id, is_deleted=False, created_at=dt_naive)

        msg_aware = SimpleNamespace(
            id=UUID(int=2),
            conversation_id=conv_aware.id,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=None,
            query="aware",
            answer="aware answer",
            created_at=dt_aware,
        )
        msg_naive = SimpleNamespace(
            id=UUID(int=1),
            conversation_id=conv_naive.id,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=None,
            query="naive",
            answer="naive answer",
            created_at=dt_naive,
        )

        class _Query:
            def __init__(self, all_result):
                self._all_result = all_result

            def filter(self, *_args, **_kwargs):
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def all(self):
                return self._all_result

        class _Session:
            def query(self, model):
                model_name = getattr(model, "__name__", "")
                if model_name == "Message":
                    return _Query([msg_aware, msg_naive])
                if model_name == "Conversation":
                    return _Query([conv_aware, conv_naive])
                if model_name == "App":
                    return _Query([])
                raise AssertionError(f"unexpected model: {model_name}")

        service.db = SimpleNamespace(session=_Session())
        account = SimpleNamespace(id=account_id, assistant_agent_conversation_id=None)

        conversations = service.get_recent_conversations(account, limit=2)

        assert len(conversations) == 2
        assert [c["id"] for c in conversations] == [str(conv_aware.id), str(conv_naive.id)]

    def test_delete_conversation_should_skip_debugger_pointer_clear_when_app_not_active(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4(), assistant_agent_conversation_id=None)
        app = SimpleNamespace(id=uuid4(), account_id=account.id, debug_conversation_id=uuid4())
        conversation = SimpleNamespace(
            id=uuid4(),
            created_by=account.id,
            is_deleted=False,
            invoke_from=InvokeFrom.DEBUGGER.value,
            app_id=app.id,
        )
        monkeypatch.setattr(service, "get_conversation", lambda *_args, **_kwargs: conversation)
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: app)
        monkeypatch.setattr(service, "_clear_cached_conversation_name", lambda *_args, **_kwargs: None)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)) or target,
        )

        service.delete_conversation(conversation.id, account)

        assert updates == [(conversation, {"is_deleted": True})]

    def test_delete_conversation_removes_from_list(self, monkeypatch):
        """测试删除对话后不再出现在列表中"""
        service = self._build_service()
        account = SimpleNamespace(id=uuid4(), assistant_agent_conversation_id=None)

        # 创建两个对话
        conv1 = SimpleNamespace(
            id=uuid4(),
            created_by=account.id,
            is_deleted=False,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=None,
        )
        conv2 = SimpleNamespace(
            id=uuid4(),
            created_by=account.id,
            is_deleted=False,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=None,
        )

        # Mock get_conversation
        def mock_get_conversation(conv_id, _account):
            if conv_id == conv1.id:
                return conv1
            if conv_id == conv2.id:
                return conv2
            raise NotFoundException()

        monkeypatch.setattr(service, "get_conversation", mock_get_conversation)
        monkeypatch.setattr(service, "_clear_cached_conversation_name", lambda *_args, **_kwargs: None)

        updates = []
        def mock_update(target, **kwargs):
            updates.append((target, kwargs))
            return target

        monkeypatch.setattr(service, "update", mock_update)

        # 删除第一个对话
        service.delete_conversation(conv1.id, account)

        # 验证删除标记
        assert len(updates) == 1
        assert updates[0][1] == {"is_deleted": True}

    def test_update_conversation_name(self, monkeypatch):
        """测试更新对话名称"""
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        conversation = SimpleNamespace(
            id=uuid4(),
            created_by=account.id,
            name="旧名称",
        )

        monkeypatch.setattr(service, "get_conversation", lambda *_args, **_kwargs: conversation)
        monkeypatch.setattr(service, "_clear_cached_conversation_name", lambda *_args, **_kwargs: None)

        updates = []
        def mock_update(target, **kwargs):
            updates.append((target, kwargs))
            for key, value in kwargs.items():
                setattr(target, key, value)
            return target

        monkeypatch.setattr(service, "update", mock_update)

        # 更新名称
        service.update_conversation(conversation.id, account, name="新名称")

        # 验证更新
        assert len(updates) == 1
        assert updates[0][1] == {"name": "新名称"}
        assert conversation.name == "新名称"

    def test_rename_and_delete_workflow(self, monkeypatch):
        """测试重命名和删除的完整流程"""
        service = self._build_service()
        account = SimpleNamespace(id=uuid4(), assistant_agent_conversation_id=None)
        conversation = SimpleNamespace(
            id=uuid4(),
            created_by=account.id,
            name="原始名称",
            is_deleted=False,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=None,
        )

        monkeypatch.setattr(service, "get_conversation", lambda *_args, **_kwargs: conversation)
        monkeypatch.setattr(service, "_clear_cached_conversation_name", lambda *_args, **_kwargs: None)

        updates = []
        def mock_update(target, **kwargs):
            updates.append((target, kwargs))
            for key, value in kwargs.items():
                setattr(target, key, value)
            return target

        monkeypatch.setattr(service, "update", mock_update)

        # 1. 重命名
        service.update_conversation(conversation.id, account, name="新名称")
        assert conversation.name == "新名称"
        assert len(updates) == 1

        # 2. 删除
        service.delete_conversation(conversation.id, account)
        assert len(updates) == 2
        assert updates[1][1] == {"is_deleted": True}

    def test_get_recent_conversations_should_scope_service_api_items_to_app_owner(self):
        owner_id, foreign_id = uuid4(), uuid4()
        owner_app = SimpleNamespace(id=uuid4(), name="Owned", account_id=owner_id)
        foreign_app = SimpleNamespace(id=uuid4(), name="Foreign", account_id=foreign_id)
        app_owners = {owner_app.id: owner_id, foreign_app.id: foreign_id}
        owner_conversation = SimpleNamespace(id=uuid4(), name="Owned", created_by=uuid4(), is_deleted=False, created_at=datetime.now(UTC))
        foreign_conversation = SimpleNamespace(id=uuid4(), name="Foreign", created_by=uuid4(), is_deleted=False, created_at=datetime.now(UTC))
        messages = [
            SimpleNamespace(id=uuid4(), conversation_id=owner_conversation.id, invoke_from=InvokeFrom.SERVICE_API.value, app_id=owner_app.id, query="owned prompt", answer="owned answer", created_at=datetime.now(UTC)),
            SimpleNamespace(id=uuid4(), conversation_id=foreign_conversation.id, invoke_from=InvokeFrom.SERVICE_API.value, app_id=foreign_app.id, query="foreign prompt", answer="foreign answer", created_at=datetime.now(UTC)),
        ]

        class _Query:
            def __init__(self, rows):
                self.rows = rows

            def filter(self, *conditions):
                for condition in conditions:
                    if getattr(getattr(condition, "left", None), "key", None) == "app_id":
                        owner = condition.right.element._where_criteria[0].right.value
                        self.rows = [row for row in self.rows if app_owners[row.app_id] == owner]
                return self

            def _chain(self, *_args):
                return self

            order_by = limit = _chain

            def all(self):
                return self.rows

        message_results = iter([[], messages])
        class _Session:
            def query(self, model):
                name = getattr(model, "__name__", "")
                if name == "Message":
                    return _Query(next(message_results))
                if name == "Conversation":
                    return _Query([owner_conversation, foreign_conversation])
                if name == "App":
                    return _Query([owner_app, foreign_app])
                raise AssertionError(f"unexpected query model: {name}")

        service = self._build_service()
        service.db = SimpleNamespace(session=_Session())
        account = SimpleNamespace(id=owner_id, assistant_agent_conversation_id=None)
        with Flask(__name__).app_context():
            results = service.get_recent_conversations(account)

        assert [item["human_message"] for item in results] == ["owned prompt"]

    @staticmethod
    def _build_batch_test_session(messages, conversations, apps, public_messages=None):
        class _BatchTestSession:
            def __init__(self, msgs, convs, app_list, pub_msgs=None):
                self.messages = msgs
                self.public_messages = pub_msgs if pub_msgs is not None else []
                self.conversations = {c.id: c for c in convs}
                self.apps = {a.id: a for a in app_list}
                self.conversation_batches = []
                self.app_batches = []
                self._message_call_count = 0

            def query(self, model):
                model_name = getattr(model, "__name__", "")
                session = self

                class _Query:
                    def __init__(self):
                        self.ids = None

                    def filter(self, *criteria):
                        for crit in criteria:
                            right = getattr(crit, "right", None)
                            val = getattr(right, "value", None)
                            if isinstance(val, (list, tuple, set)):
                                self.ids = list(val)
                        return self

                    def order_by(self, *_args, **_kwargs):
                        return self

                    def limit(self, *_args, **_kwargs):
                        return self

                    def all(self):
                        if model_name == "Message":
                            session._message_call_count += 1
                            if session._message_call_count == 1:
                                return session.messages
                            return session.public_messages
                        if model_name == "Conversation":
                            session.conversation_batches.append(list(self.ids) if self.ids else [])
                            if self.ids is not None:
                                return [
                                    session.conversations[cid]
                                    for cid in self.ids
                                    if cid in session.conversations
                                    and not getattr(session.conversations[cid], "is_deleted", False)
                                ]
                            return [
                                c for c in session.conversations.values()
                                if not getattr(c, "is_deleted", False)
                            ]
                        if model_name == "App":
                            session.app_batches.append(list(self.ids) if self.ids else [])
                            if self.ids is not None:
                                return [
                                    session.apps[aid]
                                    for aid in self.ids
                                    if aid in session.apps
                                ]
                            return list(session.apps.values())
                        raise AssertionError(f"unexpected model: {model_name}")

                return _Query()

        return _BatchTestSession(messages, conversations, apps, public_messages)

    def test_get_recent_conversations_candidate_count_exceeds_batch_size_and_stops_early(self, app_ctx):
        service = self._build_service()
        account_id = uuid4()
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)

        conversations = []
        messages = []
        for i in range(25):
            conv_id = uuid4()
            conv = SimpleNamespace(
                id=conv_id,
                name=f"会话_{i}",
                created_by=account_id,
                is_deleted=False,
                created_at=now,
            )
            conversations.append(conv)
            msg = SimpleNamespace(
                id=UUID(int=100 + i),
                conversation_id=conv_id,
                invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
                app_id=None,
                query=f"query {i}",
                answer=f"answer {i}",
                created_at=now - timedelta(minutes=i),
            )
            messages.append(msg)

        session = self._build_batch_test_session(messages, conversations, [])
        service.db = SimpleNamespace(session=session)
        account = SimpleNamespace(id=account_id, assistant_agent_conversation_id=None)

        results = service.get_recent_conversations(account, limit=5)

        assert len(results) == 5
        assert len(session.conversation_batches) == 1
        assert len(session.conversation_batches[0]) == 20
        assert results[0]["name"] == "会话_0"
        assert results[4]["name"] == "会话_4"

    def test_get_recent_conversations_first_batch_all_deleted_backfills_from_second_batch(self, app_ctx):
        service = self._build_service()
        account_id = uuid4()
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)

        conversations = []
        messages = []
        for i in range(25):
            conv_id = uuid4()
            conv = SimpleNamespace(
                id=conv_id,
                name=f"会话_{i}",
                created_by=account_id,
                is_deleted=(i < 20),
                created_at=now,
            )
            conversations.append(conv)
            msg = SimpleNamespace(
                id=UUID(int=200 + i),
                conversation_id=conv_id,
                invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
                app_id=None,
                query=f"query {i}",
                answer=f"answer {i}",
                created_at=now - timedelta(minutes=i),
            )
            messages.append(msg)

        session = self._build_batch_test_session(messages, conversations, [])
        service.db = SimpleNamespace(session=session)
        account = SimpleNamespace(id=account_id, assistant_agent_conversation_id=None)

        results = service.get_recent_conversations(account, limit=3)

        assert len(results) == 3
        assert len(session.conversation_batches) == 2
        assert len(session.conversation_batches[0]) == 20
        assert len(session.conversation_batches[1]) == 5
        assert results[0]["name"] == "会话_20"
        assert results[1]["name"] == "会话_21"
        assert results[2]["name"] == "会话_22"

    def test_get_recent_conversations_first_batch_all_missing_app_backfills(self, app_ctx):
        service = self._build_service()
        account_id = uuid4()
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)

        valid_app = SimpleNamespace(id=uuid4(), name="有效应用", debug_conversation_id=None)
        conversations = []
        messages = []
        for i in range(25):
            conv_id = uuid4()
            conv = SimpleNamespace(
                id=conv_id,
                name=f"调试会话_{i}",
                created_by=account_id,
                is_deleted=False,
                created_at=now,
            )
            conversations.append(conv)
            app_id = uuid4() if i < 20 else valid_app.id
            msg = SimpleNamespace(
                id=UUID(int=300 + i),
                conversation_id=conv_id,
                invoke_from=InvokeFrom.DEBUGGER.value,
                app_id=app_id,
                query=f"query {i}",
                answer=f"answer {i}",
                created_at=now - timedelta(minutes=i),
            )
            messages.append(msg)

        session = self._build_batch_test_session(messages, conversations, [valid_app])
        service.db = SimpleNamespace(session=session)
        account = SimpleNamespace(id=account_id, assistant_agent_conversation_id=None)

        results = service.get_recent_conversations(account, limit=3)

        assert len(results) == 3
        assert len(session.conversation_batches) == 2
        assert results[0]["name"] == "调试会话_20"
        assert results[1]["name"] == "调试会话_21"
        assert results[2]["name"] == "调试会话_22"
        assert results[0]["app_name"] == "有效应用"

    def test_get_recent_conversations_cross_batch_backfill_collects_target_limit(self, app_ctx):
        service = self._build_service()
        account_id = uuid4()
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)

        conversations = []
        messages = []
        for i in range(30):
            conv_id = uuid4()
            # Batch 1 (0..19): even deleted, odd active (10 active, 10 deleted)
            # Batch 2 (20..29): all active (10 active)
            is_deleted = (i < 20 and i % 2 == 0)
            conv = SimpleNamespace(
                id=conv_id,
                name=f"会话_{i}",
                created_by=account_id,
                is_deleted=is_deleted,
                created_at=now,
            )
            conversations.append(conv)
            msg = SimpleNamespace(
                id=UUID(int=400 + i),
                conversation_id=conv_id,
                invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
                app_id=None,
                query=f"query {i}",
                answer=f"answer {i}",
                created_at=now - timedelta(minutes=i),
            )
            messages.append(msg)

        session = self._build_batch_test_session(messages, conversations, [])
        service.db = SimpleNamespace(session=session)
        account = SimpleNamespace(id=account_id, assistant_agent_conversation_id=None)

        # limit=15: batch 1 has 10 active, batch 2 fills remaining 5
        results = service.get_recent_conversations(account, limit=15)

        assert len(results) == 15
        assert len(session.conversation_batches) == 2
        assert len(session.conversation_batches[0]) == 20
        assert len(session.conversation_batches[1]) == 10

    def test_get_recent_conversations_exhausted_candidates_with_insufficient_data(self, app_ctx):
        service = self._build_service()
        account_id = uuid4()
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)

        conversations = []
        messages = []
        for i in range(25):
            conv_id = uuid4()
            # Only index 0, 1 in batch 1 and index 22 in batch 2 are active
            is_deleted = i not in (0, 1, 22)
            conv = SimpleNamespace(
                id=conv_id,
                name=f"会话_{i}",
                created_by=account_id,
                is_deleted=is_deleted,
                created_at=now,
            )
            conversations.append(conv)
            msg = SimpleNamespace(
                id=UUID(int=500 + i),
                conversation_id=conv_id,
                invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
                app_id=None,
                query=f"query {i}",
                answer=f"answer {i}",
                created_at=now - timedelta(minutes=i),
            )
            messages.append(msg)

        session = self._build_batch_test_session(messages, conversations, [])
        service.db = SimpleNamespace(session=session)
        account = SimpleNamespace(id=account_id, assistant_agent_conversation_id=None)

        results = service.get_recent_conversations(account, limit=20)

        assert len(results) == 3
        assert [r["name"] for r in results] == ["会话_0", "会话_1", "会话_22"]
        assert len(session.conversation_batches) == 2

    def test_get_recent_conversations_limit_one_only_queries_one_batch(self, app_ctx):
        service = self._build_service()
        account_id = uuid4()
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)

        conversations = []
        messages = []
        for i in range(30):
            conv_id = uuid4()
            conv = SimpleNamespace(
                id=conv_id,
                name=f"会话_{i}",
                created_by=account_id,
                is_deleted=False,
                created_at=now,
            )
            conversations.append(conv)
            msg = SimpleNamespace(
                id=UUID(int=600 + i),
                conversation_id=conv_id,
                invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
                app_id=None,
                query=f"query {i}",
                answer=f"answer {i}",
                created_at=now - timedelta(minutes=i),
            )
            messages.append(msg)

        session = self._build_batch_test_session(messages, conversations, [])
        service.db = SimpleNamespace(session=session)
        account = SimpleNamespace(id=account_id, assistant_agent_conversation_id=None)

        results = service.get_recent_conversations(account, limit=1)

        assert len(results) == 1
        assert len(session.conversation_batches) == 1
        assert len(session.conversation_batches[0]) == 20
        assert results[0]["name"] == "会话_0"

    def test_get_recent_conversations_limit_thousand_bounded_batch_size(self, app_ctx):
        service = self._build_service()
        account_id = uuid4()
        now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)

        conversations = []
        messages = []
        for i in range(150):
            conv_id = uuid4()
            conv = SimpleNamespace(
                id=conv_id,
                name=f"会话_{i}",
                created_by=account_id,
                is_deleted=False,
                created_at=now,
            )
            conversations.append(conv)
            msg = SimpleNamespace(
                id=UUID(int=1000 + i),
                conversation_id=conv_id,
                invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
                app_id=None,
                query=f"query {i}",
                answer=f"answer {i}",
                created_at=now - timedelta(seconds=i),
            )
            messages.append(msg)

        session = self._build_batch_test_session(messages, conversations, [])
        service.db = SimpleNamespace(session=session)
        account = SimpleNamespace(id=account_id, assistant_agent_conversation_id=None)

        results = service.get_recent_conversations(account, limit=1000)

        assert len(results) == 150
        assert len(session.conversation_batches) == 2
        assert len(session.conversation_batches[0]) == 100
        assert len(session.conversation_batches[1]) == 50

    def test_get_recent_conversations_mixed_timezones_ordered_by_recency(self, app_ctx):
        service = self._build_service()
        account_id = uuid4()

        # 4 messages with different timezone representations:
        # 1. 12:30 UTC aware -> newest
        # 2. 20:15 UTC+8 (= 12:15 UTC) -> 2nd newest
        # 3. 12:00 UTC naive -> 3rd newest
        # 4. 11:45 UTC aware -> oldest
        dt_aware_newest = datetime(2026, 3, 1, 12, 30, 0, tzinfo=UTC)
        dt_offset_second = datetime(2026, 3, 1, 20, 15, 0, tzinfo=timezone(timedelta(hours=8)))
        dt_naive_third = datetime(2026, 3, 1, 12, 0, 0)
        dt_aware_oldest = datetime(2026, 3, 1, 11, 45, 0, tzinfo=UTC)

        convs = [
            SimpleNamespace(id=uuid4(), name="Newest", created_by=account_id, is_deleted=False, created_at=dt_aware_newest),
            SimpleNamespace(id=uuid4(), name="Second", created_by=account_id, is_deleted=False, created_at=dt_offset_second),
            SimpleNamespace(id=uuid4(), name="Third", created_by=account_id, is_deleted=False, created_at=dt_naive_third),
            SimpleNamespace(id=uuid4(), name="Oldest", created_by=account_id, is_deleted=False, created_at=dt_aware_oldest),
        ]
        # Feed messages in arbitrary (non-sorted) order to test sorting
        msgs = [
            SimpleNamespace(id=UUID(int=1), conversation_id=convs[2].id, invoke_from=InvokeFrom.ASSISTANT_AGENT.value, app_id=None, query="3", answer="a3", created_at=dt_naive_third),
            SimpleNamespace(id=UUID(int=2), conversation_id=convs[0].id, invoke_from=InvokeFrom.ASSISTANT_AGENT.value, app_id=None, query="1", answer="a1", created_at=dt_aware_newest),
            SimpleNamespace(id=UUID(int=3), conversation_id=convs[3].id, invoke_from=InvokeFrom.ASSISTANT_AGENT.value, app_id=None, query="4", answer="a4", created_at=dt_aware_oldest),
            SimpleNamespace(id=UUID(int=4), conversation_id=convs[1].id, invoke_from=InvokeFrom.ASSISTANT_AGENT.value, app_id=None, query="2", answer="a2", created_at=dt_offset_second),
        ]

        session = self._build_batch_test_session(msgs, convs, [])
        service.db = SimpleNamespace(session=session)
        account = SimpleNamespace(id=account_id, assistant_agent_conversation_id=None)

        results = service.get_recent_conversations(account, limit=10)

        assert len(results) == 4
        assert [r["name"] for r in results] == ["Newest", "Second", "Third", "Oldest"]

    def test_compare_messages_should_compute_run_differences(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        m1 = SimpleNamespace(
            id=uuid4(),
            created_by=account.id,
            is_deleted=False,
            status="normal",
            error="",
            latency=2.5,
            message_token_count=100,
            answer_token_count=50,
            total_token_count=150,
            total_price=0.03,
            answer="hello world",
        )
        m2 = SimpleNamespace(
            id=uuid4(),
            created_by=account.id,
            is_deleted=False,
            status="error",
            error="rate limit",
            latency=1.2,
            message_token_count=80,
            answer_token_count=20,
            total_token_count=100,
            total_price=0.01,
            answer="err",
        )
        service = ConversationService(db=SimpleNamespace())
        messages_by_id = {m1.id: m1, m2.id: m2}
        monkeypatch.setattr(service, "get", lambda _cls, msg_id: messages_by_id.get(msg_id))

        res = service.compare_messages(m1.id, m2.id, account)

        assert res["target"]["id"] == str(m1.id)
        assert res["target"]["error"] == ""
        assert res["base"]["id"] == str(m2.id)
        assert res["base"]["error"] == "rate limit"
        assert res["diff"]["latency_diff"] == pytest.approx(1.3)
        assert res["diff"]["total_token_count_diff"] == 50
        assert res["diff"]["message_token_count_diff"] == 20
        assert res["diff"]["answer_token_count_diff"] == 30
        assert res["diff"]["total_price_diff"] == pytest.approx(0.02)
        assert res["diff"]["status_changed"] is True
        assert res["diff"]["error_changed"] is True
        assert res["diff"]["answer_match"] is False
        assert res["diff"]["answer_length_diff"] == 8
        assert res["target"]["answer_length"] == 11
        assert res["base"]["answer_length"] == 3

    def test_compare_messages_should_raise_when_not_found(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        service = ConversationService(db=SimpleNamespace())
        monkeypatch.setattr(service, "get", lambda _cls, _id: None)

        with pytest.raises(NotFoundException):
            service.compare_messages(uuid4(), uuid4(), account)

    def test_compare_messages_should_raise_when_cross_app(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        m1 = SimpleNamespace(
            id=uuid4(),
            app_id=uuid4(),
            created_by=account.id,
            is_deleted=False,
            status="normal",
        )
        m2 = SimpleNamespace(
            id=uuid4(),
            app_id=uuid4(),
            created_by=account.id,
            is_deleted=False,
            status="normal",
        )
        service = ConversationService(db=SimpleNamespace())
        messages_by_id = {m1.id: m1, m2.id: m2}
        monkeypatch.setattr(service, "get", lambda _cls, msg_id: messages_by_id.get(msg_id))

        with pytest.raises(ValidateErrorException, match="只能对比同一应用下的运行消息"):
            service.compare_messages(m1.id, m2.id, account)

    def test_get_message_trace_should_return_timeline(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        msg = SimpleNamespace(
            id=uuid4(),
            conversation_id=uuid4(),
            app_id=uuid4(),
            created_by=account.id,
            is_deleted=False,
            status="normal",
            error="",
            latency=1.2,
            total_token_count=100,
            total_price=0.01,
            created_at=datetime(2024, 1, 1, 0, 0, 0),
        )
        thought = SimpleNamespace(
            id=uuid4(),
            position=1,
            event="agent_action",
            thought="calling tool",
            observation="done",
            tool="search",
            tool_input={"q": "test"},
            latency=0.5,
            total_token_count=50,
            total_price=0.005,
            created_at=datetime(2024, 1, 1, 0, 0, 1),
        )
        mock_query = SimpleNamespace(
            filter=lambda *args: SimpleNamespace(
                order_by=lambda *args: SimpleNamespace(all=lambda: [thought])
            )
        )
        service = ConversationService(db=SimpleNamespace(session=SimpleNamespace(query=lambda *args: mock_query)))
        monkeypatch.setattr(service, "get", lambda _cls, _id: msg)

        res = service.get_message_trace(msg.id, account)
        assert res["message_id"] == str(msg.id)
        assert res["status"] == "normal"
        assert len(res["timeline"]) == 1
        assert res["timeline"][0]["tool"] == "search"
        assert res["timeline"][0]["position"] == 1

    def test_get_message_trace_should_raise_when_message_not_found(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        service = ConversationService(db=SimpleNamespace())
        monkeypatch.setattr(service, "get", lambda _cls, _id: None)

        with pytest.raises(NotFoundException):
            service.get_message_trace(uuid4(), account)

    def test_build_replay_snapshot_should_extract_snapshots_and_apply_patch(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        msg = SimpleNamespace(
            id=uuid4(),
            conversation_id=uuid4(),
            app_id=uuid4(),
            created_by=account.id,
            is_deleted=False,
            query="hello world",
            image_urls=["http://img.png"],
        )
        app_config = SimpleNamespace(
            model_config={"model": "gpt-4o"},
            preset_prompt="base prompt",
            retrieval_config={"top_k": 3},
            tools=["search"],
            datasets=[],
            workflows=[],
        )
        app = SimpleNamespace(id=msg.app_id, draft_app_config=app_config)

        service = ConversationService(db=SimpleNamespace())
        monkeypatch.setattr(service, "get_message", lambda _mid, _acc: msg)
        monkeypatch.setattr(service, "get", lambda model, _id: app if model is App else SimpleNamespace())

        patch = {"preset_prompt": "new prompt", "tools": ["python_repl"]}
        snapshot = service.build_replay_snapshot(msg.id, patch, account)

        assert snapshot["message_id"] == str(msg.id)
        assert snapshot["input_snapshot"]["query"] == "hello world"
        assert snapshot["config_snapshot"]["preset_prompt"] == "base prompt"
        assert snapshot["patched_config"]["preset_prompt"] == "new prompt"
        assert snapshot["patched_config"]["tools"] == ["python_repl"]
        assert snapshot["applied_patch_keys"] == ["preset_prompt", "tools"]

    def test_build_replay_snapshot_should_reject_unsupported_patch_keys(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        msg = SimpleNamespace(id=uuid4(), conversation_id=uuid4(), app_id=uuid4())
        service = ConversationService(db=SimpleNamespace())
        monkeypatch.setattr(service, "get_message", lambda _mid, _acc: msg)
        monkeypatch.setattr(service, "get", lambda *_args: None)

        with pytest.raises(ValidateErrorException, match="不支持的回放Patch配置项"):
            service.build_replay_snapshot(msg.id, {"dangerous_action": True}, account)

    def test_build_replay_snapshot_should_reject_non_dict_patch(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        msg = SimpleNamespace(id=uuid4(), conversation_id=uuid4(), app_id=uuid4())
        service = ConversationService(db=SimpleNamespace())
        monkeypatch.setattr(service, "get_message", lambda _mid, _acc: msg)
        monkeypatch.setattr(service, "get", lambda *_args: None)

        for invalid_patch in ["string_patch", [1, 2, 3], 12345, True]:
            with pytest.raises(ValidateErrorException, match="回放Patch配置必须为字典对象"):
                service.build_replay_snapshot(msg.id, invalid_patch, account)

    def test_build_replay_snapshot_should_not_leak_draft_app_config_for_service_api(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        msg = SimpleNamespace(
            id=uuid4(),
            conversation_id=uuid4(),
            app_id=uuid4(),
            created_by=account.id,
            is_deleted=False,
            query="api message query",
            image_urls=[],
            invoke_from=InvokeFrom.SERVICE_API.value,
        )
        app_config = SimpleNamespace(
            model_config={"model": "gpt-4o"},
            preset_prompt="secret system prompt",
            retrieval_config={"top_k": 5},
            tools=["secret_tool"],
            datasets=["secret_dataset"],
            workflows=["secret_workflow"],
        )
        app = SimpleNamespace(id=msg.app_id, account_id=account.id, draft_app_config=app_config)

        service = ConversationService(db=SimpleNamespace())
        monkeypatch.setattr(service, "get_message", lambda _mid, _acc: msg)
        monkeypatch.setattr(service, "get", lambda model, _id: app if model is App else SimpleNamespace())

        snapshot = service.build_replay_snapshot(msg.id, {}, account)
        assert snapshot["config_snapshot"]["preset_prompt"] == ""
        assert snapshot["config_snapshot"]["model_config"] == {}
        assert snapshot["config_snapshot"]["tools"] == []
        assert snapshot["config_snapshot"]["datasets"] == []
        assert snapshot["config_snapshot"]["workflows"] == []

    def test_build_replay_snapshot_should_raise_not_found_on_app_ownership_mismatch(self, monkeypatch):
        account = SimpleNamespace(id=uuid4())
        other_account_id = uuid4()
        msg = SimpleNamespace(
            id=uuid4(),
            conversation_id=uuid4(),
            app_id=uuid4(),
            created_by=account.id,
            is_deleted=False,
            query="test",
            image_urls=[],
            invoke_from="debugger",
        )
        app = SimpleNamespace(id=msg.app_id, account_id=other_account_id, draft_app_config=None)

        service = ConversationService(db=SimpleNamespace())
        monkeypatch.setattr(service, "get_message", lambda _mid, _acc: msg)
        monkeypatch.setattr(service, "get", lambda model, _id: app if model is App else SimpleNamespace())

        with pytest.raises(NotFoundException):
            service.build_replay_snapshot(msg.id, {}, account)
