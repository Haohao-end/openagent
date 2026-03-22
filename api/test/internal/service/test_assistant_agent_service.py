from contextlib import contextmanager
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4
import json

import pytest
from werkzeug.datastructures import FileStorage

from internal.core.agent.entities.queue_entity import AgentThought, QueueEvent
from internal.entity.app_entity import DEFAULT_APP_CONFIG
from internal.entity.conversation_entity import InvokeFrom
from internal.entity.workflow_entity import WorkflowStatus
from internal.exception import FailException, NotFoundException
from internal.model import ApiTool, AppDatasetJoin, Dataset, Message, Workflow
from internal.service.app_config_service import AppConfigService
from internal.service.assistant_agent_service import AssistantAgentService
from internal.service.cos_service import CosService
from internal.service.embeddings_service import EmbeddingsService
from internal.service.faiss_service import FaissService
from internal.service.upload_file_service import UploadFileService
from internal.service.vector_database_service import VectorDatabaseService


@contextmanager
def _null_context():
    yield


class _QueryStub:
    def __init__(self, *, all_result=None):
        self._all_result = all_result if all_result is not None else []

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return self._all_result


class TestAssistantAgentService:
    def _build_service(self):
        return AssistantAgentService(
            db=SimpleNamespace(session=SimpleNamespace(query=lambda *_args, **_kwargs: _QueryStub(all_result=[]))),
            faiss_service=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            redis_client=SimpleNamespace(
                get=lambda key: None,
                setex=lambda key, ttl, value: None,
                scan=lambda cursor, match, count: (0, []),
                delete=lambda *keys: None,
            ),
        )

    def test_extract_chunk_content_should_support_common_types(self):
        assert AssistantAgentService._extract_chunk_content(None) == ""
        assert AssistantAgentService._extract_chunk_content("hello") == "hello"
        assert AssistantAgentService._extract_chunk_content({"text": "world"}) == "world"
        assert AssistantAgentService._extract_chunk_content(["a", {"text": "b"}]) == "ab"

    def test_contains_markdown_and_ensure_markdown_should_work_for_plain_text(self):
        assert AssistantAgentService._contains_markdown_syntax("### title\n- item") is True
        assert AssistantAgentService._contains_markdown_syntax("plain text") is False

        markdown = AssistantAgentService._ensure_introduction_markdown(
            "欢迎使用。你可以创建应用。建议先定义目标。",
            display_name="开发者",
        )
        assert markdown.startswith("### Hi，开发者")
        assert "#### 建议下一步" in markdown

    def test_stop_chat_should_delegate_to_agent_queue_manager(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "internal.service.assistant_agent_service.AgentQueueManager.set_stop_flag",
            lambda task_id, invoke_from, account_id: calls.append((task_id, invoke_from, account_id)),
        )
        task_id = uuid4()
        account = SimpleNamespace(id=uuid4())

        AssistantAgentService.stop_chat(task_id, account)

        assert calls[0][0] == task_id
        assert calls[0][2] == account.id

    def test_delete_conversation_should_clear_account_reference(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4(), assistant_agent_conversation_id=uuid4())
        updates = []
        cache_clears = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)),
        )
        monkeypatch.setattr(
            service,
            "_clear_introduction_cache",
            lambda account_id: cache_clears.append(account_id),
        )

        service.delete_conversation(account)

        assert updates == [(account, {"assistant_agent_conversation_id": None})]
        assert cache_clears == [account.id]

    def test_resolve_conversation_id_should_parse_uuid_or_return_none(self):
        conversation_id = uuid4()

        assert AssistantAgentService._resolve_conversation_id("") is None
        assert AssistantAgentService._resolve_conversation_id("   ") is None
        assert AssistantAgentService._resolve_conversation_id(str(conversation_id)) == conversation_id

    def test_resolve_assistant_agent_conversation_should_return_active_when_id_absent(self):
        service = self._build_service()
        active_conversation = SimpleNamespace(id=uuid4())
        account = SimpleNamespace(assistant_agent_conversation=active_conversation)

        result = service._resolve_assistant_agent_conversation(account=account, conversation_id=None)

        assert result is active_conversation

    def test_resolve_assistant_agent_conversation_should_validate_and_sync(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(
            id=uuid4(),
            assistant_agent_conversation_id=uuid4(),
        )
        conversation = SimpleNamespace(
            id=uuid4(),
            created_by=account.id,
            is_deleted=False,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: conversation)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)),
        )

        result = service._resolve_assistant_agent_conversation(
            account=account,
            conversation_id=conversation.id,
            sync_active=True,
        )

        assert result is conversation
        assert updates == [(account, {"assistant_agent_conversation_id": conversation.id})]

    def test_resolve_assistant_agent_conversation_should_not_sync_when_target_already_active(self, monkeypatch):
        service = self._build_service()
        conversation_id = uuid4()
        account = SimpleNamespace(
            id=uuid4(),
            assistant_agent_conversation_id=conversation_id,
        )
        conversation = SimpleNamespace(
            id=conversation_id,
            created_by=account.id,
            is_deleted=False,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: conversation)
        updates = []
        monkeypatch.setattr(
            service,
            "update",
            lambda target, **kwargs: updates.append((target, kwargs)),
        )

        result = service._resolve_assistant_agent_conversation(
            account=account,
            conversation_id=conversation.id,
            sync_active=True,
        )

        assert result is conversation
        assert updates == []

    def test_resolve_assistant_agent_conversation_should_raise_when_invalid(self, monkeypatch):
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        conversation_id = uuid4()

        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: None)
        with pytest.raises(NotFoundException):
            service._resolve_assistant_agent_conversation(account=account, conversation_id=conversation_id)

        invalid_conversation = SimpleNamespace(
            id=conversation_id,
            created_by=uuid4(),
            is_deleted=False,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        monkeypatch.setattr(service, "get", lambda *_args, **_kwargs: invalid_conversation)
        with pytest.raises(NotFoundException):
            service._resolve_assistant_agent_conversation(account=account, conversation_id=conversation_id)

    def test_generate_message_fingerprint_should_create_consistent_hash(self):
        service = AssistantAgentService(
            db=SimpleNamespace(),
            faiss_service=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            redis_client=SimpleNamespace(),
        )
        message_ids = ["msg1", "msg2", "msg3"]
        summary = "用户关注AI应用开发"

        fingerprint1 = service._generate_message_fingerprint(message_ids, summary)
        fingerprint2 = service._generate_message_fingerprint(message_ids, summary)

        assert fingerprint1 == fingerprint2
        assert len(fingerprint1) == 32  # MD5 hash length

        # 不同的输入应该产生不同的指纹
        different_fingerprint = service._generate_message_fingerprint(
            ["msg1", "msg2"], summary
        )
        assert fingerprint1 != different_fingerprint

    def test_get_cached_introduction_should_return_none_when_cache_miss(self):
        redis_mock = SimpleNamespace(get=lambda key: None)
        service = AssistantAgentService(
            db=SimpleNamespace(),
            faiss_service=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            redis_client=redis_mock,
        )
        account_id = uuid4()
        fingerprint = "abc123"

        result = service._get_cached_introduction(account_id, fingerprint)

        assert result is None

    def test_get_cached_introduction_should_return_data_when_cache_hit(self):
        cached_data = {
            "introduction": "### Hi，开发者\n\n欢迎回来！",
            "suggested_questions_message_id": "msg123",
            "generated_at": "2026-02-28T10:00:00Z",
        }
        redis_mock = SimpleNamespace(
            get=lambda key: json.dumps(cached_data, ensure_ascii=False).encode("utf-8")
        )
        service = AssistantAgentService(
            db=SimpleNamespace(),
            faiss_service=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            redis_client=redis_mock,
        )
        account_id = uuid4()
        fingerprint = "abc123"

        result = service._get_cached_introduction(account_id, fingerprint)

        assert result == cached_data
        assert result["introduction"] == "### Hi，开发者\n\n欢迎回来！"

    def test_get_cached_introduction_should_return_none_when_redis_failed(self):
        service = AssistantAgentService(
            db=SimpleNamespace(),
            faiss_service=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            redis_client=SimpleNamespace(get=lambda _key: (_ for _ in ()).throw(RuntimeError("redis down"))),
        )

        result = service._get_cached_introduction(uuid4(), "fingerprint")

        assert result is None

    def test_set_cached_introduction_should_store_data_with_ttl(self):
        setex_calls = []
        redis_mock = SimpleNamespace(
            setex=lambda key, ttl, value: setex_calls.append((key, ttl, value))
        )
        service = AssistantAgentService(
            db=SimpleNamespace(),
            faiss_service=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            redis_client=redis_mock,
        )
        account_id = uuid4()
        fingerprint = "abc123"
        data = {
            "introduction": "### Hi，开发者",
            "suggested_questions_message_id": "msg123",
        }

        service._set_cached_introduction(account_id, fingerprint, data, ttl=3600)

        assert len(setex_calls) == 1
        key, ttl, value = setex_calls[0]
        assert f"assistant_agent:introduction:{account_id}:{fingerprint}" == key
        assert ttl == 3600
        assert json.loads(value) == data

    def test_get_conversation_messages_with_page_should_filter_by_conversation_id(self, monkeypatch):
        """
        测试：验证修复了竞态条件导致的消息不显示问题

        问题描述：
        用户访问 /home?conversation_id=xxx 时，前端在 onMounted 时立即查询消息。
        但此时消息还没有被插入到数据库中，导致查询返回 0 条记录。

        修复方案：
        后端应该正确处理 conversation_id 参数，确保查询返回正确的消息。
        """
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        conversation_id = uuid4()

        # 模拟请求对象
        req = SimpleNamespace(
            conversation_id=SimpleNamespace(data=str(conversation_id)),
            current_page=SimpleNamespace(data=1),
            page_size=SimpleNamespace(data=5),
            created_at=SimpleNamespace(data=0),
        )

        # 模拟对话对象
        conversation = SimpleNamespace(
            id=conversation_id,
            created_by=account.id,
            is_deleted=False,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )

        # 模拟消息对象
        message = SimpleNamespace(
            id=uuid4(),
            conversation_id=conversation_id,
            query="你好",
            answer="你好，我是助手",
            status="normal",
            is_deleted=False,
            agent_thoughts=[],
        )

        # 模拟数据库查询
        def mock_get(model, conversation_id_param):
            if model == "Conversation" and conversation_id_param == conversation_id:
                return conversation
            return None

        monkeypatch.setattr(service, "get", mock_get)

        # 模拟分页查询
        paginator_calls = []
        def mock_paginate(query):
            paginator_calls.append(query)
            return [message.id]

        monkeypatch.setattr(service, "db", SimpleNamespace(
            session=SimpleNamespace(
                query=lambda *args, **kwargs: SimpleNamespace(
                    filter=lambda *args, **kwargs: SimpleNamespace(
                        order_by=lambda *args, **kwargs: SimpleNamespace(
                            all=lambda: [message]
                        )
                    ),
                    options=lambda *args, **kwargs: SimpleNamespace(
                        filter=lambda *args, **kwargs: SimpleNamespace(
                            order_by=lambda *args, **kwargs: SimpleNamespace(
                                all=lambda: [message]
                            )
                        )
                    )
                )
            )
        ))

        # 调用方法
        messages, paginator = service.get_conversation_messages_with_page(req, account)

        # 验证结果
        assert len(messages) == 1
        assert messages[0].id == message.id
        assert messages[0].query == "你好"
        assert messages[0].answer == "你好，我是助手"

    def test_get_conversation_messages_with_page_should_handle_empty_conversation_id(self, monkeypatch):
        """
        测试：当 conversation_id 为空时，应该使用账号的默认会话
        """
        service = self._build_service()
        account = SimpleNamespace(id=uuid4())
        default_conversation_id = uuid4()

        # 模拟请求对象（conversation_id 为空）
        req = SimpleNamespace(
            conversation_id=SimpleNamespace(data=""),
            current_page=SimpleNamespace(data=1),
            page_size=SimpleNamespace(data=5),
            created_at=SimpleNamespace(data=0),
        )

        # 模拟对话对象
        conversation = SimpleNamespace(
            id=default_conversation_id,
            created_by=account.id,
            is_deleted=False,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )

        account.assistant_agent_conversation = conversation

        # 模拟消息对象
        message = SimpleNamespace(
            id=uuid4(),
            conversation_id=default_conversation_id,
            query="你好",
            answer="你好，我是助手",
            status="normal",
            is_deleted=False,
            agent_thoughts=[],
        )

        # 模拟数据库查询
        def mock_get(model, conversation_id_param):
            if model == "Conversation" and conversation_id_param == default_conversation_id:
                return conversation
            return None

        monkeypatch.setattr(service, "get", mock_get)

        # 模拟分页查询
        monkeypatch.setattr(service, "db", SimpleNamespace(
            session=SimpleNamespace(
                query=lambda *args, **kwargs: SimpleNamespace(
                    filter=lambda *args, **kwargs: SimpleNamespace(
                        order_by=lambda *args, **kwargs: SimpleNamespace(
                            all=lambda: [message]
                        )
                    ),
                    options=lambda *args, **kwargs: SimpleNamespace(
                        filter=lambda *args, **kwargs: SimpleNamespace(
                            order_by=lambda *args, **kwargs: SimpleNamespace(
                                all=lambda: [message]
                            )
                        )
                    )
                )
            )
        ))

        # 调用方法
        messages, paginator = service.get_conversation_messages_with_page(req, account)

        # 验证结果
        assert len(messages) == 1
        assert messages[0].id == message.id

    def test_clear_introduction_cache_should_delete_all_account_caches(self):
        deleted_keys = []
        redis_mock = SimpleNamespace(
            scan=lambda cursor, match, count: (
                0,
                [
                    f"assistant_agent:introduction:{uuid4()}:hash1",
                    f"assistant_agent:introduction:{uuid4()}:hash2",
                ],
            )
            if cursor == 0
            else (0, []),
            delete=lambda *keys: deleted_keys.extend(keys),
        )
        service = AssistantAgentService(
            db=SimpleNamespace(),
            faiss_service=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            redis_client=redis_mock,
        )
        account_id = uuid4()

        service._clear_introduction_cache(account_id)

        assert len(deleted_keys) == 2

    def test_clear_introduction_cache_should_continue_scanning_until_cursor_zero(self):
        deleted_keys = []
        calls = {"count": 0}

        def _scan(cursor, match, count):
            calls["count"] += 1
            if calls["count"] == 1:
                return 1, ["cache-key-1"]
            return 0, ["cache-key-2"]

        service = AssistantAgentService(
            db=SimpleNamespace(),
            faiss_service=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            redis_client=SimpleNamespace(
                scan=_scan,
                delete=lambda *keys: deleted_keys.extend(keys),
            ),
        )

        service._clear_introduction_cache(uuid4())

        assert calls["count"] == 2
        assert deleted_keys == ["cache-key-1", "cache-key-2"]

    def test_clear_introduction_cache_should_not_delete_when_scan_returns_empty_keys(self):
        delete_calls = []
        service = AssistantAgentService(
            db=SimpleNamespace(),
            faiss_service=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            redis_client=SimpleNamespace(
                scan=lambda cursor, match, count: (0, []),
                delete=lambda *keys: delete_calls.append(keys),
            ),
        )

        service._clear_introduction_cache(uuid4())

        assert delete_calls == []

    def test_clear_introduction_cache_should_swallow_exception_when_scan_failed(self):
        service = AssistantAgentService(
            db=SimpleNamespace(),
            faiss_service=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            redis_client=SimpleNamespace(scan=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("scan-failed"))),
        )

        service._clear_introduction_cache(uuid4())

    def test_generate_introduction_cache_key_should_follow_pattern(self):
        service = AssistantAgentService(
            db=SimpleNamespace(),
            faiss_service=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            redis_client=SimpleNamespace(),
        )
        account_id = uuid4()
        fingerprint = "abc123def456"

        cache_key = service._generate_introduction_cache_key(account_id, fingerprint)

        assert cache_key == f"assistant_agent:introduction:{account_id}:{fingerprint}"
        assert cache_key.startswith("assistant_agent:introduction:")
        assert fingerprint in cache_key

    def test_convert_create_app_to_tool_should_trigger_async_task(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "internal.service.assistant_agent_service.auto_create_app.delay",
            lambda name, description, account_id: calls.append((name, description, account_id)),
        )
        account_id = uuid4()
        tool = AssistantAgentService.convert_create_app_to_tool(account_id)

        result = tool.invoke({"name": "客服助手", "description": "面向工单场景自动答疑"})

        assert calls == [("客服助手", "面向工单场景自动答疑", account_id)]
        assert "应用名称: 客服助手" in result

    def test_get_conversation_messages_with_page_should_delegate_query_and_paginate(self, monkeypatch):
        message_1 = SimpleNamespace(id=uuid4())
        message_2 = SimpleNamespace(id=uuid4())
        all_messages = [message_1, message_2]

        class _Query:
            def __init__(self, all_result=None):
                self.filter_calls = []
                self._all_result = all_result if all_result is not None else []

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
        message_query = _Query(all_result=all_messages)

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

        monkeypatch.setattr("internal.service.assistant_agent_service.Paginator", _Paginator)
        service = AssistantAgentService(
            db=SimpleNamespace(session=_Session()),
            faiss_service=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            redis_client=SimpleNamespace(),
        )
        req = SimpleNamespace(
            created_at=SimpleNamespace(data=int(datetime(2024, 1, 1, 0, 0, 0).timestamp())),
            conversation_id=SimpleNamespace(data=""),
        )
        account = SimpleNamespace(assistant_agent_conversation=SimpleNamespace(id=uuid4()))

        messages, paginator = service.get_conversation_messages_with_page(req, account)

        assert messages == all_messages
        assert isinstance(paginator, _Paginator)
        assert paginator.paginate_called is True
        # 包含 4 个固定过滤条件 + 1 个 created_at 条件
        assert len(id_query.filter_calls[0]) == 5

    def test_get_conversation_messages_with_page_should_skip_created_at_filter_when_absent(self, monkeypatch):
        message = SimpleNamespace(id=uuid4())

        class _Query:
            def __init__(self, all_result=None):
                self.filter_calls = []
                self._all_result = all_result if all_result is not None else []

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

        monkeypatch.setattr("internal.service.assistant_agent_service.Paginator", _Paginator)
        service = AssistantAgentService(
            db=SimpleNamespace(session=_Session()),
            faiss_service=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            redis_client=SimpleNamespace(),
        )
        req = SimpleNamespace(
            created_at=SimpleNamespace(data=None),
            conversation_id=SimpleNamespace(data=""),
        )
        account = SimpleNamespace(assistant_agent_conversation=SimpleNamespace(id=uuid4()))

        messages, _paginator = service.get_conversation_messages_with_page(req, account)

        assert messages == [message]
        assert len(id_query.filter_calls[0]) == 4

    def test_generate_introduction_should_return_first_time_done_when_no_history(self):
        class _Query:
            def __init__(self, rows):
                self._rows = rows

            def filter(self, *_args, **_kwargs):
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def all(self):
                return self._rows

        class _Session:
            def __init__(self):
                self._queries = [_Query([]), _Query([])]

            def query(self, _model):
                return self._queries.pop(0)

        service = AssistantAgentService(
            db=SimpleNamespace(session=_Session()),
            faiss_service=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            redis_client=SimpleNamespace(get=lambda key: None),
        )
        account = SimpleNamespace(id=uuid4(), name="新人")

        events = list(service.generate_introduction(account))

        assert len(events) == 1
        assert events[0].startswith("event: intro_done")
        payload = json.loads(events[0].split("data:", 1)[1].strip())
        assert payload["is_first_time"] is True
        assert payload["content"] == ""
        assert payload["message_id"] == ""

    def test_generate_introduction_should_stream_chunks_and_emit_markdown_done(self, monkeypatch):
        latest_message = SimpleNamespace(id=uuid4(), query="你好", answer="你好呀")

        class _Query:
            def __init__(self, rows):
                self._rows = rows

            def filter(self, *_args, **_kwargs):
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def all(self):
                return self._rows

        class _Session:
            def __init__(self):
                self._queries = [
                    _Query([latest_message]),
                    _Query([("历史偏好：关注自动化测试",)]),
                ]

            def query(self, _model):
                return self._queries.pop(0)

        class _FakeLLM:
            @staticmethod
            def stream(_messages):
                # 故意输出纯文本，验证服务会兜底格式化为 Markdown
                return iter(["欢迎回来。", "建议先定义你的目标。"])

        monkeypatch.setattr(
            "internal.service.assistant_agent_service.DeepSeekChat",
            lambda **_kwargs: _FakeLLM(),
        )
        service = AssistantAgentService(
            db=SimpleNamespace(session=_Session()),
            faiss_service=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            redis_client=SimpleNamespace(get=lambda key: None),
        )
        account = SimpleNamespace(id=uuid4(), name="测试用户")

        events = list(service.generate_introduction(account))

        assert any(item.startswith("event: intro_chunk") for item in events)
        done_event = [item for item in events if item.startswith("event: intro_done")][0]
        done_payload = json.loads(done_event.split("data:", 1)[1].strip())
        assert done_payload["is_first_time"] is False
        assert done_payload["suggested_questions_message_id"] == str(latest_message.id)
        assert done_payload["content"].startswith("### Hi，测试用户")

    def test_generate_introduction_should_use_cached_content_when_cache_hit(self, monkeypatch):
        latest_message = SimpleNamespace(id=uuid4(), query="你好", answer="你好呀")

        class _Query:
            def __init__(self, rows):
                self._rows = rows

            def filter(self, *_args, **_kwargs):
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def all(self):
                return self._rows

        class _Session:
            def __init__(self):
                self._queries = [
                    _Query([latest_message]),
                    _Query([("历史偏好：关注测试覆盖率",)]),
                ]

            def query(self, _model):
                return self._queries.pop(0)

        service = AssistantAgentService(
            db=SimpleNamespace(session=_Session()),
            faiss_service=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            redis_client=SimpleNamespace(),
        )
        cached_text = "### Hi，缓存用户\n\n欢迎回来，这是一段缓存介绍。"
        monkeypatch.setattr(
            service,
            "_get_cached_introduction",
            lambda *_args, **_kwargs: {
                "introduction": cached_text,
                "suggested_questions_message_id": "cached-msg-id",
            },
        )
        account = SimpleNamespace(id=uuid4(), name="缓存用户")

        events = list(service.generate_introduction(account))

        assert any(item.startswith("event: intro_chunk") for item in events)
        done_event = [item for item in events if item.startswith("event: intro_done")][0]
        done_payload = json.loads(done_event.split("data:", 1)[1].strip())
        assert done_payload["content"] == cached_text
        assert done_payload["message_id"] == "cached-msg-id"
        assert done_payload["suggested_questions_message_id"] == "cached-msg-id"

    def test_chat_should_stream_events_and_save_aggregated_agent_thoughts(self, monkeypatch, app):
        assistant_agent_id = uuid4()
        app.config["ASSISTANT_AGENT_ID"] = assistant_agent_id
        conversation = SimpleNamespace(id=uuid4(), summary="历史摘要")
        account = SimpleNamespace(id=uuid4(), assistant_agent_conversation=conversation)
        req = SimpleNamespace(
            query=SimpleNamespace(data="帮我创建一个客服Agent"),
            image_urls=SimpleNamespace(data=["https://example.com/demo.png"]),
            conversation_id=SimpleNamespace(data=""),
        )

        save_payload = {}
        service = AssistantAgentService(
            db=SimpleNamespace(session=SimpleNamespace()),
            faiss_service=SimpleNamespace(convert_faiss_to_tool=lambda: "faiss-tool"),
            conversation_service=SimpleNamespace(
                save_agent_thoughts=lambda **kwargs: save_payload.update(kwargs)
            ),
            redis_client=SimpleNamespace(),
        )

        message_id = uuid4()
        create_calls = []
        monkeypatch.setattr(
            service,
            "create",
            lambda model, **kwargs: create_calls.append((model, kwargs))
            or SimpleNamespace(id=message_id),
        )
        monkeypatch.setattr(
            service,
            "convert_create_app_to_tool",
            lambda _account_id: "create-app-tool",
        )

        llm_capture = {}

        class _FakeLLM:
            def __init__(self, **kwargs):
                llm_capture["kwargs"] = kwargs

            def convert_to_human_message(self, query, image_urls):
                llm_capture["human_message"] = (query, image_urls)
                return {"query": query, "image_urls": image_urls}

        class _FakeTokenBufferMemory:
            def __init__(self, db, conversation, model_instance):
                llm_capture["memory_args"] = (db, conversation, model_instance)

            def get_history_prompt_messages(self, message_limit):
                llm_capture["message_limit"] = message_limit
                return ["历史消息"]

        shared_event_id = uuid4()
        task_id = uuid4()
        stream_events = [
            AgentThought(id=uuid4(), task_id=task_id, event=QueueEvent.PING),
            AgentThought(
                id=shared_event_id,
                task_id=task_id,
                event=QueueEvent.AGENT_MESSAGE,
                thought="A",
                answer="A",
                message=[{"role": "assistant", "content": "A"}],
                message_token_count=1,
                total_token_count=1,
                latency=0.1,
            ),
            AgentThought(
                id=shared_event_id,
                task_id=task_id,
                event=QueueEvent.AGENT_MESSAGE,
                thought="B",
                answer="B",
                message=[{"role": "assistant", "content": "B"}],
                message_token_count=2,
                total_token_count=2,
                latency=0.2,
            ),
            AgentThought(
                id=uuid4(),
                task_id=task_id,
                event=QueueEvent.AGENT_ACTION,
                tool="create_app",
                tool_input={"name": "客服Agent"},
                observation="ok",
                latency=0.3,
            ),
        ]
        agent_capture = {}

        class _FakeFunctionCallAgent:
            def __init__(self, llm, agent_config):
                agent_capture["llm"] = llm
                agent_capture["agent_config"] = agent_config

            def stream(self, state):
                agent_capture["state"] = state
                return iter(stream_events)

        # AgentConfig 的 tools 字段会校验 BaseTool；这里仅验证服务编排逻辑，使用轻量对象替代。
        monkeypatch.setattr(
            "internal.service.assistant_agent_service.AgentConfig",
            lambda **kwargs: SimpleNamespace(**kwargs),
        )
        monkeypatch.setattr(
            "internal.service.assistant_agent_service.DeepSeekChat",
            lambda **kwargs: _FakeLLM(**kwargs),
        )
        monkeypatch.setattr(
            "internal.service.assistant_agent_service.TokenBufferMemory",
            _FakeTokenBufferMemory,
        )
        monkeypatch.setattr(
            "internal.service.assistant_agent_service.FunctionCallAgent",
            _FakeFunctionCallAgent,
        )

        with app.app_context():
            events = list(service.chat(req, account))

        assert create_calls[0][0] is Message
        assert create_calls[0][1]["app_id"] == assistant_agent_id
        assert create_calls[0][1]["conversation_id"] == conversation.id
        assert create_calls[0][1]["query"] == req.query.data
        assert create_calls[0][1]["image_urls"] == req.image_urls.data
        assert llm_capture["kwargs"]["model"] == "deepseek-chat"
        assert llm_capture["message_limit"] == 3
        assert llm_capture["human_message"] == (req.query.data, req.image_urls.data)
        assert len(agent_capture["agent_config"].tools) == 2
        assert agent_capture["state"]["history"] == ["历史消息"]
        assert agent_capture["state"]["long_term_memory"] == "历史摘要"
        assert len(events) == 4
        assert events[0].startswith("event: ping")
        first_payload = json.loads(events[1].split("data:", 1)[1].strip())
        assert first_payload["id"] == str(shared_event_id)
        assert save_payload["account_id"] == account.id
        assert save_payload["app_id"] == assistant_agent_id
        assert save_payload["conversation_id"] == conversation.id
        assert save_payload["message_id"] == message_id
        assert len(save_payload["agent_thoughts"]) == 2
        merged_message_thought = [
            item
            for item in save_payload["agent_thoughts"]
            if item.event == QueueEvent.AGENT_MESSAGE
        ][0]
        assert merged_message_thought.thought == "AB"
        assert merged_message_thought.answer == "AB"

    def test_generate_introduction_should_skip_empty_chunks(self, monkeypatch):
        latest_message = SimpleNamespace(id=uuid4(), query="你好", answer="你好呀")

        class _Query:
            def __init__(self, rows):
                self._rows = rows

            def filter(self, *_args, **_kwargs):
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def all(self):
                return self._rows

        class _Session:
            def __init__(self):
                self._queries = [
                    _Query([latest_message]),
                    _Query([("历史偏好：更关注自动化",)]),
                ]

            def query(self, _model):
                return self._queries.pop(0)

        class _FakeLLM:
            @staticmethod
            def stream(_messages):
                # 这里故意混入空分块，验证服务会跳过空输出分片。
                return iter(["", {"text": "欢迎回来。"}, None, "建议先定义目标。"])

        monkeypatch.setattr(
            "internal.service.assistant_agent_service.DeepSeekChat",
            lambda **_kwargs: _FakeLLM(),
        )
        service = AssistantAgentService(
            db=SimpleNamespace(session=_Session()),
            faiss_service=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            redis_client=SimpleNamespace(get=lambda key: None),
        )
        account = SimpleNamespace(id=uuid4(), name="测试用户")

        events = list(service.generate_introduction(account))

        intro_chunk_events = [item for item in events if item.startswith("event: intro_chunk")]
        assert len(intro_chunk_events) == 2
        done_event = [item for item in events if item.startswith("event: intro_done")][0]
        done_payload = json.loads(done_event.split("data:", 1)[1].strip())
        assert done_payload["is_first_time"] is False
        assert done_payload["suggested_questions_message_id"] == str(latest_message.id)

    def test_generate_introduction_should_emit_error_event_when_stream_failed(self, monkeypatch):
        latest_message = SimpleNamespace(id=uuid4(), query="你好", answer="你好呀")

        class _Query:
            def __init__(self, rows):
                self._rows = rows

            def filter(self, *_args, **_kwargs):
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def all(self):
                return self._rows

        class _Session:
            def __init__(self):
                self._queries = [
                    _Query([latest_message]),
                    _Query([("历史偏好：关注测试稳定性",)]),
                ]

            def query(self, _model):
                return self._queries.pop(0)

        class _FakeLLM:
            @staticmethod
            def stream(_messages):
                raise RuntimeError("stream boom")

        monkeypatch.setattr(
            "internal.service.assistant_agent_service.DeepSeekChat",
            lambda **_kwargs: _FakeLLM(),
        )
        service = AssistantAgentService(
            db=SimpleNamespace(session=_Session()),
            faiss_service=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            redis_client=SimpleNamespace(get=lambda key: None),
        )
        account = SimpleNamespace(id=uuid4(), name="测试用户")

        events = list(service.generate_introduction(account))

        assert len(events) == 1
        assert events[0].startswith("event: error")
        payload = json.loads(events[0].split("data:", 1)[1].strip())
        assert "个性化介绍生成失败" in payload["observation"]

    def test_get_conversations_should_return_active_flag_and_timestamps(self, app):
        assistant_agent_id = uuid4()
        app.config["ASSISTANT_AGENT_ID"] = assistant_agent_id
        active_id = uuid4()
        now = datetime.now()
        conversations = [
            SimpleNamespace(id=active_id, name="当前会话", updated_at=now, created_at=now),
            SimpleNamespace(id=uuid4(), name="历史会话", updated_at=now, created_at=now),
        ]

        class _MessageIdQuery:
            def filter(self, *_args, **_kwargs):
                return self

            def exists(self):
                return True

        class _ConversationQuery:
            def filter(self, *_args, **_kwargs):
                return self

            def order_by(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def all(self):
                return conversations

        class _Session:
            def __init__(self):
                self.calls = 0

            def query(self, _model):
                self.calls += 1
                if self.calls == 1:
                    return _MessageIdQuery()
                return _ConversationQuery()

        service = AssistantAgentService(
            db=SimpleNamespace(session=_Session()),
            faiss_service=SimpleNamespace(),
            conversation_service=SimpleNamespace(),
            redis_client=SimpleNamespace(),
        )
        req = SimpleNamespace(limit=SimpleNamespace(data=20))
        account = SimpleNamespace(id=uuid4(), assistant_agent_conversation_id=active_id)

        with app.app_context():
            result = service.get_conversations(req, account)

        assert len(result) == 2
        assert result[0]["id"] == active_id
        assert result[0]["is_active"] is True
        assert result[1]["is_active"] is False

    def test_extract_chunk_content_should_fallback_for_unknown_items(self):
        assert AssistantAgentService._extract_chunk_content([1, {"text": "b"}]) == "1b"
        assert AssistantAgentService._extract_chunk_content(123) == "123"

    def test_build_introduction_prompt_messages_should_skip_summary_and_empty_query_answer(self):
        account = SimpleNamespace(name="  ")
        messages = [
            SimpleNamespace(query="最近在做测试", answer=""),
            SimpleNamespace(query="", answer="建议先补单元测试"),
            SimpleNamespace(query=" ", answer=" "),
        ]

        prompt_messages = AssistantAgentService._build_introduction_prompt_messages(
            account=account,
            summary="",
            messages=messages,
        )

        contents = [getattr(item, "content", "") for item in prompt_messages]
        assert "用户历史会话摘要如下" not in "\n".join(contents)
        assert any("最近在做测试" in content for content in contents)
        assert any("建议先补单元测试" in content for content in contents)

    def test_contains_markdown_should_detect_code_fence(self):
        assert AssistantAgentService._contains_markdown_syntax(
            "```python\nprint('hello')\n```"
        ) is True

    def test_ensure_introduction_markdown_should_cover_fallback_branches(self):
        empty_markdown = AssistantAgentService._ensure_introduction_markdown(
            introduction="",
            display_name="开发者",
        )
        assert empty_markdown.startswith("### Hi，开发者")
        markdown = "### 已有标题\n- 建议项"
        assert (
            AssistantAgentService._ensure_introduction_markdown(
                introduction=markdown,
                display_name="开发者",
            )
            == markdown
        )
        punctuation_only = AssistantAgentService._ensure_introduction_markdown(
            introduction="。。。！！！",
            display_name="开发者",
        )
        assert punctuation_only.startswith("### Hi，开发者")
        assert "。。。！！！" in punctuation_only

    def test_ensure_introduction_markdown_should_not_add_suggestion_block_for_single_sentence(self):
        markdown = AssistantAgentService._ensure_introduction_markdown(
            introduction="欢迎回来",
            display_name="开发者",
        )

        assert markdown.startswith("### Hi，开发者")
        assert "#### 建议下一步" not in markdown

    def test_get_conversation_messages_with_page_should_include_messages_with_empty_answer(self, monkeypatch):
        """
        测试：验证修复了消息不显示问题

        问题描述：
        用户发送消息后，消息被创建但答案还在生成中（answer 为空）。
        前端立即查询消息时，后端因为过滤条件 Message.answer != "" 而返回 0 条记录。

        修复方案：
        改为只过滤 Message.query != ""，允许答案为空的消息显示。
        """
        service = self._build_service()
        account = SimpleNamespace(id=uuid4(), assistant_agent_conversation=None)
        conversation_id = uuid4()

        # 模拟请求对象
        req = SimpleNamespace(
            conversation_id=SimpleNamespace(data=str(conversation_id)),
            current_page=SimpleNamespace(data=1),
            page_size=SimpleNamespace(data=5),
            created_at=SimpleNamespace(data=0),
        )

        # 模拟对话对象
        conversation = SimpleNamespace(
            id=conversation_id,
            created_by=account.id,
            is_deleted=False,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )

        # 模拟消息对象 - 答案为空（正在生成中）
        message_with_empty_answer = SimpleNamespace(
            id=uuid4(),
            conversation_id=conversation_id,
            query="你好",
            answer="",  # 答案为空
            status="normal",
            is_deleted=False,
            agent_thoughts=[],
        )

        # 模拟 _resolve_assistant_agent_conversation 方法
        def mock_resolve_conversation(*args, **kwargs):
            return conversation

        monkeypatch.setattr(service, "_resolve_assistant_agent_conversation", mock_resolve_conversation)

        # 模拟分页器
        mock_paginator = SimpleNamespace(paginate=lambda query: [message_with_empty_answer.id])
        monkeypatch.setattr("internal.service.assistant_agent_service.Paginator", lambda **kwargs: mock_paginator)

        # 模拟分页查询
        monkeypatch.setattr(service, "db", SimpleNamespace(
            session=SimpleNamespace(
                query=lambda *args, **kwargs: SimpleNamespace(
                    filter=lambda *args, **kwargs: SimpleNamespace(
                        order_by=lambda *args, **kwargs: SimpleNamespace(
                            all=lambda: [message_with_empty_answer]
                        )
                    ),
                    options=lambda *args, **kwargs: SimpleNamespace(
                        filter=lambda *args, **kwargs: SimpleNamespace(
                            order_by=lambda *args, **kwargs: SimpleNamespace(
                                all=lambda: [message_with_empty_answer]
                            )
                        )
                    )
                )
            )
        ))

        # 调用方法
        messages, paginator = service.get_conversation_messages_with_page(req, account)

        # 验证结果 - 应该返回消息，即使答案为空
        assert len(messages) == 1
        assert messages[0].id == message_with_empty_answer.id
        assert messages[0].query == "你好"
        assert messages[0].answer == ""  # 答案为空也应该返回

    def test_get_conversation_messages_with_page_should_exclude_messages_with_empty_query(self, monkeypatch):
        """
        测试：验证仍然过滤掉 query 为空的消息

        说明：
        虽然允许答案为空，但仍然应该过滤掉用户提问为空的消息。
        """
        service = self._build_service()
        account = SimpleNamespace(id=uuid4(), assistant_agent_conversation=None)
        conversation_id = uuid4()

        # 模拟请求对象
        req = SimpleNamespace(
            conversation_id=SimpleNamespace(data=str(conversation_id)),
            current_page=SimpleNamespace(data=1),
            page_size=SimpleNamespace(data=5),
            created_at=SimpleNamespace(data=0),
        )

        # 模拟对话对象
        conversation = SimpleNamespace(
            id=conversation_id,
            created_by=account.id,
            is_deleted=False,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )

        # 模拟 _resolve_assistant_agent_conversation 方法
        def mock_resolve_conversation(*args, **kwargs):
            return conversation

        monkeypatch.setattr(service, "_resolve_assistant_agent_conversation", mock_resolve_conversation)

        # 模拟分页器 - 返回空列表
        mock_paginator = SimpleNamespace(paginate=lambda query: [])
        monkeypatch.setattr("internal.service.assistant_agent_service.Paginator", lambda **kwargs: mock_paginator)

        # 模拟分页查询 - 返回空列表（因为 query 为空被过滤掉了）
        monkeypatch.setattr(service, "db", SimpleNamespace(
            session=SimpleNamespace(
                query=lambda *args, **kwargs: SimpleNamespace(
                    filter=lambda *args, **kwargs: SimpleNamespace(
                        order_by=lambda *args, **kwargs: SimpleNamespace(
                            all=lambda: []  # 返回空列表
                        )
                    ),
                    options=lambda *args, **kwargs: SimpleNamespace(
                        filter=lambda *args, **kwargs: SimpleNamespace(
                            order_by=lambda *args, **kwargs: SimpleNamespace(
                                all=lambda: []
                            )
                        )
                    )
                )
            )
        ))

        # 调用方法
        messages, paginator = service.get_conversation_messages_with_page(req, account)

        # 验证结果 - 应该返回空列表
        assert len(messages) == 0
