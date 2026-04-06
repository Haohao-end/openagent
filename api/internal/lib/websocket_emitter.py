"""
WebSocket 事件发射器

提供向特定用户发送 WebSocket 事件的功能。
"""

import logging
from typing import Any, Dict, Optional
from uuid import UUID
from flask import current_app

logger = logging.getLogger(__name__)


def emit_to_user(user_id: UUID, event: str, data: Dict[str, Any], namespace: str = "/") -> bool:
    """
    向特定用户发送 WebSocket 事件

    Args:
        user_id: 用户 ID
        event: 事件名称
        data: 事件数据
        namespace: WebSocket 命名空间，默认为 "/"

    Returns:
        bool: 是否发送成功
    """
    try:
        if not current_app.config.get("SOCKETIO_ENABLED", False):
            logger.debug("SocketIO 未启用，跳过事件发送: %s", event)
            return False

        from internal.lib.websocket_manager import ws_manager
        ws_manager.emit_to_account(user_id, event, data)
        return True
    except Exception as e:
        logger.error("发送 WebSocket 事件失败: %s, 用户: %s, 错误: %s", event, user_id, str(e))
        return False


def emit_message_complete(
    user_id: UUID,
    conversation_id: UUID,
    message_id: UUID,
    content: Optional[str] = None,
    status: str = "completed"
) -> bool:
    """
    发送消息完成事件

    Args:
        user_id: 用户 ID
        conversation_id: 会话 ID
        message_id: 消息 ID
        content: 消息内容（可选）
        status: 消息状态，默认为 "completed"

    Returns:
        bool: 是否发送成功
    """
    data = {
        "conversation_id": str(conversation_id),
        "message_id": str(message_id),
        "status": status,
    }
    if content is not None:
        data["content"] = content

    return emit_to_user(user_id, "message_complete", data)


def emit_message_error(
    user_id: UUID,
    conversation_id: UUID,
    message_id: UUID,
    error: str
) -> bool:
    """
    发送消息错误事件

    Args:
        user_id: 用户 ID
        conversation_id: 会话 ID
        message_id: 消息 ID
        error: 错误信息

    Returns:
        bool: 是否发送成功
    """
    data = {
        "conversation_id": str(conversation_id),
        "message_id": str(message_id),
        "error": error,
        "status": "error",
    }
    return emit_to_user(user_id, "message_error", data)


def emit_message_chunk(
    user_id: UUID,
    conversation_id: UUID,
    message_id: UUID,
    chunk: str
) -> bool:
    """
    发送消息流式数据块

    Args:
        user_id: 用户 ID
        conversation_id: 会话 ID
        message_id: 消息 ID
        chunk: 数据块内容

    Returns:
        bool: 是否发送成功
    """
    data = {
        "conversation_id": str(conversation_id),
        "message_id": str(message_id),
        "chunk": chunk,
    }
    return emit_to_user(user_id, "message_chunk", data)
