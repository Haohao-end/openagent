from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import current_user, login_required
from injector import inject

from internal.schema.document_index_notification_schema import DocumentIndexNotificationSchema
from internal.schema.agent_notification_schema import AgentNotificationSchema
from internal.entity.agent_notification_entity import AgentNotificationEntity
from internal.entity.document_index_notification_entity import DocumentIndexNotificationEntity
from internal.service.notification_service import NotificationService
from pkg.paginator import PageModel
from pkg.response import success_json, validate_error_json


@inject
@dataclass
class NotificationHandler:
    """通知处理器"""
    notification_service: NotificationService

    @login_required
    def get_notifications(self):
        """获取用户的通知列表"""
        # 获取分页参数
        page = request.args.get("page", 1, type=int)
        limit = request.args.get("limit", 10, type=int)
        offset = (page - 1) * limit
        notification_type = request.args.get("type", type=str)

        if notification_type not in (None, "", "document", "agent"):
            return validate_error_json({"type": ["通知类型非法"]})

        # 获取通知列表
        notifications, total = self.notification_service.get_user_notifications(
            current_user.id,
            limit=limit,
            offset=offset,
            notification_type=notification_type or None,
        )

        # 根据通知类型选择不同的 schema 进行序列化
        serialized_notifications = []
        for notification in notifications:
            if isinstance(notification, AgentNotificationEntity):
                schema = AgentNotificationSchema()
                serialized_notifications.append(schema.dump(notification))
            elif isinstance(notification, DocumentIndexNotificationEntity):
                schema = DocumentIndexNotificationSchema()
                serialized_notifications.append(schema.dump(notification))

        return success_json(
            PageModel(
                list=serialized_notifications,
                paginator={
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "total_page": (total + limit - 1) // limit,
                },
            )
        )

    @login_required
    def mark_notification_as_read(self, notification_id: str):
        """标记通知为已读"""
        success = self.notification_service.mark_as_read(current_user.id, notification_id)
        if not success:
            return validate_error_json({"notification_id": ["通知不存在或无权限"]})

        return success_json({"message": "标记成功"})

    @login_required
    def delete_notification(self, notification_id: str):
        """删除通知"""
        success = self.notification_service.delete_notification(current_user.id, notification_id)
        if not success:
            return validate_error_json({"notification_id": ["通知不存在或无权限"]})

        return success_json({"message": "删除成功"})
