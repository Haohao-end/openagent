"""
集成测试：验证首页意图识别功能的完整流程
"""
import json
import pytest
from datetime import UTC, datetime
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4

from internal.handler.home_handler import HomeHandler
from internal.service.home_service import HomeService
from internal.service.intent_recognition_service import IntentRecognitionService
from internal.model import Account, Conversation, Message


class TestHomeIntentIntegration:
    """首页意图识别集成测试"""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis"""
        return Mock()

    @pytest.fixture
    def mock_db(self):
        """Mock数据库"""
        return Mock()

    @pytest.fixture
    def intent_service(self, mock_redis):
        """创建意图识别服务"""
        return IntentRecognitionService(redis_client=mock_redis)

    @pytest.fixture
    def home_service(self, mock_db, intent_service):
        """创建首页服务"""
        return HomeService(db=mock_db, intent_recognition_service=intent_service)

    @pytest.fixture
    def home_handler(self, home_service):
        """创建首页处理器"""
        return HomeHandler(home_service=home_service)

    def test_complete_flow_with_cache_miss(self, home_service, intent_service, mock_db, mock_redis):
        """测试完整流程：缓存未命中，调用模型"""
        # 准备用户
        user = Mock(spec=Account)
        user.id = uuid4()

        # 准备对话和消息
        conversation = Mock(spec=Conversation)
        conversation.id = uuid4()

        message1 = Mock(spec=Message)
        message1.query = "我想创建一个AI应用"
        message1.answer = "好的，我可以帮你创建一个AI应用。"
        message1.created_at = datetime.now(UTC)
        message1.is_deleted = False

        message2 = Mock(spec=Message)
        message2.query = "应该如何开始？"
        message2.answer = "首先，你需要定义应用的功能和目标。"
        message2.created_at = datetime.now(UTC)
        message2.is_deleted = False

        # Mock数据库查询
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = conversation
        mock_db.session.query.return_value = mock_query

        # Mock消息查询
        mock_msg_query = Mock()
        mock_msg_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [message1, message2]
        mock_db.session.query.side_effect = [mock_query, mock_msg_query]

        # Mock缓存未命中
        mock_redis.get.return_value = None

        # Mock模型响应
        with patch.object(intent_service, 'recognize') as mock_recognize:
            mock_recognize.return_value = {
                "intent": "用户想创建一个AI应用来处理特定的业务需求",
                "confidence": 0.95,
                "suggested_actions": [
                    {"label": "创建应用", "action": "create_app", "icon": "plus"},
                    {"label": "查看示例", "action": "view_examples", "icon": "book"}
                ],
                "is_default": False
            }

            # 调用服务
            result = home_service.get_user_intent(user)

            # 验证结果
            assert result["intent"] == "用户想创建一个AI应用来处理特定的业务需求"
            assert result["confidence"] == 0.95
            assert len(result["suggested_actions"]) == 2
            assert result["is_default"] is False

            # 验证模型被调用
            mock_recognize.assert_called_once()

            # 验证缓存被写入
            mock_redis.setex.assert_called_once()

    def test_complete_flow_with_cache_hit(self, home_service, intent_service, mock_db, mock_redis):
        """测试完整流程：缓存命中"""
        # 准备用户
        user = Mock(spec=Account)
        user.id = uuid4()

        # 准备对话和消息
        conversation = Mock(spec=Conversation)
        conversation.id = uuid4()

        message1 = Mock(spec=Message)
        message1.query = "我想创建一个AI应用"
        message1.answer = "好的，我可以帮你创建一个AI应用。"
        message1.created_at = datetime.now(UTC)
        message1.is_deleted = False

        # Mock数据库查询
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = conversation
        mock_db.session.query.return_value = mock_query

        # Mock消息查询
        mock_msg_query = Mock()
        mock_msg_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [message1]
        mock_db.session.query.side_effect = [mock_query, mock_msg_query]

        # Mock缓存命中
        cached_intent = {
            "intent": "用户想创建一个AI应用",
            "confidence": 0.9,
            "suggested_actions": [
                {"label": "创建应用", "action": "create_app", "icon": "plus"}
            ],
            "is_default": False,
            "last_message_timestamp": message1.created_at.isoformat()
        }
        mock_redis.get.return_value = json.dumps(cached_intent).encode()

        # Mock模型响应（不应该被调用）
        with patch.object(intent_service, 'recognize') as mock_recognize:
            # 调用服务
            result = home_service.get_user_intent(user)

            # 验证结果
            assert result["intent"] == "用户想创建一个AI应用"
            assert result["confidence"] == 0.9

            # 验证模型未被调用
            mock_recognize.assert_not_called()

    def test_complete_flow_insufficient_messages(self, home_service, mock_db):
        """测试消息不足时返回默认意图"""
        # 准备用户
        user = Mock(spec=Account)
        user.id = uuid4()

        # Mock数据库查询返回None（没有对话）
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = None
        mock_db.session.query.return_value = mock_query

        # 调用服务
        result = home_service.get_user_intent(user)

        # 验证返回默认意图
        assert result["is_default"] is True
        assert "Hi，haohao" in result["intent"]

    def test_handler_integration(self, home_handler, home_service, mock_db, mock_redis):
        """测试处理器集成"""
        # 准备用户
        user = Mock(spec=Account)
        user.id = uuid4()

        # Mock数据库查询
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.first.return_value = None
        mock_db.session.query.return_value = mock_query

        # 由于处理器需要Flask请求上下文，这里只验证处理器的存在和基本结构
        assert home_handler is not None
        assert hasattr(home_handler, 'get_intent')
        assert hasattr(home_handler, 'home_service')

    def test_parse_response_with_various_formats(self, intent_service):
        """测试解析各种格式的响应"""
        # 测试纯JSON
        json_response = json.dumps({
            "intent": "测试意图",
            "confidence": 0.85,
            "suggested_actions": []
        })
        result = intent_service._parse_response(json_response)
        assert result["intent"] == "测试意图"

        # 测试Markdown JSON
        markdown_response = """
