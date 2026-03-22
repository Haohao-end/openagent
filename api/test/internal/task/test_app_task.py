import pytest
from uuid import uuid4
from datetime import datetime, UTC
from unittest.mock import Mock, patch, MagicMock
from internal.task.app_task import auto_create_app
from internal.entity.agent_notification_entity import AgentNotificationEntity


class TestAutoCreateAppTask:
    """测试auto_create_app任务"""

    @pytest.fixture
    def setup(self):
        """设置测试环境"""
        self.account_id = uuid4()
        self.app_id = uuid4()
        self.app_name = "Test Agent"
        self.description = "Test Description"

    def test_auto_create_app_creates_notification(self, setup):
        """测试auto_create_app是否创建通知"""
        with patch('internal.task.app_task.injector') as mock_injector, \
             patch('internal.task.app_task.ws_manager') as mock_ws_manager:

            # 模拟服务
            mock_app_service = Mock()
            mock_notification_service = Mock()

            # 模拟创建的应用
            mock_app = Mock()
            mock_app.id = self.app_id
            mock_app.name = self.app_name
            mock_app_service.auto_create_app.return_value = mock_app

            # 模拟创建的通知
            mock_notification = AgentNotificationEntity(
                id=str(uuid4()),
                user_id=self.account_id,
                app_id=self.app_id,
                app_name=self.app_name,
                created_at=datetime.now(UTC).replace(tzinfo=None),
                is_read=False,
            )
            mock_notification_service.create_agent_notification.return_value = mock_notification

            # 配置injector
            def get_service(service_class):
                if service_class.__name__ == 'AppService':
                    return mock_app_service
                elif service_class.__name__ == 'NotificationService':
                    return mock_notification_service
                return Mock()

            mock_injector.get.side_effect = get_service

            # 执行任务
            auto_create_app(self.app_name, self.description, self.account_id)

            # 验证应用创建
            mock_app_service.auto_create_app.assert_called_once_with(
                self.app_name, self.description, self.account_id
            )

            # 验证通知创建
            mock_notification_service.create_agent_notification.assert_called_once_with(
                user_id=self.account_id,
                app_id=self.app_id,
                app_name=self.app_name,
            )

    def test_auto_create_app_emits_websocket_notification(self, setup):
        """测试auto_create_app是否通过WebSocket发送通知"""
        with patch('internal.task.app_task.injector') as mock_injector, \
             patch('internal.task.app_task.ws_manager') as mock_ws_manager:

            # 模拟服务
            mock_app_service = Mock()
            mock_notification_service = Mock()

            # 模拟创建的应用
            mock_app = Mock()
            mock_app.id = self.app_id
            mock_app.name = self.app_name
            mock_app_service.auto_create_app.return_value = mock_app

            # 模拟创建的通知
            mock_notification = AgentNotificationEntity(
                id=str(uuid4()),
                user_id=self.account_id,
                app_id=self.app_id,
                app_name=self.app_name,
                created_at=datetime.now(UTC).replace(tzinfo=None),
                is_read=False,
            )
            mock_notification_service.create_agent_notification.return_value = mock_notification

            # 配置injector
            def get_service(service_class):
                if service_class.__name__ == 'AppService':
                    return mock_app_service
                elif service_class.__name__ == 'NotificationService':
                    return mock_notification_service
                return Mock()

            mock_injector.get.side_effect = get_service

            # 执行任务
            auto_create_app(self.app_name, self.description, self.account_id)

            # 验证WebSocket通知发送
            # 应该使用 agent:{account_id} 作为键
            expected_key = f"agent:{self.account_id}"
            mock_ws_manager.emit_notification_to_user.assert_called_once()

            # 获取调用参数
            call_args = mock_ws_manager.emit_notification_to_user.call_args
            assert call_args[0][0] == expected_key, f"Expected key {expected_key}, got {call_args[0][0]}"
            assert call_args[1]['event'] == 'agent_notification', f"Expected event 'agent_notification', got {call_args[1]['event']}"

    def test_auto_create_app_websocket_key_format(self, setup):
        """测试WebSocket通知键格式是否正确"""
        with patch('internal.task.app_task.injector') as mock_injector, \
             patch('internal.task.app_task.ws_manager') as mock_ws_manager:

            # 模拟服务
            mock_app_service = Mock()
            mock_notification_service = Mock()

            # 模拟创建的应用
            mock_app = Mock()
            mock_app.id = self.app_id
            mock_app.name = self.app_name
            mock_app_service.auto_create_app.return_value = mock_app

            # 模拟创建的通知
            mock_notification = AgentNotificationEntity(
                id=str(uuid4()),
                user_id=self.account_id,
                app_id=self.app_id,
                app_name=self.app_name,
                created_at=datetime.now(UTC).replace(tzinfo=None),
                is_read=False,
            )
            mock_notification_service.create_agent_notification.return_value = mock_notification

            # 配置injector
            def get_service(service_class):
                if service_class.__name__ == 'AppService':
                    return mock_app_service
                elif service_class.__name__ == 'NotificationService':
                    return mock_notification_service
                return Mock()

            mock_injector.get.side_effect = get_service

            # 执行任务
            auto_create_app(self.app_name, self.description, self.account_id)

            # 验证键格式
            call_args = mock_ws_manager.emit_notification_to_user.call_args
            key = call_args[0][0]

            # 键应该以 "agent:" 开头
            assert key.startswith('agent:'), f"Key should start with 'agent:', got {key}"

            # 键应该包含account_id
            assert str(self.account_id) in key, f"Key should contain account_id {self.account_id}, got {key}"

    def test_auto_create_app_error_handling(self, setup):
        """测试auto_create_app错误处理"""
        with patch('internal.task.app_task.injector') as mock_injector:

            # 模拟服务抛出异常
            mock_app_service = Mock()
            mock_app_service.auto_create_app.side_effect = Exception("Database error")

            # 配置injector
            def get_service(service_class):
                if service_class.__name__ == 'AppService':
                    return mock_app_service
                return Mock()

            mock_injector.get.side_effect = get_service

            # 执行任务应该抛出异常
            with pytest.raises(Exception):
                auto_create_app(self.app_name, self.description, self.account_id)
