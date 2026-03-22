"""
集成测试：验证消息显示的完整流程
"""
import pytest
from uuid import uuid4
from datetime import datetime, UTC
from internal.model import Conversation, Message, Account
from internal.entity.conversation_entity import InvokeFrom, MessageStatus


class TestMessageDisplay:
    """集成测试：消息显示流程"""

    def test_messages_are_displayed_when_visiting_with_conversation_id(self, client, db, monkeypatch):
        """
        测试场景：用户访问 /home?conversation_id=xxx 时，消息应该被显示

        预期行为：
        1. 创建一个会话
        2. 创建一条消息
        3. 查询消息
        4. 验证消息被返回
        """
        # 1. 创建账号
        account = Account(
            id=uuid4(),
            email="test@example.com",
            name="test_user",
            password="hash",
        )
        db.session.add(account)
        db.session.flush()

        # Mock current_user
        monkeypatch.setattr("internal.handler.assistant_agent_handler.current_user", account)

        # 2. 创建会话
        conversation = Conversation(
            id=uuid4(),
            app_id=uuid4(),
            name="Test Conversation",
            created_by=account.id,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        db.session.add(conversation)
        db.session.flush()

        # 3. 创建消息
        message = Message(
            id=uuid4(),
            app_id=conversation.app_id,
            conversation_id=conversation.id,
            query="你好",
            answer="你好，我是助手",
            status=MessageStatus.NORMAL.value,
            created_by=account.id,
            invoke_from=InvokeFrom.ASSISTANT_AGENT.value,
        )
        db.session.add(message)
        db.session.commit()

        # 4. 查询消息
        response = client.get(
            f"/assistant-agent/messages?conversation_id={conversation.id}&limit=20&created_at=0"
        )

        # 5. 验证响应
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.get_json()
        assert data["code"] == "success", f"Expected success, got {data['code']}: {data.get('message')}"
        assert len(data["data"]["list"]) == 1, f"Expected 1 message, got {len(data['data']['list'])}"
        assert data["data"]["list"][0]["query"] == "你好"
        assert data["data"]["list"][0]["answer"] == "你好，我是助手"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
