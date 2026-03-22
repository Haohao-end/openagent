from dataclasses import dataclass
from uuid import UUID
from datetime import datetime


@dataclass
class DocumentIndexNotificationEntity:
    """文档索引完成通知实体"""
    id: str
    user_id: UUID
    dataset_id: UUID
    document_id: UUID
    document_name: str
    segment_count: int
    index_duration: float  # 索引耗时（秒）
    created_at: datetime
    status: str = "success"  # success 或 error
    error_message: str = ""  # 错误信息
    is_read: bool = False
