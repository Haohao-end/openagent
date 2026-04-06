import logging
from dataclasses import dataclass
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
    MIN_MESSAGES_FOR_INTENT = 2

    def get_user_intent(self, user: Account) -> dict[str, Any]:
        """获取用户的意图识别结果"""
        try:
            user_id = str(user.id)

            # 1. 获取最近的消息
            recent_messages = self._get_recent_messages(user)

            # 2. 如果消息不足，返回默认文案
            if len(recent_messages) < self.MIN_MESSAGES_FOR_INTENT:
                logging.info(f"User {user_id} has insufficient messages, returning default intent")
                return self.intent_recognition_service.DEFAULT_INTENT

            # 3. 获取最后一条消息的时间戳
            last_message_timestamp = recent_messages[-1].get("created_at")

            # 4. 检查缓存
            cached_intent = self.intent_recognition_service.get_cached_intent(user_id)
            if cached_intent:
                cached_timestamp = cached_intent.get("last_message_timestamp")

                # 如果时间戳相同，返回缓存
                if cached_timestamp == last_message_timestamp:
                    logging.info(f"Cache hit for user {user_id}")
                    return cached_intent

                # 如果时间戳不同，清除缓存
                logging.info(f"Cache invalidated for user {user_id}, message timestamp changed")
                self.intent_recognition_service.clear_cache(user_id)

            # 5. 调用模型进行意图识别
            logging.info(f"Recognizing intent for user {user_id}")
            intent_result = self.intent_recognition_service.recognize(recent_messages)

            # 6. 添加消息时间戳到结果
            intent_result["last_message_timestamp"] = last_message_timestamp

            # 7. 缓存结果
            self.intent_recognition_service.cache_intent(user_id, intent_result)

            return intent_result

        except FailException:
            raise
        except Exception as e:
            logging.error(f"Failed to get user intent: {str(e)}")

            # 尝试返回缓存的旧数据
            cached_intent = self.intent_recognition_service.get_cached_intent(str(user.id))
            if cached_intent:
                logging.info(f"Returning cached intent for user {user.id} due to error")
                return cached_intent

            # 如果没有缓存，返回默认文案
            return self.intent_recognition_service.DEFAULT_INTENT

    def _get_recent_messages(self, user: Account) -> list[dict[str, Any]]:
        """获取用户最近的消息"""
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

            # 转换为字典格式
            result: list[dict[str, Any]] = []
            for msg in messages:
                # 添加用户消息（query）
                if msg.query:
                    result.append(
                        {
                            "role": "user",
                            "content": msg.query,
                            "created_at": msg.created_at.isoformat() if msg.created_at else None,
                        }
                    )

                # 添加 AI 回复（answer）
                if msg.answer:
                    result.append(
                        {
                            "role": "assistant",
                            "content": msg.answer,
                            "created_at": msg.created_at.isoformat() if msg.created_at else None,
                        }
                    )

            return result

        except Exception as e:
            logging.error(f"Failed to get recent messages: {str(e)}")
            return []
