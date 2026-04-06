"""WebSocket连接管理器 - 管理用户连接和消息推送"""
import logging
from typing import Dict, Set
from uuid import UUID
from dataclasses import dataclass
from threading import Lock


@dataclass
class UserConnection:
    """用户连接信息"""
    account_id: UUID
    sid: str  # SocketIO session ID
    conversation_id: str = ""
    message_id: str = ""


class WebSocketManager:
    """WebSocket连接管理器"""

    def __init__(self):
        # account_id -> set of sids
        self._user_connections: Dict[str, Set[str]] = {}
        # sid -> UserConnection
        self._sid_to_connection: Dict[str, UserConnection] = {}
        # message_id -> set of sids (订阅该消息的客户端)
        self._message_subscribers: Dict[str, Set[str]] = {}
        # user_id -> set of sids (订阅该用户通知的客户端)
        self._notification_subscribers: Dict[str, Set[str]] = {}
        self._lock = Lock()

    def add_connection(self, sid: str, account_id: UUID) -> None:
        """添加新连接"""
        with self._lock:
            account_key = str(account_id)
            if account_key not in self._user_connections:
                self._user_connections[account_key] = set()
            self._user_connections[account_key].add(sid)

            self._sid_to_connection[sid] = UserConnection(
                account_id=account_id,
                sid=sid
            )
            logging.info(f"[WS] User {account_id} connected, sid={sid}")

    def remove_connection(self, sid: str) -> None:
        """移除连接"""
        with self._lock:
            connection = self._sid_to_connection.pop(sid, None)
            if not connection:
                return

            account_key = str(connection.account_id)
            if account_key in self._user_connections:
                self._user_connections[account_key].discard(sid)
                if not self._user_connections[account_key]:
                    del self._user_connections[account_key]

            # 清理消息订阅
            for message_id, sids in list(self._message_subscribers.items()):
                sids.discard(sid)
                if not sids:
                    del self._message_subscribers[message_id]

            # 清理通知订阅
            for user_id, sids in list(self._notification_subscribers.items()):
                sids.discard(sid)
                if not sids:
                    del self._notification_subscribers[user_id]

            logging.info(f"[WS] User {connection.account_id} disconnected, sid={sid}")

    def subscribe_message(self, sid: str, message_id: str, conversation_id: str = "") -> None:
        """订阅消息更新"""
        with self._lock:
            connection = self._sid_to_connection.get(sid)
            if not connection:
                return

            connection.message_id = message_id
            connection.conversation_id = conversation_id

            if message_id not in self._message_subscribers:
                self._message_subscribers[message_id] = set()
            self._message_subscribers[message_id].add(sid)

            logging.info(f"[WS] sid={sid} subscribed to message={message_id}")

    def unsubscribe_message(self, sid: str, message_id: str) -> None:
        """取消订阅消息"""
        with self._lock:
            if message_id in self._message_subscribers:
                self._message_subscribers[message_id].discard(sid)
                if not self._message_subscribers[message_id]:
                    del self._message_subscribers[message_id]

            connection = self._sid_to_connection.get(sid)
            if connection and connection.message_id == message_id:
                connection.message_id = ""

            logging.info(f"[WS] sid={sid} unsubscribed from message={message_id}")

    def get_message_subscribers(self, message_id: str) -> Set[str]:
        """获取订阅该消息的所有客户端"""
        with self._lock:
            return self._message_subscribers.get(message_id, set()).copy()

    def get_user_sids(self, account_id: UUID) -> Set[str]:
        """获取用户的所有连接"""
        with self._lock:
            account_key = str(account_id)
            return self._user_connections.get(account_key, set()).copy()

    def get_connection(self, sid: str) -> UserConnection | None:
        """获取连接信息"""
        with self._lock:
            return self._sid_to_connection.get(sid)

    def emit_to_account(self, account_id: UUID, event: str, data: dict) -> None:
        """向指定账号的所有连接推送消息"""
        from internal.extension.socketio_extension import socketio

        sids = self.get_user_sids(account_id)
        if not sids:
            logging.debug(f"[WS] No connections for account {account_id}, skipping emit")
            return

        for sid in sids:
            try:
                socketio.emit(event, data, room=sid)
                logging.debug(f"[WS] Emitted {event} to sid={sid}, account={account_id}")
            except Exception as e:
                logging.error(f"[WS] Failed to emit {event} to sid={sid}: {e}")

    def subscribe_notification(self, sid: str, user_id: str) -> None:
        """订阅用户的通知"""
        from flask_socketio import join_room

        with self._lock:
            if user_id not in self._notification_subscribers:
                self._notification_subscribers[user_id] = set()
            self._notification_subscribers[user_id].add(sid)

        join_room(user_id, sid=sid)
        logging.info(f"[WS] sid={sid} subscribed to notifications for user={user_id}")

    def unsubscribe_notification(self, sid: str, user_id: str) -> None:
        """取消订阅用户的通知"""
        from flask_socketio import leave_room

        with self._lock:
            if user_id in self._notification_subscribers:
                self._notification_subscribers[user_id].discard(sid)
                if not self._notification_subscribers[user_id]:
                    del self._notification_subscribers[user_id]

        leave_room(user_id, sid=sid)
        logging.info(f"[WS] sid={sid} unsubscribed from notifications for user={user_id}")

    def emit_notification_to_user(self, user_id: str, notification_data: dict, event: str = "document_index_notification") -> None:
        """向指定用户推送通知"""
        from internal.extension.socketio_extension import socketio

        if socketio is None:
            logging.warning(f"[WS] SocketIO not initialized, skipping {event} for user={user_id}")
            return

        try:
            # Use Socket.IO rooms so Celery workers can broadcast through Redis message_queue.
            socketio.emit(event, notification_data, room=user_id)
            logging.debug(f"[WS] Emitted {event} to room={user_id}")
        except Exception as e:
            logging.error(f"[WS] Failed to emit {event} to room={user_id}: {e}")


# 全局单例
ws_manager = WebSocketManager()
