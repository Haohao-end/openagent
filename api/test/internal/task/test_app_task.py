import pytest
from uuid import uuid4
from datetime import datetime, UTC
from types import SimpleNamespace
from unittest.mock import Mock, patch
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
        mock_app_service = Mock()
        mock_notification_service = Mock()
        mock_ws_manager = Mock()
        mock_app = SimpleNamespace(id=self.app_id, name=self.app_name)
        mock_app_service.auto_create_app.return_value = mock_app
        mock_notification = AgentNotificationEntity(
            id=str(uuid4()),
            user_id=self.account_id,
            app_id=self.app_id,
            app_name=self.app_name,
            created_at=datetime.now(UTC).replace(tzinfo=None),
            is_read=False,
        )
        mock_notification_service.create_agent_notification.return_value = mock_notification
        injector = SimpleNamespace(
            get=lambda cls: mock_app_service if cls.__name__ == "AppService" else mock_notification_service
        )

        with patch("app.http.app.injector", injector), patch(
            "internal.lib.websocket_manager.ws_manager",
            mock_ws_manager,
        ):
            auto_create_app(self.app_name, self.description, self.account_id)

        mock_app_service.auto_create_app.assert_called_once_with(
            self.app_name, self.description, self.account_id
        )
        mock_notification_service.create_agent_notification.assert_called_once_with(
            user_id=self.account_id,
            app_id=self.app_id,
            app_name=self.app_name,
        )

    def test_auto_create_app_emits_websocket_notification(self, setup):
        """测试auto_create_app是否通过WebSocket发送通知"""
        mock_app_service = Mock()
        mock_notification_service = Mock()
        mock_ws_manager = Mock()
        mock_app = SimpleNamespace(id=self.app_id, name=self.app_name)
        mock_app_service.auto_create_app.return_value = mock_app
        mock_notification = AgentNotificationEntity(
            id=str(uuid4()),
            user_id=self.account_id,
            app_id=self.app_id,
            app_name=self.app_name,
            created_at=datetime.now(UTC).replace(tzinfo=None),
            is_read=False,
        )
        mock_notification_service.create_agent_notification.return_value = mock_notification
        injector = SimpleNamespace(
            get=lambda cls: mock_app_service if cls.__name__ == "AppService" else mock_notification_service
        )

        with patch("app.http.app.injector", injector), patch(
            "internal.lib.websocket_manager.ws_manager",
            mock_ws_manager,
        ):
            auto_create_app(self.app_name, self.description, self.account_id)

        expected_key = f"agent:{self.account_id}"
        mock_ws_manager.emit_notification_to_user.assert_called_once()
        call_args = mock_ws_manager.emit_notification_to_user.call_args
        assert call_args[0][0] == expected_key
        assert call_args[1]["event"] == "agent_notification"

    def test_auto_create_app_websocket_key_format(self, setup):
        """测试WebSocket通知键格式是否正确"""
        mock_app_service = Mock()
        mock_notification_service = Mock()
        mock_ws_manager = Mock()
        mock_app = SimpleNamespace(id=self.app_id, name=self.app_name)
        mock_app_service.auto_create_app.return_value = mock_app
        mock_notification = AgentNotificationEntity(
            id=str(uuid4()),
            user_id=self.account_id,
            app_id=self.app_id,
            app_name=self.app_name,
            created_at=datetime.now(UTC).replace(tzinfo=None),
            is_read=False,
        )
        mock_notification_service.create_agent_notification.return_value = mock_notification
        injector = SimpleNamespace(
            get=lambda cls: mock_app_service if cls.__name__ == "AppService" else mock_notification_service
        )

        with patch("app.http.app.injector", injector), patch(
            "internal.lib.websocket_manager.ws_manager",
            mock_ws_manager,
        ):
            auto_create_app(self.app_name, self.description, self.account_id)

        key = mock_ws_manager.emit_notification_to_user.call_args[0][0]
        assert key.startswith("agent:")
        assert str(self.account_id) in key

    def test_auto_create_app_error_handling(self, setup):
        """测试auto_create_app错误处理"""
        mock_app_service = Mock()
        mock_app_service.auto_create_app.side_effect = Exception("Database error")
        injector = SimpleNamespace(
            get=lambda cls: mock_app_service if cls.__name__ == "AppService" else Mock()
        )

        with patch("app.http.app.injector", injector):
            with pytest.raises(Exception):
                auto_create_app(self.app_name, self.description, self.account_id)
