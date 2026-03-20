import json
import uuid
from datetime import datetime
from uuid import UUID

from flask import current_app

from internal.entity.document_index_notification_entity import DocumentIndexNotificationEntity
from internal.entity.agent_notification_entity import AgentNotificationEntity
from internal.extension.redis_extension import redis_client


class NotificationService:
    """通知服务 - 管理文档索引完成通知"""

    NOTIFICATION_KEY_PREFIX = "notification:"
    USER_NOTIFICATIONS_KEY_PREFIX = "user_notifications:"

    def create_notification(
        self,
        user_id: UUID,
        dataset_id: UUID,
        document_id: UUID,
        document_name: str,
        segment_count: int,
        index_duration: float,
        status: str = "success",
        error_message: str = "",
    ) -> DocumentIndexNotificationEntity:
        """创建文档索引完成通知"""
        notification_id = str(uuid.uuid4())
        now = datetime.utcnow()

        notification = DocumentIndexNotificationEntity(
            id=notification_id,
            user_id=user_id,
            dataset_id=dataset_id,
            document_id=document_id,
            document_name=document_name,
            segment_count=segment_count,
            index_duration=index_duration,
            created_at=now,
            status=status,
            error_message=error_message,
            is_read=False,
        )

        # 存储通知到 Redis
        self._save_notification(notification)

        # 添加到用户的通知列表
        user_notifications_key = f"{self.USER_NOTIFICATIONS_KEY_PREFIX}{user_id}"
        redis_client.lpush(user_notifications_key, notification_id)
        # 设置过期时间为 7 天
        redis_client.expire(user_notifications_key, 7 * 24 * 3600)

        return notification

    def get_user_notifications(
        self, user_id: UUID, limit: int = 10, offset: int = 0
    ) -> tuple[list[DocumentIndexNotificationEntity], int]:
        """获取用户的通知列表"""
        user_notifications_key = f"{self.USER_NOTIFICATIONS_KEY_PREFIX}{user_id}"

        # 获取通知 ID 列表
        notification_ids = redis_client.lrange(
            user_notifications_key, offset, offset + limit - 1
        )

        # 获取总数
        total = redis_client.llen(user_notifications_key)

        # 获取通知详情
        notifications = []
        for notification_id in notification_ids:
            notification = self._get_notification(notification_id.decode())
            if notification:
                notifications.append(notification)

        return notifications, total

    def mark_as_read(self, user_id: UUID, notification_id: str) -> bool:
        """标记通知为已读"""
        notification = self._get_notification(notification_id)
        if not notification or notification.user_id != user_id:
            return False

        notification.is_read = True
        self._save_notification(notification)
        return True

    def delete_notification(self, user_id: UUID, notification_id: str) -> bool:
        """删除通知"""
        notification = self._get_notification(notification_id)
        if not notification or notification.user_id != user_id:
            return False

        # 从 Redis 中删除
        notification_key = f"{self.NOTIFICATION_KEY_PREFIX}{notification_id}"
        redis_client.delete(notification_key)

        # 从用户通知列表中移除
        user_notifications_key = f"{self.USER_NOTIFICATIONS_KEY_PREFIX}{user_id}"
        redis_client.lrem(user_notifications_key, 0, notification_id)

        return True

    def _save_notification(self, notification: DocumentIndexNotificationEntity) -> None:
        """保存通知到 Redis"""
        notification_key = f"{self.NOTIFICATION_KEY_PREFIX}{notification.id}"
        notification_data = {
            "id": notification.id,
            "user_id": str(notification.user_id),
            "dataset_id": str(notification.dataset_id),
            "document_id": str(notification.document_id),
            "document_name": notification.document_name,
            "segment_count": notification.segment_count,
            "index_duration": notification.index_duration,
            "created_at": notification.created_at.isoformat(),
            "status": notification.status,
            "error_message": notification.error_message,
            "is_read": notification.is_read,
        }
        redis_client.setex(
            notification_key, 7 * 24 * 3600, json.dumps(notification_data)
        )

    def _get_notification(self, notification_id: str) -> DocumentIndexNotificationEntity | None:
        """从 Redis 获取通知"""
        notification_key = f"{self.NOTIFICATION_KEY_PREFIX}{notification_id}"
        data = redis_client.get(notification_key)

        if not data:
            return None

        notification_data = json.loads(data)
        return DocumentIndexNotificationEntity(
            id=notification_data["id"],
            user_id=UUID(notification_data["user_id"]),
            dataset_id=UUID(notification_data["dataset_id"]),
            document_id=UUID(notification_data["document_id"]),
            document_name=notification_data["document_name"],
            segment_count=notification_data["segment_count"],
            index_duration=notification_data["index_duration"],
            created_at=datetime.fromisoformat(notification_data["created_at"]),
            status=notification_data.get("status", "success"),
            error_message=notification_data.get("error_message", ""),
            is_read=notification_data["is_read"],
        )

    def create_agent_notification(
        self,
        user_id: UUID,
        app_id: UUID,
        app_name: str,
    ) -> AgentNotificationEntity:
        """创建Agent构建完成通知"""
        notification_id = str(uuid.uuid4())
        now = datetime.utcnow()

        notification = AgentNotificationEntity(
            id=notification_id,
            user_id=user_id,
            app_id=app_id,
            app_name=app_name,
            created_at=now,
            is_read=False,
        )

        # 存储通知到 Redis
        self._save_agent_notification(notification)

        # 添加到用户的通知列表
        user_notifications_key = f"{self.USER_NOTIFICATIONS_KEY_PREFIX}{user_id}"
        redis_client.lpush(user_notifications_key, notification_id)
        # 设置过期时间为 7 天
        redis_client.expire(user_notifications_key, 7 * 24 * 3600)

        return notification

    def _save_agent_notification(self, notification: AgentNotificationEntity) -> None:
        """保存Agent通知到 Redis"""
        notification_key = f"{self.NOTIFICATION_KEY_PREFIX}{notification.id}"
        notification_data = {
            "id": notification.id,
            "user_id": str(notification.user_id),
            "app_id": str(notification.app_id),
            "app_name": notification.app_name,
            "created_at": notification.created_at.isoformat(),
            "is_read": notification.is_read,
        }
        redis_client.setex(
            notification_key, 7 * 24 * 3600, json.dumps(notification_data)
        )

    def _get_agent_notification(self, notification_id: str) -> AgentNotificationEntity | None:
        """从Redis获取Agent通知"""
        notification_key = f"{self.NOTIFICATION_KEY_PREFIX}{notification_id}"
        data = redis_client.get(notification_key)

        if not data:
            return None

        notification_data = json.loads(data)
        return AgentNotificationEntity(
            id=notification_data["id"],
            user_id=UUID(notification_data["user_id"]),
            app_id=UUID(notification_data["app_id"]),
            app_name=notification_data["app_name"],
            created_at=datetime.fromisoformat(notification_data["created_at"]),
            is_read=notification_data["is_read"],
        )
