from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from internal.entity.conversation_entity import InvokeFrom, MessageStatus
from internal.lib.helper import datetime_to_timestamp
from internal.service.conversation_service import ConversationService


ASSISTANT_AGENT_ID = UUID("00000000-0000-0000-0000-00000000aa01")


class _QueryStub:
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


class _SessionQueue:
    def __init__(self, query_results):
        self._query_results = list(query_results)

    def query(self, _model):
        if not self._query_results:
            raise AssertionError("unexpected query call")
        return _QueryStub(self._query_results.pop(0))


def _build_service(*query_results):
    return ConversationService(db=SimpleNamespace(session=_SessionQueue(query_results)))


def _account(**kwargs):
    payload = {
        "id": uuid4(),
        "assistant_agent_conversation_id": None,
    }
    payload.update(kwargs)
    return SimpleNamespace(**payload)


def _conversation(
    *,
    conversation_id: UUID | None = None,
    name: str,
    account_id: UUID,
    created_at: datetime | None = None,
):
    return SimpleNamespace(
        id=conversation_id or uuid4(),
        name=name,
        created_by=account_id,
        is_deleted=False,
        created_at=created_at or datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
    )


def _message(
    *,
    conversation_id: UUID,
    account_id: UUID,
    query: str,
    answer: str,
    invoke_from: str,
    app_id: UUID | None = None,
    created_at: datetime | None = None,
):
    return SimpleNamespace(
        id=uuid4(),
        conversation_id=conversation_id,
        app_id=app_id,
        created_by=account_id,
        query=query,
        answer=answer,
        invoke_from=invoke_from,
        status=MessageStatus.NORMAL.value,
        is_deleted=False,
        created_at=created_at or datetime(2024, 1, 2, 0, 0, 0, tzinfo=UTC),
    )


def _app(*, app_id: UUID, name: str, debug_conversation_id: UUID | None = None):
    return SimpleNamespace(
        id=app_id,
        name=name,
        debug_conversation_id=debug_conversation_id,
    )


