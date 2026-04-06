"""
标签模型

定义标签、应用标签、工作流标签的数据库模型。
"""

from datetime import UTC, datetime
import uuid
from sqlalchemy import (
    Column,
    UUID,
    String,
    Text,
    DateTime,
    PrimaryKeyConstraint,
    ForeignKey,
    Index,
    text,
)
from internal.extension.database_extension import db
from internal.entity.tag_entity import TagStatus, TagType


def _utcnow_naive() -> datetime:
    """返回无时区的 UTC 时间，兼容数据库 DateTime 列且避免 utcnow 退化警告。"""
    return datetime.now(UTC).replace(tzinfo=None)


class Tag(db.Model):
    """标签模型"""
    __tablename__ = "tag"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_tag_id"),
        Index("tag_account_id_idx", "account_id"),
        Index("tag_status_idx", "status"),
        Index("tag_type_idx", "tag_type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    account_id = Column(UUID, nullable=False)  # 创建账号 ID
    name = Column(String(50), nullable=False)  # 标签名称
    description = Column(Text, nullable=True, server_default=text("''::text"))  # 标签描述
    tag_type = Column(String(50), nullable=False, server_default=TagType.CUSTOM.value)  # 标签类型
    status = Column(String(50), nullable=False, server_default=TagStatus.ACTIVE.value)  # 标签状态
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
        default=_utcnow_naive,
    )
    created_at = Column(DateTime, nullable=False, default=_utcnow_naive, server_default=text("CURRENT_TIMESTAMP(0)"))


class AppTag(db.Model):
    """应用标签关联模型"""
    __tablename__ = "app_tag"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_tag_id"),
        Index("app_tag_app_id_idx", "app_id"),
        Index("app_tag_tag_id_idx", "tag_id"),
        Index("app_tag_account_id_idx", "account_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    account_id = Column(UUID, nullable=False)  # 创建账号 ID
    app_id = Column(UUID, nullable=False)  # 应用 ID
    tag_id = Column(UUID, nullable=False)  # 标签 ID
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
        default=_utcnow_naive,
    )
    created_at = Column(DateTime, nullable=False, default=_utcnow_naive, server_default=text("CURRENT_TIMESTAMP(0)"))


class WorkflowTag(db.Model):
    """工作流标签关联模型"""
    __tablename__ = "workflow_tag"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_workflow_tag_id"),
        Index("workflow_tag_workflow_id_idx", "workflow_id"),
        Index("workflow_tag_tag_id_idx", "tag_id"),
        Index("workflow_tag_account_id_idx", "account_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    account_id = Column(UUID, nullable=False)  # 创建账号 ID
    workflow_id = Column(UUID, nullable=False)  # 工作流 ID
    tag_id = Column(UUID, nullable=False)  # 标签 ID
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
        default=_utcnow_naive,
    )
    created_at = Column(DateTime, nullable=False, default=_utcnow_naive, server_default=text("CURRENT_TIMESTAMP(0)"))
