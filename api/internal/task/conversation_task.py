"""
会话相关的 Celery 后台任务

处理会话消息处理、总结生成等异步任务。
"""

import logging
from uuid import UUID
from celery import shared_task
from flask import current_app

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_conversation_message(self, conversation_id: str, message_id: str, user_id: str):
    """
    处理会话消息

    Args:
        conversation_id: 会话 ID
        message_id: 消息 ID
        user_id: 用户 ID
    """
    try:
        from internal.service import ConversationService
        from internal.lib.websocket_emitter import emit_message_complete

        conversation_id_uuid = UUID(conversation_id)
        message_id_uuid = UUID(message_id)
        user_id_uuid = UUID(user_id)

        # 处理消息逻辑
        logger.info(f"处理会话消息: {conversation_id}, 消息: {message_id}")

        # 发送完成事件
        emit_message_complete(user_id_uuid, conversation_id_uuid, message_id_uuid)

    except Exception as exc:
        logger.error(f"处理会话消息失败: {str(exc)}")
        # 重试
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def generate_conversation_summary(self, conversation_id: str, user_id: str):
    """
    生成会话总结

    Args:
        conversation_id: 会话 ID
        user_id: 用户 ID
    """
    try:
        from internal.service import ConversationService

        conversation_id_uuid = UUID(conversation_id)
        user_id_uuid = UUID(user_id)

        logger.info(f"生成会话总结: {conversation_id}")

        # 生成总结逻辑
        # conversation_service.generate_summary(conversation_id_uuid, user_id_uuid)

    except Exception as exc:
        logger.error(f"生成会话总结失败: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def index_conversation_to_vector_db(self, conversation_id: str, user_id: str):
    """
    将会话索引到向量数据库

    Args:
        conversation_id: 会话 ID
        user_id: 用户 ID
    """
    try:
        from internal.service import ConversationService

        conversation_id_uuid = UUID(conversation_id)
        user_id_uuid = UUID(user_id)

        logger.info(f"索引会话到向量数据库: {conversation_id}")

        # 索引逻辑
        # conversation_service.index_to_vector_db(conversation_id_uuid, user_id_uuid)

    except Exception as exc:
        logger.error(f"索引会话到向量数据库失败: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def cleanup_old_conversations(self, days: int = 30):
    """
    清理旧会话

    Args:
        days: 保留天数，默认 30 天
    """
    try:
        from internal.service import ConversationService

        logger.info(f"清理 {days} 天前的会话")

        # 清理逻辑
        # conversation_service.cleanup_old_conversations(days)

    except Exception as exc:
        logger.error(f"清理旧会话失败: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def save_agent_thoughts_async(self, conversation_id: str, message_id: str, thoughts: list):
    """
    异步保存 Agent 思考过程

    Args:
        conversation_id: 会话 ID
        message_id: 消息 ID
        thoughts: 思考过程列表
    """
    try:
        from internal.service import ConversationService

        conversation_id_uuid = UUID(conversation_id)
        message_id_uuid = UUID(message_id)

        logger.info(f"保存 Agent 思考过程: {message_id}")

        # 保存逻辑
        # conversation_service.save_agent_thoughts(conversation_id_uuid, message_id_uuid, thoughts)

    except Exception as exc:
        logger.error(f"保存 Agent 思考过程失败: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def update_message_error_async(self, conversation_id: str, message_id: str, error: str):
    """
    异步更新消息错误状态

    Args:
        conversation_id: 会话 ID
        message_id: 消息 ID
        error: 错误信息
    """
    try:
        from internal.service import ConversationService

        conversation_id_uuid = UUID(conversation_id)
        message_id_uuid = UUID(message_id)

        logger.info(f"更新消息错误状态: {message_id}")

        # 更新逻辑
        # conversation_service.update_message_error(conversation_id_uuid, message_id_uuid, error)

    except Exception as exc:
        logger.error(f"更新消息错误状态失败: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)
