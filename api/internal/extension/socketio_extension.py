"""Socket.IO 扩展初始化"""
import logging
from typing import Any, Mapping

from flask import Flask


socketio = None


def resolve_cors_settings(config: Mapping[str, Any]) -> tuple[list[str], bool]:
    """统一计算 HTTP / Socket.IO 使用的 CORS 配置。"""
    cors_allow_origins = list(config.get("CORS_ALLOW_ORIGINS") or [])
    cors_supports_credentials = bool(config.get("CORS_SUPPORTS_CREDENTIALS", True))

    if cors_supports_credentials and cors_allow_origins == ["*"]:
        logging.warning("CORS_ALLOW_ORIGINS='*' 与 supports_credentials=True 冲突，已拒绝使用通配符")
        cors_allow_origins = []

    if not cors_allow_origins:
        cors_allow_origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]

    return cors_allow_origins, cors_supports_credentials


def init_socketio(app: Flask):
    """初始化 Socket.IO 扩展"""
    from flask_socketio import SocketIO
    from internal.handler.websocket_handler import register_socketio_handlers

    global socketio

    cors_origins, cors_credentials = resolve_cors_settings(app.config)

    socketio = SocketIO(
        app,
        cors_allowed_origins=cors_origins,
        cors_credentials=cors_credentials,
        async_mode="threading",
        logger=False,
        engineio_logger=False,
        message_queue=app.config.get("REDIS_URL") or None,
    )

    register_socketio_handlers(socketio)

    return socketio
