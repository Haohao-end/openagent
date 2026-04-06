from dataclasses import dataclass
from uuid import UUID
from datetime import datetime


@dataclass
class AgentNotificationEntity:
    """Agent构建完成通知实体"""
    id: str
    user_id: UUID
    app_id: UUID
    app_name: str
    created_at: datetime
    is_read: bool = False
