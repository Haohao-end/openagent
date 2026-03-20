"""WebSocket 事件处理"""
import logging
from typing import Any

from flask import request
from flask_login import current_user

from internal.extension.socketio_extension import socketio
from internal.lib.websocket_manager import ws_manager


@socketio.on("connect")
def handle_connect(*_args: Any, **_kwargs: Any) -> None:
    """建立连接时，记录登录用户连接。"""
    if not getattr(current_user, "is_authenticated", False):
        logging.debug("[WS] anonymous connection sid=%s", request.sid)
        return

    ws_manager.add_connection(request.sid, current_user.id)


@socketio.on("disconnect")
def handle_disconnect() -> None:
    """断开连接时清理连接记录。"""
    ws_manager.remove_connection(request.sid)


@socketio.on("subscribe_message")
def handle_subscribe_message(data: dict[str, Any] | None = None) -> None:
    """订阅消息流更新。"""
    payload = data or {}
    message_id = str(payload.get("message_id", "")).strip()
    conversation_id = str(payload.get("conversation_id", "")).strip()
    if not message_id:
        return

    ws_manager.subscribe_message(request.sid, message_id, conversation_id)


@socketio.on("unsubscribe_message")
def handle_unsubscribe_message(data: dict[str, Any] | None = None) -> None:
    """取消订阅消息流更新。"""
    payload = data or {}
    message_id = str(payload.get("message_id", "")).strip()
    if not message_id:
        return

    ws_manager.unsubscribe_message(request.sid, message_id)


@socketio.on("subscribe_document_index_notification")
def handle_subscribe_document_index_notification(data: dict[str, Any] | None = None) -> None:
    """订阅文档索引完成通知。"""
    payload = data or {}
    user_id = str(payload.get("user_id", "")).strip()
    if not user_id:
        return

    ws_manager.subscribe_notification(request.sid, user_id)


@socketio.on("unsubscribe_document_index_notification")
def handle_unsubscribe_document_index_notification(data: dict[str, Any] | None = None) -> None:
    """取消订阅文档索引完成通知。"""
    payload = data or {}
    user_id = str(payload.get("user_id", "")).strip()
    if not user_id:
        return

    ws_manager.unsubscribe_notification(request.sid, user_id)


@socketio.on("subscribe_agent_notification")
def handle_subscribe_agent_notification(data: dict[str, Any] | None = None) -> None:
    """订阅Agent构建完成通知。"""
    payload = data or {}
    user_id = str(payload.get("user_id", "")).strip()
    if not user_id:
        return

    ws_manager.subscribe_notification(request.sid, user_id)


@socketio.on("unsubscribe_agent_notification")
def handle_unsubscribe_agent_notification(data: dict[str, Any] | None = None) -> None:
    """取消订阅Agent构建完成通知。"""
    payload = data or {}
    user_id = str(payload.get("user_id", "")).strip()
    if not user_id:
        return

    ws_manager.unsubscribe_notification(request.sid, user_id)

