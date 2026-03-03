from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    UUID,
    String,
    DateTime,
    Boolean,
    text,
    PrimaryKeyConstraint,
    Index,
)

from internal.entity.conversation_entity import InvokeFrom
from internal.extension.database_extension import db
from .conversation import Conversation


def _utcnow_naive() -> datetime:
    """返回无时区的 UTC 时间，兼容数据库 DateTime 列且避免 utcnow 退化警告。"""
    return datetime.now(UTC).replace(tzinfo=None)


class WechatConfig(db.Model):
    """Agent微信配置信息"""
    __tablename__ = "wechat_config"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_wechat_config_id"),
        Index("wechat_config_app_id_idx", "app_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))  # 配置id
    app_id = Column(UUID, nullable=False)  # 配置关联应用id
    wechat_app_id = Column(String(255), nullable=True, server_default=text("''::character varying"))  # 微信公众号开发者id
    wechat_app_secret = Column(String(255), nullable=True, server_default=text("''::character varying"))  # 微信公众号开发者秘钥
    wechat_token = Column(String(255), nullable=True, server_default=text("''::character varying"))  # 微信公众号校验凭证
    status = Column(String(255), nullable=False, server_default=text("''::character varying"))  # 配置状态
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        onupdate=_utcnow_naive,
    )  # 更新时间
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))  # 创建时间


class WechatEndUser(db.Model):
    """微信公众号与终端用户标识关联表"""
    __tablename__ = "wechat_end_user"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_wechat_end_user_id"),
        Index("wechat_end_user_openid_app_id_idx", "openid", "app_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))  # 记录id
    openid = Column(String, nullable=False)  # 发送方账号，数据其实是openid(FromUserName/source)
    app_id = Column(UUID, nullable=False)  # 关联配置的应用id
    end_user_id = Column(UUID, nullable=False)  # 关联的终端用户id
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        onupdate=_utcnow_naive,
    )  # 更新时间
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))  # 创建时间

    @property
    def conversation(self) -> "Conversation":
        """获取微信终端用户的会话记录，如果没有则创建"""
        # 1.查询会话记录
        conversation = db.session.query(Conversation).filter(
            Conversation.created_by == self.end_user_id,
            Conversation.invoke_from == InvokeFrom.SERVICE_API,
            ~Conversation.is_deleted,
        ).one_or_none()

        # 2.判断会话是否存在，不存在则创建
        if not conversation:
            with db.auto_commit():
                conversation = Conversation(
                    app_id=self.app_id,
                    name="New Conversation",
                    invoke_from=InvokeFrom.SERVICE_API,
                    created_by=self.end_user_id,
                )
                db.session.add(conversation)

        return conversation


class WechatMessage(db.Model):
    """微信公众号消息模型，用于记录未推送的消息记录"""
    __tablename__ = "wechat_message"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_wechat_message_id"),
        Index("wechat_message_wechat_end_user_id_idx", "wechat_end_user_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))  # 记录id
    wechat_end_user_id = Column(UUID, nullable=False)  # 关联的微信终端用户id
    message_id = Column(UUID, nullable=False)  # 关联的消息id
    is_pushed = Column(Boolean, nullable=False, server_default=text("false"))  # 是否推送，默认为false表示未推送
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        onupdate=_utcnow_naive,
    )  # 更新时间
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))  # 创建时间
