import json
import uuid
from datetime import datetime, UTC
from uuid import UUID
from typing import Literal

from flask import current_app

from internal.entity.document_index_notification_entity import DocumentIndexNotificationEntity
from internal.entity.agent_notification_entity import AgentNotificationEntity
from internal.extension.redis_extension import redis_client


class NotificationService:
    """通知服务 - 管理文档索引完成通知"""

    NOTIFICATION_KEY_PREFIX = "notification:"
    USER_NOTIFICATIONS_KEY_PREFIX = "user_notifications:"
    USER_DOCUMENT_NOTIFICATIONS_KEY_PREFIX = "user_document_notifications:"
    USER_AGENT_NOTIFICATIONS_KEY_PREFIX = "user_agent_notifications:"

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
        now = datetime.now(UTC).replace(tzinfo=None)

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

        self._push_notification_id(
            user_id=user_id,
            notification_id=notification_id,
            notification_type="document",
        )

        return notification

    def get_user_notifications(
        self,
        user_id: UUID,
        limit: int = 10,
        offset: int = 0,
        notification_type: Literal["document", "agent"] | None = None,
    ) -> tuple[list[DocumentIndexNotificationEntity | AgentNotificationEntity], int]:
        """获取用户的通知列表"""
        notifications = self._load_user_notifications(user_id, notification_type)
        total = len(notifications)
        return notifications[offset : offset + limit], total

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

        # 从用户所有通知列表中移除，兼容旧/新存储结构
        for key in self._get_user_notification_keys(user_id):
            redis_client.lrem(key, 0, notification_id)

        return True

    def _save_notification(self, notification: DocumentIndexNotificationEntity | AgentNotificationEntity) -> None:
        """保存通知到 Redis"""
        notification_key = f"{self.NOTIFICATION_KEY_PREFIX}{notification.id}"

        # 根据通知类型选择保存方法
        if isinstance(notification, AgentNotificationEntity):
            self._save_agent_notification(notification)
        else:
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

    def _get_notification(self, notification_id: str) -> DocumentIndexNotificationEntity | AgentNotificationEntity | None:
        """从 Redis 获取通知"""
        notification_key = f"{self.NOTIFICATION_KEY_PREFIX}{notification_id}"
        data = redis_client.get(notification_key)

        if not data:
            return None

        notification_data = json.loads(data)

        # 判断通知类型：如果有 app_id 则是 Agent 通知，否则是文档索引通知
        if "app_id" in notification_data:
            return self._get_agent_notification(notification_id)
        else:
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
        now = datetime.now(UTC).replace(tzinfo=None)

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

        self._push_notification_id(
            user_id=user_id,
            notification_id=notification_id,
            notification_type="agent",
        )

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

    def _load_user_notifications(
        self,
        user_id: UUID,
        notification_type: Literal["document", "agent"] | None = None,
    ) -> list[DocumentIndexNotificationEntity | AgentNotificationEntity]:
        """加载用户通知，兼容旧的聚合列表和新的类型拆分列表。"""
        notification_ids = self._collect_notification_ids(user_id, notification_type)

        notifications = []
        for notification_id in notification_ids:
            notification = self._get_notification(notification_id)
            if not notification:
                continue
            if notification_type == "document" and isinstance(
                notification, AgentNotificationEntity
            ):
                continue
            if notification_type == "agent" and isinstance(
                notification, DocumentIndexNotificationEntity
            ):
                continue
            notifications.append(notification)

        notifications.sort(key=lambda item: item.created_at, reverse=True)
        return notifications

    def _push_notification_id(
        self,
        user_id: UUID,
        notification_id: str,
        notification_type: Literal["document", "agent"],
    ) -> None:
        """写入通知索引列表，同时兼容旧列表和类型拆分列表。"""
        keys = [
            f"{self.USER_NOTIFICATIONS_KEY_PREFIX}{user_id}",
            (
                f"{self.USER_DOCUMENT_NOTIFICATIONS_KEY_PREFIX}{user_id}"
                if notification_type == "document"
                else f"{self.USER_AGENT_NOTIFICATIONS_KEY_PREFIX}{user_id}"
            ),
        ]

        for key in keys:
            redis_client.lpush(key, notification_id)
            redis_client.expire(key, 7 * 24 * 3600)

    def _collect_notification_ids(
        self,
        user_id: UUID,
        notification_type: Literal["document", "agent"] | None = None,
    ) -> list[str]:
        """收集通知ID并去重。"""
        notification_ids: set[str] = set()

        for key in self._get_user_notification_keys(user_id, notification_type):
            for notification_id in redis_client.lrange(key, 0, -1):
                if isinstance(notification_id, bytes):
                    notification_ids.add(notification_id.decode())
                else:
                    notification_ids.add(str(notification_id))

        return list(notification_ids)

    def _get_user_notification_keys(
        self,
        user_id: UUID,
        notification_type: Literal["document", "agent"] | None = None,
    ) -> list[str]:
        """返回用户通知列表键，兼容旧/新两套结构。"""
        legacy_key = f"{self.USER_NOTIFICATIONS_KEY_PREFIX}{user_id}"
        document_key = f"{self.USER_DOCUMENT_NOTIFICATIONS_KEY_PREFIX}{user_id}"
        agent_key = f"{self.USER_AGENT_NOTIFICATIONS_KEY_PREFIX}{user_id}"

        if notification_type == "document":
            return [legacy_key, document_key]
        if notification_type == "agent":
            return [legacy_key, agent_key]
        return [legacy_key, document_key, agent_key]
