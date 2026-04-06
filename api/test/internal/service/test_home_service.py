import pytest
from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

from internal.service.intent_recognition_service import IntentRecognitionService
from internal.service.home_service import HomeService
from internal.model import Account, Message


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
        service = HomeService(db=mock_db, intent_recognition_service=mock_intent_service)
        return service

    def test_get_recent_messages_no_messages(self, service, mock_db):
        """测试没有消息时返回空列表"""
        user = Mock(spec=Account)
        user.id = uuid4()

        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_db.session.query.return_value = mock_query

        result = service._get_recent_messages(user)
        assert result == []

    def test_get_recent_messages_with_messages(self, service, mock_db):
        """测试获取消息"""
        user = Mock(spec=Account)
        user.id = uuid4()

        # Mock消息
        message1 = Mock(spec=Message)
        message1.query = "你好"
        message1.answer = "你好，有什么帮助吗？"
        message1.created_at = datetime.now(UTC)
        message1.is_deleted = False

        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [message1]
        mock_db.session.query.return_value = mock_query

        result = service._get_recent_messages(user)
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "你好"
        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == "你好，有什么帮助吗？"

    def test_get_user_intent_insufficient_messages(self, service, mock_intent_service):
        """测试消息不足时返回默认意图"""
        user = Mock(spec=Account)
        user.id = uuid4()

        # Mock获取消息返回空列表
        service._get_recent_messages = Mock(return_value=[])

        result = service.get_user_intent(user)
        assert result == mock_intent_service.DEFAULT_INTENT

    def test_get_user_intent_cache_hit(self, service, mock_intent_service):
        """测试缓存命中"""
        user = Mock(spec=Account)
        user.id = uuid4()

        # Mock消息
        messages = [
            {"role": "user", "content": "你好", "created_at": "2026-03-17T10:00:00Z"},
            {"role": "assistant", "content": "你好", "created_at": "2026-03-17T10:00:00Z"},
        ]
        service._get_recent_messages = Mock(return_value=messages)

        # Mock缓存命中
        cached_intent = {
            "intent": "缓存的意图",
            "confidence": 0.8,
            "suggested_actions": [],
            "last_message_timestamp": "2026-03-17T10:00:00Z"
        }
        mock_intent_service.get_cached_intent.return_value = cached_intent

        result = service.get_user_intent(user)
        assert result["intent"] == "缓存的意图"
        mock_intent_service.recognize.assert_not_called()

    def test_get_user_intent_cache_miss(self, service, mock_intent_service):
        """测试缓存未命中，调用模型"""
        user = Mock(spec=Account)
        user.id = uuid4()

        # Mock消息
        messages = [
            {"role": "user", "content": "你好", "created_at": "2026-03-17T10:00:00Z"},
            {"role": "assistant", "content": "你好", "created_at": "2026-03-17T10:00:00Z"},
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
            "is_default": False
        }
        mock_intent_service.recognize.return_value = recognized_intent

        result = service.get_user_intent(user)
        assert result["intent"] == "用户想创建应用"
        mock_intent_service.recognize.assert_called_once()
        mock_intent_service.cache_intent.assert_called_once()