class TestConversationSearchService:
    def test_search_conversations_should_delegate_blank_query_to_recent_conversations(self, monkeypatch):
        service = _build_service()
        account = _account()
        calls = []

        monkeypatch.setattr(
            service,
            "get_recent_conversations",
            lambda current_account, limit: calls.append((current_account, limit)) or [{"id": "recent"}],
        )

        results = service.search_conversations(account, "   ", limit=999)

        assert results == [{"id": "recent"}]
        assert calls == [(account, 100)]

    def test_search_conversations_should_return_debugger_match_with_current_fields(self, app):
        account = _account()
        conversation = _conversation(name="Python教程", account_id=account.id)
        debug_app_id = uuid4()
        message = _message(
            conversation_id=conversation.id,
            account_id=account.id,
            query="如何学习Python",
            answer="Python是一门很好的编程语言",
            invoke_from=InvokeFrom.DEBUGGER.value,
            app_id=debug_app_id,
        )
        debug_app = _app(
            app_id=debug_app_id,
            name="调试应用",
            debug_conversation_id=conversation.id,
        )
        service = _build_service(
            [message],
            [conversation],
            [debug_app],
        )

        with app.app_context():
            app.config["ASSISTANT_AGENT_ID"] = ASSISTANT_AGENT_ID
            results = service.search_conversations(account, "python", limit=10)

        assert len(results) == 1
        result = results[0]
        assert result["id"] == str(conversation.id)
        assert result["name"] == "Python教程"
        assert result["source_type"] == "app_debugger"
        assert result["app_id"] == str(debug_app_id)
        assert result["app_name"] == "调试应用"
        assert result["human_message"] == "如何学习Python"
        assert result["ai_message"] == "Python是一门很好的编程语言"
        assert set(result["matched_fields"]) == {"name", "human_message", "ai_message"}
        assert result["message_id"] == str(message.id)

    def test_search_conversations_should_return_name_match_even_without_messages(self, app):
        account = _account()
        conversation = _conversation(name="天气查询系统", account_id=account.id)
        assistant_app = _app(app_id=ASSISTANT_AGENT_ID, name="辅助Agent")
        service = _build_service(
            [],
            [conversation],
            [assistant_app],
        )

        with app.app_context():
            app.config["ASSISTANT_AGENT_ID"] = ASSISTANT_AGENT_ID
            results = service.search_conversations(account, "天气", limit=10)

        assert len(results) == 1
        result = results[0]
        assert result["name"] == "天气查询系统"
        assert result["source_type"] == "assistant_agent"
        assert result["agent_name"] == "OpenAgent"
        assert result["human_message"] == ""
        assert result["ai_message"] == ""
        assert result["matched_fields"] == ["name"]
        assert result["latest_message_at"] == datetime_to_timestamp(conversation.created_at)

    def test_search_conversations_should_not_return_unrelated_qa_for_title_only_match(self, app):
        account = _account()
        conversation = _conversation(name="Python 标题命中", account_id=account.id)
        latest_message = _message(
            conversation_id=conversation.id,
            account_id=account.id,
            query="这是最近一条但不包含关键词的问题",
            answer="这是最近一条但不包含关键词的回答",
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        assistant_app = _app(app_id=ASSISTANT_AGENT_ID, name="辅助Agent")
        service = _build_service(
            [latest_message],
            [conversation],
            [assistant_app],
        )

        with app.app_context():
            app.config["ASSISTANT_AGENT_ID"] = ASSISTANT_AGENT_ID
            results = service.search_conversations(account, "python", limit=10)

        assert len(results) == 1
        result = results[0]
        assert result["name"] == "Python 标题命中"
        assert result["human_message"] == ""
        assert result["ai_message"] == ""
        assert result["matched_fields"] == ["name"]
        assert result["message_id"] == str(latest_message.id)

    def test_search_conversations_should_return_empty_when_nothing_matches(self, app):
        account = _account()
        service = _build_service(
            [],
            [],
            [],
        )

        with app.app_context():
            app.config["ASSISTANT_AGENT_ID"] = ASSISTANT_AGENT_ID
            results = service.search_conversations(account, "不存在的内容xyz", limit=10)

        assert results == []

    def test_search_conversations_should_truncate_long_match_and_keep_one_result_per_conversation(self, app):
        account = _account()
        conversation = _conversation(name="长消息测试", account_id=account.id)
        long_query = "前缀" * 80 + "Python" + "后缀" * 80
        long_answer = "答案" * 90 + "PYTHON" + "结尾" * 90
        first_message = _message(
            conversation_id=conversation.id,
            account_id=account.id,
            query=long_query,
            answer=long_answer,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            created_at=datetime(2024, 1, 3, 0, 0, 0, tzinfo=UTC),
        )
        second_message = _message(
            conversation_id=conversation.id,
            account_id=account.id,
            query="Python补充问题",
            answer="补充答案",
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
            created_at=datetime(2024, 1, 2, 0, 0, 0, tzinfo=UTC),
        )
        assistant_app = _app(app_id=ASSISTANT_AGENT_ID, name="辅助Agent")
        service = _build_service(
            [first_message, second_message],
            [conversation],
            [assistant_app],
        )

        with app.app_context():
            app.config["ASSISTANT_AGENT_ID"] = ASSISTANT_AGENT_ID
            results = service.search_conversations(account, "python", limit=1)

        assert len(results) == 1
        result = results[0]
        assert result["name"] == "长消息测试"
        assert "Python" in result["human_message"] or "PYTHON" in result["human_message"]
        assert "PYTHON" in result["ai_message"] or "Python" in result["ai_message"]
        assert len(result["human_message"]) < len(long_query)
        assert len(result["ai_message"]) < len(long_answer)
        assert set(result["matched_fields"]) == {"human_message", "ai_message"}
