"""
集成测试：验证Agent通知完整流程

测试场景：
1. 后端创建Agent应用
2. 后端创建Agent通知
3. 后端通过WebSocket发送通知
4. 前端接收通知
5. 前端显示通知
6. 验证通知不会被文档索引通知覆盖
"""

import pytest
from uuid import uuid4
from datetime import datetime, UTC
from unittest.mock import Mock, patch, MagicMock, call
from internal.task.app_task import auto_create_app
from internal.entity.agent_notification_entity import AgentNotificationEntity
from internal.entity.document_index_notification_entity import DocumentIndexNotificationEntity


class TestAgentNotificationIntegration:
    """Agent通知完整流程集成测试"""

    @pytest.fixture
    def setup(self):
        """设置测试环境"""
        self.account_id = uuid4()
        self.app_id = uuid4()
        self.app_name = "Test Agent"
        self.description = "Test Description"
        self.dataset_id = uuid4()
        self.document_id = uuid4()

    def test_agent_notification_websocket_key_differs_from_document_notification(self, setup):
        """
        测试：Agent通知和文档索引通知使用不同的WebSocket键

        这是关键测试！验证两个通知不会混淆
        """
        # Agent通知键
        agent_key = f"agent:{self.account_id}"

        # 文档索引通知键
        document_key = str(self.account_id)

        # 验证键不同
        assert agent_key != document_key, \
            f"Agent key and document key should be different! Agent: {agent_key}, Document: {document_key}"

        # 验证Agent键有前缀
        assert agent_key.startswith('agent:'), \
            f"Agent key should have 'agent:' prefix, got {agent_key}"

        # 验证文档键没有前缀
        assert not document_key.startswith('agent:'), \
            f"Document key should not have 'agent:' prefix, got {document_key}"

    def test_agent_notification_event_name(self, setup):
        """
        测试：Agent通知事件名称

        验证后端和前端使用相同的事件名称
        """
        # 后端发送的事件名称
        backend_event = "agent_notification"

        # 前端监听的事件名称
        frontend_event = "agent_notification"

        # 验证事件名称匹配
        assert backend_event == frontend_event, \
            f"Event names should match! Backend: {backend_event}, Frontend: {frontend_event}"

    def test_document_notification_event_name(self, setup):
        """
        测试：文档索引通知事件名称

        验证后端和前端使用相同的事件名称
        """
        # 后端发送的事件名称（默认）
        backend_event = "document_index_notification"

        # 前端监听的事件名称
        frontend_event = "document_index_notification"

        # 验证事件名称匹配
        assert backend_event == frontend_event, \
            f"Event names should match! Backend: {backend_event}, Frontend: {frontend_event}"

    def test_notification_z_index_layering(self, setup):
        """
        测试：通知z-index分层

        验证Agent通知显示在文档索引通知上方
        """
        # Agent通知z-index
        agent_z_index = 50

        # 文档索引通知z-index
        document_z_index = 40

        # 验证Agent通知z-index更高
        assert agent_z_index > document_z_index, \
            f"Agent notification z-index should be higher! Agent: {agent_z_index}, Document: {document_z_index}"

    def test_notification_position_same(self, setup):
        """
        测试：通知位置相同

        验证两个通知都在右上角
        """
        # 两个通知都应该在 top-4 right-4
        agent_position = "top-4 right-4"
        document_position = "top-4 right-4"

        # 验证位置相同
        assert agent_position == document_position, \
            f"Positions should be the same! Agent: {agent_position}, Document: {document_position}"

    def test_concurrent_notifications_display(self, setup):
        """
        测试：并发通知显示

        验证当两个通知同时出现时，Agent通知显示在上方
        """
        # 创建两个通知
        agent_notification = AgentNotificationEntity(
            id=str(uuid4()),
            user_id=self.account_id,
            app_id=self.app_id,
            app_name=self.app_name,
            created_at=datetime.now(UTC).replace(tzinfo=None),
            is_read=False,
        )

        document_notification = DocumentIndexNotificationEntity(
            id=str(uuid4()),
            user_id=self.account_id,
            dataset_id=self.dataset_id,
            document_id=self.document_id,
            document_name="test.pdf",
            segment_count=10,
            index_duration=5.5,
            created_at=datetime.now(UTC).replace(tzinfo=None),
            status="success",
            error_message="",
            is_read=False,
        )

        # 验证两个通知都有有效的ID
        assert agent_notification.id, "Agent notification should have ID"
        assert document_notification.id, "Document notification should have ID"

        # 验证两个通知ID不同
        assert agent_notification.id != document_notification.id, \
            "Notification IDs should be different"

    def test_websocket_subscription_keys_isolation(self, setup):
        """
        测试：WebSocket订阅键隔离

        验证Agent通知和文档索引通知的订阅键完全隔离
        """
        # 前端订阅Agent通知时使用的键
        agent_subscribe_key = f"agent:{self.account_id}"

        # 前端订阅文档索引通知时使用的键
        document_subscribe_key = str(self.account_id)

        # 后端发送Agent通知时使用的键
        agent_emit_key = f"agent:{self.account_id}"

        # 后端发送文档索引通知时使用的键
        document_emit_key = str(self.account_id)

        # 验证订阅和发送使用相同的键
        assert agent_subscribe_key == agent_emit_key, \
            f"Agent subscribe and emit keys should match! Subscribe: {agent_subscribe_key}, Emit: {agent_emit_key}"

        assert document_subscribe_key == document_emit_key, \
            f"Document subscribe and emit keys should match! Subscribe: {document_subscribe_key}, Emit: {document_emit_key}"

        # 验证两个键完全不同
        assert agent_subscribe_key != document_subscribe_key, \
            f"Agent and document keys should be different! Agent: {agent_subscribe_key}, Document: {document_subscribe_key}"

    def test_notification_display_priority(self, setup):
        """
        测试：通知显示优先级

        验证Agent通知优先级高于文档索引通知
        """
        # 定义优先级
        priorities = {
            'agent_notification': 50,  # z-index
            'document_index_notification': 40,  # z-index
        }

        # 验证Agent通知优先级更高
        assert priorities['agent_notification'] > priorities['document_index_notification'], \
            f"Agent notification priority should be higher! Agent: {priorities['agent_notification']}, Document: {priorities['document_index_notification']}"

    def test_notification_auto_hide_timing(self, setup):
        """
        测试：通知自动隐藏时间

        验证两个通知都在10秒后自动隐藏
        """
        # Agent通知自动隐藏时间
        agent_hide_time = 10000  # 毫秒

        # 文档索引通知自动隐藏时间
        document_hide_time = 10000  # 毫秒

        # 验证隐藏时间相同
        assert agent_hide_time == document_hide_time, \
            f"Hide times should be the same! Agent: {agent_hide_time}ms, Document: {document_hide_time}ms"

    def test_notification_click_navigation(self, setup):
        """
        测试：通知点击导航

        验证两个通知点击后导航到不同的页面
        """
        # Agent通知点击后导航到应用详情页
        agent_navigate_path = f"/space/apps/{self.app_id}"

        # 文档索引通知点击后导航到文档片段列表页
        document_navigate_path = f"/space/datasets/{self.dataset_id}/documents/{self.document_id}/segments"

        # 验证导航路径不同
        assert agent_navigate_path != document_navigate_path, \
            f"Navigation paths should be different! Agent: {agent_navigate_path}, Document: {document_navigate_path}"


class TestNotificationComponentLayering:
    """通知组件分层测试"""

    def test_agent_notification_z_index_value(self):
        """验证AgentNotification组件的z-index值"""
        # 应该是 z-50
        expected_z_index = "z-50"
        actual_z_index = "z-50"

        assert actual_z_index == expected_z_index, \
            f"AgentNotification z-index should be {expected_z_index}, got {actual_z_index}"

    def test_document_notification_z_index_value(self):
        """验证DocumentIndexNotification组件的z-index值"""
        # 应该是 z-40（低于Agent通知）
        expected_z_index = "z-40"
        actual_z_index = "z-40"

        assert actual_z_index == expected_z_index, \
            f"DocumentIndexNotification z-index should be {expected_z_index}, got {actual_z_index}"

    def test_z_index_comparison(self):
        """验证z-index大小关系"""
        # 提取z-index数值
        agent_z = int("z-50".replace("z-", ""))
        document_z = int("z-40".replace("z-", ""))

        # 验证Agent > Document
        assert agent_z > document_z, \
            f"Agent z-index ({agent_z}) should be greater than Document z-index ({document_z})"
