import logging
from uuid import UUID

import httpx
from celery import shared_task
from openai import APIConnectionError

logger = logging.getLogger(__name__)

_PUBLIC_APP_REGISTRY_RETRY_BASE_SECONDS = 30
_PUBLIC_APP_REGISTRY_RETRY_MAX_SECONDS = 300


def _public_app_registry_retry_countdown(retries: int) -> int:
    normalized_retries = max(int(retries or 0), 0)
    return min(
        _PUBLIC_APP_REGISTRY_RETRY_BASE_SECONDS * (2 ** normalized_retries),
        _PUBLIC_APP_REGISTRY_RETRY_MAX_SECONDS,
    )


@shared_task
def auto_create_app(
        name: str,
        description: str,
        account_id: UUID,
) -> None:
    """根据传递的名称、描述、账号id创建一个Agent"""
    from app.http.app import injector
    from internal.service import AppService
    from internal.service.notification_service import NotificationService
    from internal.lib.websocket_manager import ws_manager
    from internal.schema.agent_notification_schema import AgentNotificationSchema

    app_service = injector.get(AppService)
    notification_service = injector.get(NotificationService)

    try:
        logger.info(
            "Starting auto_create_app task, account_id=%s, name=%s",
            account_id,
            name,
        )
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
        agent_notification_key = f"agent:{account_id}"
        ws_manager.emit_notification_to_user(agent_notification_key, notification_data, event="agent_notification")

        logger.info("Created and emitted notification for agent %s", app.id)
    except Exception as e:
        logger.exception("Error in auto_create_app task: %s", str(e))
        raise


@shared_task(bind=True, max_retries=3)
def sync_public_app_registry(self, app_id: str) -> None:
    """根据应用当前状态同步公共Agent索引。"""
    from app.http.app import injector
    from internal.service import PublicAgentRegistryService

    registry_service = injector.get(PublicAgentRegistryService)
    normalized_app_id = UUID(str(app_id))

    try:
        logger.info("Starting sync_public_app_registry task, app_id=%s", normalized_app_id)
        registry_service.sync_public_app(normalized_app_id)
        logger.info("Finished sync_public_app_registry task, app_id=%s", normalized_app_id)
    except (APIConnectionError, httpx.TransportError) as exc:
        countdown = _public_app_registry_retry_countdown(getattr(self.request, "retries", 0))
        logger.warning(
            "Transient connection error in sync_public_app_registry task, app_id=%s, retry_in=%ss",
            normalized_app_id,
            countdown,
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=countdown)
    except Exception as e:
        logger.exception("Error in sync_public_app_registry task: %s", str(e))
        raise
