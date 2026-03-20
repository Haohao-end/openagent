import logging
from uuid import UUID

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def auto_create_app(
        name: str,
        description: str,
        account_id: UUID,
) -> None:
    """根据传递的名称、描述、账号id创建一个Agent"""
    from app.http.module import injector
    from internal.service import AppService
    from internal.service.notification_service import NotificationService
    from internal.lib.websocket_emitter import emit_to_user
    from internal.schema.agent_notification_schema import AgentNotificationSchema

    app_service = injector.get(AppService)
    notification_service = injector.get(NotificationService)

    try:
        # 创建应用
        app = app_service.auto_create_app(name, description, account_id)

        # 创建Agent通知
        notification = notification_service.create_agent_notification(
            user_id=account_id,
            app_id=app.id,
            app_name=app.name,
        )

        # 通过 WebSocket 推送通知
        schema = AgentNotificationSchema()
        notification_data = schema.dump(notification)
        emit_to_user(account_id, "agent_notification", notification_data)

        logger.info(f"Created and emitted notification for agent {app.id}")
    except Exception as e:
        logger.error(f"Error in auto_create_app task: {e}")
        raise