from sqlalchemy import (
    Column,
    UUID,
    DateTime,
    text,
    PrimaryKeyConstraint,
    Index
)
from datetime import UTC, datetime

from internal.extension.database_extension import db


def _utcnow_naive() -> datetime:
    """返回无时区的 UTC 时间，兼容数据库 DateTime 列且避免 utcnow 退化警告。"""
    return datetime.now(UTC).replace(tzinfo=None)
class EndUser(db.Model):
    """终端用户表模型"""
    __tablename__ = "end_user"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_end_user_id"),
        Index("end_user_tenant_id_idx", "tenant_id"),
        Index("end_user_app_id_idx", "app_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))  # 终端id
    tenant_id = Column(UUID, nullable=False)  # 归属的账号/空间id
    app_id = Column(UUID, nullable=False)  # 归属应用的id，终端用户只能在应用下使用
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP(0)'),
        server_onupdate=text('CURRENT_TIMESTAMP(0)'),
        default=_utcnow_naive,
    )
    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP(0)'))
