#!/usr/bin/env python
"""
手动测试脚本：演示首页意图识别功能
"""
import json
from datetime import UTC, datetime
from unittest.mock import Mock

from internal.service.intent_recognition_service import IntentRecognitionService
from internal.service.home_service import HomeService
from internal.model import Account, Conversation, Message


def test_intent_recognition_service():
    """测试意图识别服务"""
    print("=" * 60)
    print("测试1：意图识别服务")
    print("=" * 60)

    # 创建Mock Redis
    mock_redis = Mock()
    service = IntentRecognitionService(redis_client=mock_redis)

    # 测试消息格式化
    messages = [
        {"role": "user", "content": "我想创建一个AI应用来处理客服问题"},
        {"role": "assistant", "content": "好的，我可以帮你创建一个AI应用。首先，你需要定义应用的功能。"},
        {"role": "user", "content": "应该如何开始？"},
        {"role": "assistant", "content": "你可以点击'创建应用'按钮开始。"},
    ]

    print("\n输入消息：")
    for msg in messages:
        print(f"  {msg['role']}: {msg['content']}")

    # 构建LangChain消息
    lc_messages = service._build_langchain_messages(messages)
    print(f"\n构建的LangChain消息数量：{len(lc_messages)}")

    # 格式化消息
    formatted = service._format_messages(lc_messages)
    print(f"\n格式化后的消息：\n{formatted}")

    # 测试响应解析
    print("\n" + "=" * 60)
    print("测试2：响应解析")
    print("=" * 60)

    # 测试有效的JSON响应
    valid_response = json.dumps({
        "intent": "用户想创建一个AI应用来处理客服问题",
        "confidence": 0.92,
        "suggested_actions": [
            {"label": "创建应用", "action": "create_app", "icon": "plus"},
            {"label": "查看示例", "action": "view_examples", "icon": "book"}
        ]
    })

    print("\n原始响应：")
    print(valid_response)

    result = service._parse_response(valid_response)
    print("\n解析结果：")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 测试Markdown格式的JSON
    markdown_response = """
根据用户的对话历史，我分析出以下意图：

```json
{
  "intent": "用户想创建一个AI应用来处理客服问题",
  "confidence": 0.92,
  "suggested_actions": [
    {"label": "创建应用", "action": "create_app", "icon": "plus"},
    {"label": "查看示例", "action": "view_examples", "icon": "book"}
  ]
}
```

这是基于用户最近的对话历史分析得出的。
"""

    print("\n" + "-" * 60)
    print("Markdown格式的响应：")
    print(markdown_response)

    result = service._parse_response(markdown_response)
    print("\n解析结果：")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 测试缓存操作
    print("\n" + "=" * 60)
    print("测试3：缓存操作")
    print("=" * 60)

    user_id = "test-user-123"
    intent_data = {
        "intent": "用户想创建一个AI应用",
        "confidence": 0.9,
        "suggested_actions": [
            {"label": "创建应用", "action": "create_app", "icon": "plus"}
        ]
    }

    print(f"\n缓存用户 {user_id} 的意图数据...")
    service.cache_intent(user_id, intent_data)
    print("✓ 缓存写入成功")

    # 验证缓存key
    cache_key = service._get_cache_key(user_id)
    print(f"缓存Key: {cache_key}")

    # 测试默认意图
    print("\n" + "=" * 60)
    print("测试4：默认意图")
    print("=" * 60)

    default_intent = service.DEFAULT_INTENT
    print("\n默认意图内容：")
    print(json.dumps(default_intent, ensure_ascii=False, indent=2))

    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    test_intent_recognition_service()
