import pytest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from internal.service.intent_recognition_service import IntentRecognitionService
from internal.service.home_service import HomeService
from internal.model import Message


class TestHomeService:
    """首页服务测试"""

    @pytest.fixture
    def mock_db(self):
        """Mock数据库"""
        return Mock()

    @pytest.fixture
    def mock_intent_service(self):
        """Mock意图识别服务"""
        return Mock(spec=IntentRecognitionService)

    @pytest.fixture
    def service(self, mock_db, mock_intent_service):
        """创建服务实例"""
        service = HomeService(
            db=mock_db, intent_recognition_service=mock_intent_service
        )
        return service

    def test_get_recent_messages_no_messages(self, service, mock_db):
        """测试没有消息时返回空列表"""
        user = SimpleNamespace(id=uuid4())

        mock_query = Mock()
        query_all = (
            mock_query.filter.return_value.order_by.return_value.limit.return_value.all
        )
        query_all.return_value = []
        mock_db.session.query.return_value = mock_query

        result = service._get_recent_messages(user)
        assert result == []

    def test_get_recent_messages_with_messages(self, service, mock_db):
        """测试获取消息"""
        user = SimpleNamespace(id=uuid4())
        now = datetime.now(UTC)

        # Mock消息
        message1 = Mock(spec=Message)
        message1.id = uuid4()
        message1.query = "你好"
        message1.answer = "你好，有什么帮助吗？"
        message1.created_at = now
        message1.updated_at = now
        message1.is_deleted = False

        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            message1
        ]
        mock_db.session.query.return_value = mock_query

        result = service._get_recent_messages(user)
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "你好"
        assert result[0]["id"] == str(message1.id)
        assert result[0]["updated_at"] == now.isoformat()

    def test_build_message_signature_is_stable_and_content_sensitive(self, service):
        """测试消息签名稳定且会随内容变化"""
        messages = [
            {
                "id": "message-1",
                "role": "user",
                "content": "你好",
                "created_at": "2026-03-17T10:00:00Z",
                "updated_at": "2026-03-17T10:00:01Z",
            },
            {
                "id": "message-1",
                "role": "user",
                "content": "我想创建应用",
                "created_at": "2026-03-17T10:00:00Z",
                "updated_at": "2026-03-17T10:00:01Z",
            },
        ]

        signature = service._build_message_signature(messages)

        assert signature == service._build_message_signature(list(messages))
        changed_messages = [dict(item) for item in messages]
        changed_messages[1]["content"] = "更新后的回答"
        assert signature != service._build_message_signature(changed_messages)

    def test_build_message_signature_should_ignore_updated_at_changes(self, service):
        """测试消息签名不应因为同一条用户消息的 updated_at 变化而变化"""
        messages = [
            {
                "id": "message-1",
                "role": "user",
                "content": "我想创建应用",
                "created_at": "2026-03-17T10:00:00Z",
                "updated_at": "2026-03-17T10:00:01Z",
            }
        ]

        signature = service._build_message_signature(messages)
        mutated_messages = [dict(item) for item in messages]
        mutated_messages[0]["updated_at"] = "2026-03-17T10:05:00Z"

        assert signature == service._build_message_signature(mutated_messages)

    def test_get_user_intent_insufficient_messages(self, service, mock_intent_service):
        """测试消息不足时返回默认意图"""
        user = SimpleNamespace(id=uuid4())

        # Mock获取消息返回空列表
        service._get_recent_messages = Mock(return_value=[])

        result = service.get_user_intent(user)
        assert result == mock_intent_service.DEFAULT_INTENT

    def test_get_user_intent_single_user_message_triggers_recognition(
        self,
        service,
        mock_intent_service,
    ):
        """测试只有一条用户输入时也会调用意图识别"""
        user = SimpleNamespace(id=uuid4())
        messages = [
            {
                "role": "user",
                "content": "我想创建应用",
                "created_at": "2026-03-17T10:00:00Z",
            }
        ]
        service._get_recent_messages = Mock(return_value=messages)
        mock_intent_service.get_cached_intent.return_value = None
        mock_intent_service.recognize.return_value = {
            "intent": "用户想创建应用",
            "confidence": 0.9,
            "suggested_actions": [],
            "is_default": False,
        }

        result = service.get_user_intent(user)

        assert result["intent"] == "用户想创建应用"
        mock_intent_service.recognize.assert_called_once_with(messages)

    def test_get_user_intent_cache_hit(self, service, mock_intent_service):
        """测试缓存命中"""
        user = SimpleNamespace(id=uuid4())

        # Mock消息
        messages = [
            {"role": "user", "content": "你好", "created_at": "2026-03-17T10:00:00Z"},
            {
                "role": "user",
                "content": "我想创建应用",
                "created_at": "2026-03-17T10:01:00Z",
            },
        ]
        service._get_recent_messages = Mock(return_value=messages)

        # Mock缓存命中
        cached_intent = {
            "intent": "缓存的意图",
            "confidence": 0.8,
            "suggested_actions": [],
            "last_message_timestamp": "2026-03-17T10:01:00Z",
        }
        mock_intent_service.get_cached_intent.return_value = cached_intent

        result = service.get_user_intent(user)
        assert result["intent"] == "缓存的意图"
        mock_intent_service.recognize.assert_not_called()
        mock_intent_service.cache_intent.assert_called_once()

    def test_get_user_intent_cache_hit_with_message_signature(
        self,
        service,
        mock_intent_service,
    ):
        """测试新版本缓存使用消息签名命中"""
        user = SimpleNamespace(id=uuid4())
        messages = [
            {
                "id": "message-1",
                "role": "user",
                "content": "你好",
                "created_at": "2026-03-17T10:00:00Z",
                "updated_at": "2026-03-17T10:00:01Z",
            },
            {
                "id": "message-2",
                "role": "user",
                "content": "我想创建应用",
                "created_at": "2026-03-17T10:01:00Z",
                "updated_at": "2026-03-17T10:01:01Z",
            },
        ]
        service._get_recent_messages = Mock(return_value=messages)
        message_signature = service._build_message_signature(messages)
        mock_intent_service.get_cached_intent.return_value = {
            "intent": "缓存的意图",
            "confidence": 0.8,
            "suggested_actions": [],
            "last_message_timestamp": "2026-03-17T10:00:00Z",
            "message_signature": message_signature,
        }

        result = service.get_user_intent(user)

        assert result["intent"] == "缓存的意图"
        mock_intent_service.recognize.assert_not_called()
        mock_intent_service.cache_intent.assert_not_called()

    def test_get_user_intent_invalidates_when_signature_changes(
        self,
        service,
        mock_intent_service,
    ):
        """测试同一时间戳下消息内容变化时重新识别"""
        user = SimpleNamespace(id=uuid4())
        messages = [
            {
                "id": "message-1",
                "role": "user",
                "content": "我想创建应用",
                "created_at": "2026-03-17T10:00:00Z",
                "updated_at": "2026-03-17T10:00:01Z",
            },
            {
                "id": "message-2",
                "role": "user",
                "content": "我想创建一个天气应用",
                "created_at": "2026-03-17T10:01:00Z",
                "updated_at": "2026-03-17T10:01:01Z",
            },
        ]
        service._get_recent_messages = Mock(return_value=messages)
        mock_intent_service.get_cached_intent.return_value = {
            "intent": "旧缓存意图",
            "confidence": 0.8,
            "suggested_actions": [],
            "last_message_timestamp": "2026-03-17T10:01:00Z",
            "message_signature": "old-signature",
        }
        mock_intent_service.recognize.return_value = {
            "intent": "新识别意图",
            "confidence": 0.9,
            "suggested_actions": [],
            "is_default": False,
        }

        result = service.get_user_intent(user)

        assert result["intent"] == "新识别意图"
        assert result["message_signature"] == service._build_message_signature(messages)
        mock_intent_service.clear_cache.assert_called_once_with(str(user.id))
        mock_intent_service.recognize.assert_called_once_with(messages)
        mock_intent_service.cache_intent.assert_called_once()

    def test_get_user_intent_cache_miss(self, service, mock_intent_service):
        """测试缓存未命中，调用模型"""
        user = SimpleNamespace(id=uuid4())

        # Mock消息
        messages = [
            {"role": "user", "content": "你好", "created_at": "2026-03-17T10:00:00Z"},
            {
                "role": "user",
                "content": "我想创建应用",
                "created_at": "2026-03-17T10:01:00Z",
            },
        ]
        service._get_recent_messages = Mock(return_value=messages)

        # Mock缓存未命中
        mock_intent_service.get_cached_intent.return_value = None

        # Mock模型识别结果
        recognized_intent = {
            "intent": "用户想创建应用",
            "confidence": 0.9,
            "suggested_actions": [
                {"label": "创建应用", "action": "create_app", "icon": "plus"}
            ],
            "is_default": False,
        }
        mock_intent_service.recognize.return_value = recognized_intent

        result = service.get_user_intent(user)
        assert result["intent"] == "用户想创建应用"
        mock_intent_service.recognize.assert_called_once_with(messages)
        mock_intent_service.cache_intent.assert_called_once()
