from sqlalchemy import (
    Column,
    UUID,
    String,
    Text,
    Boolean,
    DateTime,
    Float,
    Integer,
    text,
    PrimaryKeyConstraint,
    Index,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from datetime import UTC, datetime

from internal.extension.database_extension import db


def _utcnow_naive() -> datetime:
    """返回无时区的 UTC 时间，兼容数据库 DateTime 列且避免 utcnow 退化警告。"""
    return datetime.now(UTC).replace(tzinfo=None)
class Workflow(db.Model):
    """工作流模型"""
    __tablename__ = "workflow"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_workflow_id"),
        Index("workflow_account_id_idx", "account_id"),
        Index("workflow_tool_call_name_idx", "tool_call_name"),
        Index("workflow_is_public_idx", "is_public"),
        Index("workflow_tags_idx", "tags", postgresql_using="gin"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    account_id = Column(UUID, ForeignKey('account.id'), nullable=False)  # 创建账号id
    name = Column(String(255), nullable=False, server_default=text("''::character varying"))  # 工作流名字
    tool_call_name = Column(String(255), nullable=False, server_default=text("''::character varying"))  # 工作流工具调用名字
    icon = Column(String(255), nullable=False, server_default=text("''::character varying"))  # 工作流图标
    description = Column(Text, nullable=False, server_default=text("''::text"))  # 应用描述
    graph = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # 运行时配置
    draft_graph = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # 草稿图配置
    is_debug_passed = Column(Boolean, nullable=False, server_default=text("false"))  # 是否调试通过
    status = Column(String(255), nullable=False, server_default=text("''::character varying"))  # 工作流状态
    is_public = Column(Boolean, nullable=False, server_default=text("false"))  # 是否公开到广场
    tags = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # 工作流标签列表
    view_count = Column(Integer, nullable=False, server_default=text("0"))  # 浏览次数
    like_count = Column(Integer, nullable=False, server_default=text("0"))  # 点赞数
    fork_count = Column(Integer, nullable=False, server_default=text("0"))  # 被Fork次数
    original_workflow_id = Column(UUID, nullable=True)  # 原始工作流ID（用于Fork追踪）
    published_at = Column(DateTime, nullable=True)  # 发布时间
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
        default=_utcnow_naive,
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))

    # 关系定义
    account = relationship("Account", foreign_keys=[account_id], lazy="joined")


class WorkflowResult(db.Model):
    """工作流存储结果模型"""
    __tablename__ = "workflow_result"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_workflow_result_id"),
        Index("workflow_result_app_id_idx", "app_id"),
        Index("workflow_result_account_id_idx", "account_id"),
        Index("workflow_result_workflow_id_idx", "workflow_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))  # 结果id
    app_id = Column(UUID, nullable=True)  # 工作流调用的应用id，如果为空则代表非应用调用
    account_id = Column(UUID, nullable=False)  # 创建账号id
    workflow_id = Column(UUID, nullable=False)  # 结果关联的工作流id
    graph = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # 运行时配置
    state = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # 工作流最终状态
    latency = Column(Float, nullable=False, server_default=text("0.0"))  # 消息的总耗时
    status = Column(String(255), nullable=False, server_default=text("''::character varying"))  # 运行状态
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
        default=_utcnow_naive,
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))


class WorkflowLike(db.Model):
    """用户点赞工作流关联表"""
    __tablename__ = "workflow_like"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_workflow_like_id"),
        Index("workflow_like_workflow_id_idx", "workflow_id"),
        Index("workflow_like_account_id_idx", "account_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    workflow_id = Column(UUID, nullable=False)
    account_id = Column(UUID, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))


class WorkflowFavorite(db.Model):
    """用户收藏工作流关联表"""
    __tablename__ = "workflow_favorite"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_workflow_favorite_id"),
        Index("workflow_favorite_workflow_id_idx", "workflow_id"),
        Index("workflow_favorite_account_id_idx", "account_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    workflow_id = Column(UUID, nullable=False)
    account_id = Column(UUID, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))
