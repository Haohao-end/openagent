from sqlalchemy import (
    Column,
    UUID,
    String,
    Text,
    Integer,
    DateTime,
    text,
    PrimaryKeyConstraint,
    Index,
)
from datetime import UTC, datetime
from internal.extension.database_extension import db

def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)

class Feedback(db.Model):
    """用户反馈模型"""
    __tablename__ = "feedback"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_feedback_id"),
        Index("feedback_app_id_idx", "app_id"),
        Index("feedback_target_id_idx", "target_id"),
        Index("feedback_created_by_idx", "created_by"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    app_id = Column(UUID, nullable=False)
    conversation_id = Column(UUID, nullable=False)
    target_id = Column(UUID, nullable=False) # message_id or span_id
    target_type = Column(String(255), nullable=False) # 'message' or 'span'
    rating = Column(Integer, nullable=True) # 1: like, -1: dislike
    content = Column(Text, nullable=True)
    created_by = Column(UUID, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP(0)'))
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP(0)'),
        server_onupdate=text('CURRENT_TIMESTAMP(0)'),
        default=_utcnow_naive,
    )