这是一个响应。

```json
{
  "intent": "Markdown中的意图",
  "confidence": 0.75,
  "suggested_actions": []
}
```

更多文本。
"""
        result = intent_service._parse_response(markdown_response)
        assert result["intent"] == "Markdown中的意图"

        # 测试无效JSON
        invalid_response = "这不是JSON"
        result = intent_service._parse_response(invalid_response)
        assert result["is_default"] is True

    def test_message_formatting(self, intent_service):
        """测试消息格式化"""
        from langchain_core.messages import HumanMessage, AIMessage

        messages = [
            HumanMessage(content="第一个用户消息"),
            AIMessage(content="第一个AI回复"),
            HumanMessage(content="第二个用户消息"),
            AIMessage(content="第二个AI回复"),
        ]

        formatted = intent_service._format_messages(messages)

        assert "用户: 第一个用户消息" in formatted
        assert "助手: 第一个AI回复" in formatted
        assert "用户: 第二个用户消息" in formatted
        assert "助手: 第二个AI回复" in formatted

    def test_cache_operations(self, intent_service, mock_redis):
        """测试缓存操作"""
        user_id = "test-user-123"
        intent_data = {
            "intent": "测试意图",
            "confidence": 0.9,
            "suggested_actions": []
        }

        # 测试缓存写入
        intent_service.cache_intent(user_id, intent_data)
        mock_redis.setex.assert_called_once()

        # 验证缓存key和TTL
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == f"home:intent:{user_id}"
        assert call_args[0][1] == 24 * 60 * 60

        # 测试缓存清除
        mock_redis.reset_mock()
        intent_service.clear_cache(user_id)
        mock_redis.delete.assert_called_once_with(f"home:intent:{user_id}")
