import json
import pytest
from datetime import UTC, datetime
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4

from internal.service.intent_recognition_service import IntentRecognitionService
from internal.service.home_service import HomeService
from internal.model import Account, Conversation, Message


class TestIntentRecognitionService:
    """意图识别服务测试"""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis客户端"""
        return Mock()

    @pytest.fixture
    def service(self, mock_redis):
        """创建服务实例"""
        service = IntentRecognitionService(redis_client=mock_redis)
        return service

    def test_default_intent(self, service):
        """测试默认意图"""
        default = service.DEFAULT_INTENT
        assert "intent" in default
        assert "confidence" in default
        assert "suggested_actions" in default
        assert default["is_default"] is True

    def test_build_langchain_messages(self, service):
        """测试构建LangChain消息"""
        messages = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好，有什么帮助吗？"},
        ]
        lc_messages = service._build_langchain_messages(messages)
        assert len(lc_messages) == 2
        assert lc_messages[0].content == "你好"
        assert lc_messages[1].content == "你好，有什么帮助吗？"

    def test_format_messages(self, service):
        """测试格式化消息"""
        from langchain_core.messages import HumanMessage, AIMessage
        messages = [
            HumanMessage(content="你好"),
            AIMessage(content="你好，有什么帮助吗？"),
        ]
        formatted = service._format_messages(messages)
        assert "用户: 你好" in formatted
        assert "助手: 你好，有什么帮助吗？" in formatted

    def test_parse_response_valid_json(self, service):
        """测试解析有效的JSON响应"""
        response = json.dumps({
            "intent": "用户想创建应用",
            "confidence": 0.9,
            "suggested_actions": [
                {"label": "创建应用", "action": "create_app", "icon": "plus"}
            ]
        })
        result = service._parse_response(response)
        assert result["intent"] == "用户想创建应用"
        assert result["confidence"] == 0.9
        assert result["is_default"] is False

    def test_parse_response_json_in_markdown(self, service):
        """测试解析Markdown代码块中的JSON"""
        response = """```json
{
  "intent": "用户想创建应用",
  "confidence": 0.9,
  "suggested_actions": [
    {"label": "创建应用", "action": "create_app", "icon": "plus"}
  ]
}
```"""
        result = service._parse_response(response)
        assert result["intent"] == "用户想创建应用"
        assert result["is_default"] is False

    def test_parse_response_invalid_json(self, service):
        """测试解析无效JSON时返回默认值"""
        response = "这不是JSON"
        result = service._parse_response(response)
        assert result == service.DEFAULT_INTENT

    def test_cache_key_generation(self, service):
        """测试缓存key生成"""
        user_id = "test-user-123"
        key = service._get_cache_key(user_id)
        assert key == f"home:intent:{user_id}"

    def test_get_cached_intent_hit(self, service, mock_redis):
        """测试缓存命中"""
        user_id = "test-user-123"
        cached_data = {
            "intent": "缓存的意图",
            "confidence": 0.8,
            "suggested_actions": []
        }
        mock_redis.get.return_value = json.dumps(cached_data).encode()

        result = service.get_cached_intent(user_id)
        assert result["intent"] == "缓存的意图"
        mock_redis.get.assert_called_once()

    def test_get_cached_intent_miss(self, service, mock_redis):
        """测试缓存未命中"""
        user_id = "test-user-123"
        mock_redis.get.return_value = None

        result = service.get_cached_intent(user_id)
        assert result is None

    def test_cache_intent(self, service, mock_redis):
        """测试缓存意图"""
        user_id = "test-user-123"
        intent_result = {
            "intent": "用户想创建应用",
            "confidence": 0.9,
            "suggested_actions": []
        }

        service.cache_intent(user_id, intent_result)

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == f"home:intent:{user_id}"
        assert call_args[0][1] == 24 * 60 * 60

    def test_clear_cache(self, service, mock_redis):
        """测试清除缓存"""
        user_id = "test-user-123"
        service.clear_cache(user_id)
        mock_redis.delete.assert_called_once_with(f"home:intent:{user_id}")


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

    def test_get_recent_messages_no_conversation(self, service, mock_db):
        """测试没有对话时返回空列表"""
        user = Mock(spec=Account)
        user.id = uuid4()

        # Mock查询返回None
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = None
        mock_db.session.query.return_value = mock_query

        result = service._get_recent_messages(user)
        assert result == []

    def test_get_recent_messages_with_messages(self, service, mock_db):
        """测试获取消息"""
        user = Mock(spec=Account)
        user.id = uuid4()

        # Mock对话
        conversation = Mock(spec=Conversation)
        conversation.id = uuid4()

        # Mock消息
        message1 = Mock(spec=Message)
        message1.query = "你好"
        message1.answer = "你好，有什么帮助吗？"
        message1.created_at = datetime.now(UTC)
        message1.is_deleted = False

        # Mock查询
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = conversation
        mock_db.session.query.return_value = mock_query

        # Mock消息查询
        mock_msg_query = Mock()
        mock_msg_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [message1]
        mock_db.session.query.side_effect = [mock_query, mock_msg_query]

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
