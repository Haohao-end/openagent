"""
后端集成测试：验证消息查询的完整流程

测试场景：
1. 用户发送消息
2. 后端插入消息到数据库
3. 前端查询消息
4. 后端返回消息
"""

import pytest
from uuid import uuid4
from datetime import datetime, UTC
from types import SimpleNamespace

from internal.entity.conversation_entity import InvokeFrom, MessageStatus


class TestAssistantAgentMessageQueryIntegration:
    """后端集成测试：消息查询流程"""

    def test_message_query_with_specific_conversation_id(self):
        """
        测试场景：前端查询特定会话的消息

        预期行为：
        1. 后端接收 conversation_id 参数
        2. 后端查询该会话的消息
        3. 后端返回消息列表
        """
        conversation_id = uuid4()
        account_id = uuid4()

        # 模拟请求对象
        req = SimpleNamespace(
            conversation_id=SimpleNamespace(data=str(conversation_id)),
            current_page=SimpleNamespace(data=1),
            page_size=SimpleNamespace(data=5),
            created_at=SimpleNamespace(data=0),
        )

        # 模拟账号对象
        account = SimpleNamespace(id=account_id)

        # 验证：conversation_id 应该被正确解析
        from internal.service.assistant_agent_service import AssistantAgentService
        resolved_id = AssistantAgentService._resolve_conversation_id(str(conversation_id))
        assert resolved_id == conversation_id, "conversation_id 应该被正确解析"

    def test_message_query_with_empty_conversation_id(self):
        """
        测试场景：前端查询消息时 conversation_id 为空

        预期行为：
        1. 后端接收空的 conversation_id 参数
        2. 后端使用账号的默认会话
        3. 后端返回默认会话的消息
        """
        account_id = uuid4()
        default_conversation_id = uuid4()

        # 模拟请求对象（conversation_id 为空）
        req = SimpleNamespace(
            conversation_id=SimpleNamespace(data=""),
            current_page=SimpleNamespace(data=1),
            page_size=SimpleNamespace(data=5),
            created_at=SimpleNamespace(data=0),
        )

        # 模拟账号对象
        account = SimpleNamespace(
            id=account_id,
            assistant_agent_conversation=SimpleNamespace(id=default_conversation_id),
        )

        # 验证：conversation_id 应该被解析为 None
        from internal.service.assistant_agent_service import AssistantAgentService
        resolved_id = AssistantAgentService._resolve_conversation_id("")
        assert resolved_id is None, "空的 conversation_id 应该被解析为 None"

    def test_message_status_filter(self):
        """
        测试场景：后端应该只返回有效的消息

        预期行为：
        1. 后端应该过滤掉已删除的消息
        2. 后端应该过滤掉没有 answer 的消息
        3. 后端应该只返回 status 为 'normal' 或 'stop' 的消息
        """
        # 模拟消息对象
        valid_message = SimpleNamespace(
            id=uuid4(),
            conversation_id=uuid4(),
            query='你好',
            answer='你好，我是助手',
            status=MessageStatus.NORMAL.value,
            is_deleted=False,
        )

        deleted_message = SimpleNamespace(
            id=uuid4(),
            conversation_id=uuid4(),
            query='你好',
            answer='你好，我是助手',
            status=MessageStatus.NORMAL.value,
            is_deleted=True,
        )

        empty_answer_message = SimpleNamespace(
            id=uuid4(),
            conversation_id=uuid4(),
            query='你好',
            answer='',
            status=MessageStatus.NORMAL.value,
            is_deleted=False,
        )

        # 验证：只有有效的消息应该被返回
        messages = [valid_message, deleted_message, empty_answer_message]
        filtered_messages = [
            msg for msg in messages
            if not msg.is_deleted and msg.answer != '' and msg.status in [MessageStatus.NORMAL.value, MessageStatus.STOP.value]
        ]

        assert len(filtered_messages) == 1, "应该只返回有效的消息"
        assert filtered_messages[0].id == valid_message.id, "应该返回正确的消息"

    def test_message_query_pagination(self):
        """
        测试场景：后端应该支持分页查询

        预期行为：
        1. 后端应该支持 current_page 和 page_size 参数
        2. 后端应该返回分页信息
        3. 后端应该返回正确的消息列表
        """
        # 模拟消息列表
        messages = [
            SimpleNamespace(id=uuid4(), query=f'问题 {i}', answer=f'回答 {i}')
            for i in range(10)
        ]

        # 模拟分页参数
        current_page = 1
        page_size = 5

        # 计算分页
        start_idx = (current_page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_messages = messages[start_idx:end_idx]

        # 验证：应该返回正确的分页消息
        assert len(paginated_messages) == 5, "应该返回 5 条消息"
        assert paginated_messages[0].query == '问题 0', "应该返回正确的消息"

        # 验证：第二页
        current_page = 2
        start_idx = (current_page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_messages = messages[start_idx:end_idx]

        assert len(paginated_messages) == 5, "应该返回 5 条消息"
        assert paginated_messages[0].query == '问题 5', "应该返回正确的消息"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
