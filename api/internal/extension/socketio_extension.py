"""Socket.IO 扩展初始化"""
from flask import Flask


socketio = None


def init_socketio(app: Flask):
    """初始化 Socket.IO 扩展"""
    from flask_socketio import SocketIO

    global socketio

    cors_origins = app.config.get("CORS_ALLOW_ORIGINS") or ["*"]

    socketio = SocketIO(
        app,
        cors_allowed_origins=cors_origins,
        async_mode="threading",
        logger=False,
        engineio_logger=False,
        message_queue=app.config.get("REDIS_URL") or None,
    )

    return socketio
