import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from injector import inject
from sqlalchemy import desc

from internal.exception import FailException
from internal.model import Account, Message
from pkg.sqlalchemy import SQLAlchemy

from .base_service import BaseService
from .intent_recognition_service import IntentRecognitionService


@inject
@dataclass
class HomeService(BaseService):
    """首页服务"""

    db: SQLAlchemy
    intent_recognition_service: IntentRecognitionService

    RECENT_MESSAGES_LIMIT = 8
    MIN_MESSAGES_FOR_INTENT = 1

    def get_user_intent(self, user: Account) -> dict[str, Any]:
        """获取用户的意图识别结果"""
        try:
            user_id = str(user.id)

            # 1. 获取最近的消息
            recent_messages = self._get_recent_messages(user)

            # 2. 如果消息不足，返回默认文案
            if len(recent_messages) < self.MIN_MESSAGES_FOR_INTENT:
                logging.info(
                    f"User {user_id} has insufficient messages, returning default intent"
                )
                return self.intent_recognition_service.DEFAULT_INTENT

            # 3. 获取最后一条消息的时间戳与消息签名
            last_message_timestamp = recent_messages[-1].get("created_at")
            message_signature = self._build_message_signature(recent_messages)

            # 4. 检查缓存
            cached_intent = self.intent_recognition_service.get_cached_intent(user_id)
            if cached_intent:
                cached_signature = cached_intent.get("message_signature")
                cached_timestamp = cached_intent.get("last_message_timestamp")

                # 新版本优先使用消息签名判断，避免同一条消息的回答更新后误用旧缓存。
                if cached_signature and cached_signature == message_signature:
                    logging.info(f"Cache hit for user {user_id}")
                    return cached_intent

                # 兼容旧缓存：旧缓存没有 message_signature 时，仍按最后消息时间戳命中一次并回填签名。
                if not cached_signature and cached_timestamp == last_message_timestamp:
                    logging.info(f"Legacy cache hit for user {user_id}")
                    cached_intent["message_signature"] = message_signature
                    self.intent_recognition_service.cache_intent(user_id, cached_intent)
                    return cached_intent

                # 如果签名不同，清除缓存
                logging.info(
                    f"Cache invalidated for user {user_id}, message signature changed"
                )
                self.intent_recognition_service.clear_cache(user_id)

            # 5. 调用模型进行意图识别
            logging.info(f"Recognizing intent for user {user_id}")
            intent_result = self.intent_recognition_service.recognize(recent_messages)

            # 6. 添加消息版本信息到结果
            intent_result["last_message_timestamp"] = last_message_timestamp
            intent_result["message_signature"] = message_signature

            # 7. 缓存结果
            self.intent_recognition_service.cache_intent(user_id, intent_result)

            return intent_result

        except FailException:
            raise
        except Exception as e:
            logging.error(f"Failed to get user intent: {str(e)}")

            # 尝试返回缓存的旧数据
            cached_intent = self.intent_recognition_service.get_cached_intent(
                str(user.id)
            )
            if cached_intent:
                logging.info(f"Returning cached intent for user {user.id} due to error")
                return cached_intent

            # 如果没有缓存，返回默认文案
            return self.intent_recognition_service.DEFAULT_INTENT

    def _get_recent_messages(self, user: Account) -> list[dict[str, Any]]:
        """获取用户最近的输入消息（仅保留用户输入，不包含 AI 回复）"""
        try:
            # 获取当前用户最近的有效消息（覆盖所有会话，避免只看最新会话导致长期默认）
            messages = (
                self.db.session.query(Message)
                .filter(
                    Message.created_by == user.id,
                    Message.is_deleted == False,
                )
                .order_by(desc(Message.created_at))
                .limit(self.RECENT_MESSAGES_LIMIT)
                .all()
            )

            # 反转消息顺序（从旧到新）
            messages = list(reversed(messages))

            # 转换为字典格式，仅保留用户输入作为意图识别上下文
            result: list[dict[str, Any]] = []
            for msg in messages:
                message_id = str(msg.id) if getattr(msg, "id", None) else ""
                created_at_value = getattr(msg, "created_at", None)
                updated_at_value = getattr(msg, "updated_at", None)
                created_at = (
                    created_at_value.isoformat()
                    if isinstance(created_at_value, datetime)
                    else None
                )
                updated_at = (
                    updated_at_value.isoformat()
                    if isinstance(updated_at_value, datetime)
                    else None
                )

                # 添加用户消息（query）
                if msg.query:
                    result.append(
                        {
                            "id": message_id,
                            "role": "user",
                            "content": msg.query,
                            "created_at": created_at,
                            "updated_at": updated_at,
                        }
                    )

            return result

        except Exception as e:
            logging.error(f"Failed to get recent messages: {str(e)}")
            return []

    @classmethod
    def _build_message_signature(cls, messages: list[dict[str, Any]]) -> str:
        """根据最近消息内容生成稳定签名，用于判断意图缓存是否仍然有效"""
        signature_items = [
            {
                "id": str(message.get("id") or ""),
                "role": str(message.get("role") or ""),
                "content": str(message.get("content") or ""),
                "created_at": str(message.get("created_at") or ""),
                "updated_at": str(message.get("updated_at") or ""),
            }
            for message in messages
        ]
        payload = json.dumps(signature_items, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
