import json
from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from internal.service.intent_recognition_service import IntentRecognitionService


class TestIntentRecognitionService:
    @pytest.fixture
    def mock_redis(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_redis):
        return IntentRecognitionService(redis_client=mock_redis)

    def test_should_expose_default_intent_shape(self, service):
        default_intent = service.DEFAULT_INTENT

        assert default_intent["is_default"] is True
        assert "intent" in default_intent
        assert "confidence" in default_intent
        assert "suggested_actions" in default_intent

    def test_should_build_langchain_messages_from_supported_roles(self, service):
        messages = [
            {"role": "user", "content": "你好"},
            {"role": "system", "content": "忽略我"},
            {"role": "assistant", "content": "你好，有什么可以帮你？"},
        ]

        lc_messages = service._build_langchain_messages(messages)

        assert len(lc_messages) == 2
        assert isinstance(lc_messages[0], HumanMessage)
        assert isinstance(lc_messages[1], AIMessage)
        assert lc_messages[0].content == "你好"
        assert lc_messages[1].content == "你好，有什么可以帮你？"

    def test_should_format_messages_for_prompt(self, service):
        formatted = service._format_messages(
            [
                HumanMessage(content="第一条用户消息"),
                AIMessage(content="第一条助手回复"),
            ]
        )

        assert "用户: 第一条用户消息" in formatted
        assert "助手: 第一条助手回复" in formatted

    def test_should_parse_markdown_wrapped_json_response(self, service):
        response = """分析结果如下：

```json
{
  "intent": "用户想创建一个天气智能体",
  "confidence": 0.92,
  "suggested_actions": [
    {"label": "创建应用", "action": "create_app", "icon": "plus"}
  ]
}
```"""

        result = service._parse_response(response)

        assert result["intent"] == "用户想创建一个天气智能体"
        assert result["confidence"] == 0.92
        assert result["is_default"] is False

    def test_should_fallback_to_default_intent_when_required_fields_missing(self, service):
        result = service._parse_response(json.dumps({"intent": "缺少字段"}))

        assert result == service.DEFAULT_INTENT

    def test_should_return_none_when_cached_payload_is_invalid_json(self, service, mock_redis):
        mock_redis.get.return_value = b"{invalid-json"

        result = service.get_cached_intent("user-1")

        assert result is None

    def test_should_cache_intent_with_ttl_and_timestamps(self, service, mock_redis):
        intent_result = {
            "intent": "用户想创建应用",
            "confidence": 0.9,
            "suggested_actions": [],
        }

        service.cache_intent("user-1", intent_result)

        mock_redis.setex.assert_called_once()
        cache_key, ttl, payload = mock_redis.setex.call_args[0]
        cached_result = json.loads(payload)

        assert cache_key == "home:intent:user-1"
        assert ttl == service.INTENT_CACHE_TTL
        assert cached_result["intent"] == "用户想创建应用"
        assert "generated_at" in cached_result
        assert "expires_at" in cached_result

    def test_should_clear_cache_for_user(self, service, mock_redis):
        service.clear_cache("user-1")

        mock_redis.delete.assert_called_once_with("home:intent:user-1")
