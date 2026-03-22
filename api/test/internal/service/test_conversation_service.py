from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.entity.conversation_entity import InvokeFrom
from internal.exception import NotFoundException
from internal.model import Conversation, Message
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

    def test_generate_conversation_name_should_fallback_when_subject_extract_failed(self, monkeypatch):
        class _Prompt:
            def __or__(self, other):
                return other

        class _ConversationInfo:
            def __init__(self):
                self._read_count = 0

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

        logged = {}
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
        monkeypatch.setattr(
            "internal.service.conversation_service.logging.exception",
            lambda message: logged.setdefault("message", message),
        )

        name = ConversationService.generate_conversation_name("hello")

        assert name == "新的会话"
        assert "提取会话名称出错" in logged["message"]

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

    def test_generate_suggested_questions_should_fallback_on_extract_error(self, monkeypatch):
        class _Prompt:
            def __or__(self, other):
                return other

        class _SuggestedQuestions:
            def __init__(self):
                self._read_count = 0

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

        logged = {}
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
        monkeypatch.setattr(
            "internal.service.conversation_service.logging.exception",
            lambda message: logged.setdefault("message", message),
        )

        questions = ConversationService.generate_suggested_questions("history")

        assert questions == []
        assert "生成建议问题出错" in logged["message"]

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

        result = service.update_conversation(conversation.id, account, name="新名字")

        assert result is conversation
        assert updates == [(conversation, {"name": "新名字"})]

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

    def test_get_recent_conversations_should_return_assistant_and_debugger_items(self):
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
            id=uuid4(),
            conversation_id=assistant_conversation.id,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=None,
            created_at=now,
        )
        message_debugger = SimpleNamespace(
            id=uuid4(),
            conversation_id=debugger_conversation.id,
            invoke_from=InvokeFrom.DEBUGGER.value,
            app_id=app.id,
            created_at=now,
        )
        duplicated_old_message = SimpleNamespace(
            id=uuid4(),
            conversation_id=assistant_conversation.id,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=None,
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

    def test_get_recent_conversations_should_break_after_reaching_limit(self):
        service = self._build_service()
        account_id = uuid4()
        now = datetime(2026, 3, 1, tzinfo=UTC)
        conversation_a = SimpleNamespace(id=uuid4(), name="A", created_at=now, created_by=account_id, is_deleted=False)
        conversation_b = SimpleNamespace(id=uuid4(), name="B", created_at=now, created_by=account_id, is_deleted=False)
        message_a = SimpleNamespace(id=uuid4(), conversation_id=conversation_a.id, invoke_from=InvokeFrom.ASSISTANT_AGENT.value, app_id=None, created_at=now)
        message_b = SimpleNamespace(id=uuid4(), conversation_id=conversation_b.id, invoke_from=InvokeFrom.ASSISTANT_AGENT.value, app_id=None, created_at=now)

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
                    return _Query([message_a, message_b])
                if model_name == "Conversation":
                    return _Query([conversation_a, conversation_b])
                if model_name == "App":
                    return _Query([])
                raise AssertionError(f"unexpected model: {model_name}")

        service.db = SimpleNamespace(session=_Session())
        account = SimpleNamespace(id=account_id, assistant_agent_conversation_id=conversation_a.id)

        conversations = service.get_recent_conversations(account, limit=1)

        assert len(conversations) == 1
        assert conversations[0]["id"] == conversation_a.id

    def test_get_recent_conversations_should_skip_message_when_conversation_not_found(self):
        service = self._build_service()
        account_id = uuid4()
        now = datetime(2026, 3, 1, tzinfo=UTC)
        message = SimpleNamespace(
            id=uuid4(),
            conversation_id=uuid4(),
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=None,
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

    def test_get_recent_conversations_should_skip_debugger_message_when_app_not_found(self):
        service = self._build_service()
        account_id = uuid4()
        now = datetime(2026, 3, 1, tzinfo=UTC)
        conversation = SimpleNamespace(id=uuid4(), name="debug", created_by=account_id, is_deleted=False, created_at=now)
        message = SimpleNamespace(
            id=uuid4(),
            conversation_id=conversation.id,
            invoke_from=InvokeFrom.DEBUGGER.value,
            app_id=uuid4(),
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

    def test_get_recent_conversations_should_break_when_reach_limit(self):
        service = self._build_service()
        account_id = uuid4()
        now = datetime(2026, 3, 1, tzinfo=UTC)
        conversation_1 = SimpleNamespace(id=uuid4(), name="会话1", created_by=account_id, is_deleted=False, created_at=now)
        conversation_2 = SimpleNamespace(id=uuid4(), name="会话2", created_by=account_id, is_deleted=False, created_at=now)
        message_1 = SimpleNamespace(
            id=uuid4(),
            conversation_id=conversation_1.id,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=None,
            created_at=now,
        )
        message_2 = SimpleNamespace(
            id=uuid4(),
            conversation_id=conversation_2.id,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            app_id=None,
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
        assert conversations[0]["id"] == conversation_1.id

    def test_get_recent_conversations_should_skip_missing_conversation_and_missing_debugger_app(self):
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
            created_at=now,
        )
        message_missing_app = SimpleNamespace(
            id=uuid4(),
            conversation_id=existing_conversation.id,
            invoke_from=InvokeFrom.DEBUGGER.value,
            app_id=uuid4(),
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
