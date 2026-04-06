from datetime import UTC, datetime
import uuid
from sqlalchemy import (
    Column,
    UUID,
    String,
    Text,
    Integer,
    DateTime,
    Boolean,
    PrimaryKeyConstraint,
    text,
    Index,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from internal.extension.database_extension import db
from internal.entity.app_entity import AppConfigType, DEFAULT_APP_CONFIG, AppStatus
from .conversation import Conversation
from internal.entity.conversation_entity import InvokeFrom
from internal.entity.platform_entity import WechatConfigStatus
from internal.lib.helper import generate_random_string
from .platform import WechatConfig


def _utcnow_naive() -> datetime:
    """返回无时区的 UTC 时间，兼容数据库 DateTime 列且避免 utcnow 退化警告。"""
    return datetime.now(UTC).replace(tzinfo=None)


class App(db.Model):
    """AI应用基础模型类"""
    __tablename__ = "app"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_id"),
        Index("app_account_id_idx", "account_id"),
        Index("app_is_public_idx", "is_public"),
        Index("app_tags_idx", "tags", postgresql_using="gin"),
        Index("app_like_count_idx", "like_count")
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    account_id = Column(UUID, ForeignKey('account.id'), nullable=False)  # 创建账号id
    app_config_id = Column(UUID, nullable=True)  # 发布配置id，当值为空时代表没有发布
    draft_app_config_id = Column(UUID, nullable=True)  # 关联的草稿配置id
    debug_conversation_id = Column(UUID, nullable=True)  # 应用调试会话id，为None则代表没有会话信息
    name = Column(String(255), nullable=False, server_default=text("''::character varying"))  # 应用名字
    icon = Column(String(255), nullable=False, server_default=text("''::character varying"))  # 应用图标
    description = Column(Text, nullable=False, server_default=text("''::text"))  # 应用描述
    token = Column(String(255), nullable=True, server_default=text("''::character varying"))  # 应用凭证
    status = Column(String(255), nullable=False, server_default=text("''::character varying"))  # 应用状态
    is_public = Column(Boolean, nullable=False, server_default=text("false"))  # 是否公开到广场
    tags = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # 应用标签列表
    published_at = Column(DateTime, nullable=True)  # 发布到广场的时间
    view_count = Column(Integer, nullable=False, server_default=text("0"))  # 浏览次数
    like_count = Column(Integer, nullable=False, server_default=text("0"))  # 点赞数
    fork_count = Column(Integer, nullable=False, server_default=text("0"))  # 被复制次数
    original_app_id = Column(UUID, nullable=True)  # 原始应用ID(用于Fork追踪)
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
        default=_utcnow_naive,
    )
    created_at = Column(DateTime, nullable=False, default=_utcnow_naive, server_default=text("CURRENT_TIMESTAMP(0)"))

    # 关系定义
    account = relationship("Account", foreign_keys=[account_id], lazy="joined")

    @property
    def app_config(self) -> "AppConfig":
        """只读属性 返回当前应用的运行配置"""
        if not self.app_config_id:
            return None
        return db.session.query(AppConfig).get(self.app_config_id)

    @property
    def draft_app_config(self) -> "AppConfigVersion":
        """只读属性 返回当前应用的草稿配置"""
        # 1.获取当前应用的草稿配置
        app_config_version = db.session.query(AppConfigVersion).filter(
            AppConfigVersion.app_id == self.id,
            AppConfigVersion.config_type == AppConfigType.DRAFT.value,
        ).one_or_none()

        # 2.检测当前配置是否存在 如果不存在则创建一个默认值
        if not app_config_version:
            app_config_version = AppConfigVersion(
                app_id=self.id,
                version=0,
                config_type=AppConfigType.DRAFT.value,
                **DEFAULT_APP_CONFIG,
            )
            db.session.add(app_config_version)
            db.session.commit()
        return app_config_version

    @property
    def debug_conversation(self) -> "Conversation":
        """获取应用的调试会话记录"""
        # 1.根据debug_conversation_id获取调试会话记录
        debug_conversation = None
        if self.debug_conversation_id is not None:
            debug_conversation = db.session.query(Conversation).filter(
                Conversation.id == self.debug_conversation_id,
                Conversation.invoke_from == InvokeFrom.DEBUGGER.value,
                Conversation.is_deleted == False,
            ).one_or_none()

        # 2.检测数据是否存在 如果不存在则创建
        if not self.debug_conversation_id or not debug_conversation:
            # 3.开启数据库自动提交上下文
            with db.auto_commit():
                # 4.创建应用调试会话记录并刷新会话id
                debug_conversation = Conversation(
                    app_id=self.id,
                    name="New Conversation",
                    invoke_from=InvokeFrom.DEBUGGER.value,
                    created_by=self.account_id,
                )
                db.session.add(debug_conversation)
                db.session.flush()

                # 5.更新当前记录的debug_conversation_id
                self.debug_conversation_id = debug_conversation.id

        return debug_conversation

    @property
    def token_with_default(self) -> str:
        """获取带有默认值的token"""
        # 1.判断状态是否为已发布
        if self.status != AppStatus.PUBLISHED.value:
            # 2.非发布的情况下需要清空数据 并提交更新
            if self.token is not None and self.token != "":
                self.token = None
                db.session.commit()
            return ""

        # 3.已发布状态需要判断token是否存在 不存在则生成
        if self.token is None or self.token == "":
            self.token = generate_random_string(16)
            db.session.commit()

        return self.token

    @property
    def wechat_config(self) -> "WechatConfig":
        """获取应用的微信发布配置信息"""
        # 1.获取当前应用的微信配置信息
        config = db.session.query(WechatConfig).filter(
            WechatConfig.app_id == self.id,
        ).one_or_none()

        # 2.检测配置是否存在，不存在则创建
        if not config:
            config = WechatConfig(app_id=self.id, status=WechatConfigStatus.UNCONFIGURED)
            db.session.add(config)
            db.session.commit()

        # 3.检查wechat_config只要app_id、app_secret和token有一个没填写则更新配置状态
        if config.status == WechatConfigStatus.CONFIGURED:
            if not config.wechat_app_id or not config.wechat_app_secret or not config.wechat_token:
                config.status = WechatConfigStatus.UNCONFIGURED
                db.session.commit()

        # 4.检测应用发布状态与配置信息是否匹配，不匹配则更新
        if self.status == AppStatus.DRAFT:
            # 5.草稿配置，检查WechatConfig是否设置为已发布，是的话则更新
            if config.status == WechatConfigStatus.CONFIGURED:
                config.status = WechatConfigStatus.UNCONFIGURED
                db.session.commit()
        elif self.status == AppStatus.PUBLISHED:
            # 6.已发布配置，检测WechatConfig如果填写了app_id、app_secret与token，则更新配置信息
            if config.status == WechatConfigStatus.UNCONFIGURED:
                if config.wechat_app_id and config.wechat_app_secret and config.wechat_token:
                    config.status = WechatConfigStatus.CONFIGURED
                    db.session.commit()

        return config


class AppConfig(db.Model):
    """应用配置模型"""
    __tablename__ = "app_config"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_config_id"),
        Index("app_config_app_id_idx", "app_id")
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))  # 配置id
    app_id = Column(UUID, nullable=False)  # 关联应用id
    model_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # 模型配置
    dialog_round = Column(Integer, nullable=False, server_default=text("0"))  # 鞋带上下文轮数
    preset_prompt = Column(Text, nullable=False, server_default=text("''::text"))  # 预设prompt
    tools = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # 应用关联工具列表
    workflows = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # 应用关联的工作流列表
    retrieval_config = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # 检索配置
    long_term_memory = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # 长期记忆配置
    opening_statement = Column(Text, nullable=False, server_default=text("''::text"))  # 开场白文案
    opening_questions = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # 开场白建议问题列表
    speech_to_text = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # 语音转文本配置
    text_to_speech = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # 文本转语音配置
    suggested_after_answer = Column(
        JSONB,
        nullable=False,
        server_default=text("'{\"enable\": true}'::jsonb"),
    )  # 回答后生成建议问题
    review_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # 审核配置
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
        default=_utcnow_naive,
    )
    created_at = Column(DateTime, nullable=False, default=_utcnow_naive, server_default=text("CURRENT_TIMESTAMP(0)"))


    @property
    def app_dataset_joins(self) -> list["AppDatasetJoin"]:
        """只读属性 获取配置的知识库关联记录"""
        return (
            db.session.query(AppDatasetJoin).filter(
                AppDatasetJoin.app_id == self.app_id,
            ).all()
        )


class AppConfigVersion(db.Model):
    """应用配置版本历史表，用于存储草稿配置+历史发布配置"""
    __tablename__ = "app_config_version"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_config_version_id"),
        Index("app_config_version_app_id_idx", "app_id")
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))  # 配置id
    app_id = Column(UUID, nullable=False)  # 关联应用id
    model_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # 模型配置
    dialog_round = Column(Integer, nullable=False, server_default=text("0"))  # 鞋带上下文轮数
    preset_prompt = Column(Text, nullable=False, server_default=text("''::text"))  # 人设与回复逻辑
    tools = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # 应用关联的工具列表
    workflows = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # 应用关联的工作流列表
    datasets = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # 应用关联的知识库列表
    retrieval_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # 检索配置
    long_term_memory = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # 长期记忆配置
    opening_statement = Column(Text, nullable=False, server_default=text("''::text"))  # 开场白文案
    opening_questions = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # 开场白建议问题列表
    speech_to_text = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # 语音转文本配置
    text_to_speech = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # 文本转语音配置
    suggested_after_answer = Column(
        JSONB,
        nullable=False,
        server_default=text("'{\"enable\": true}'::jsonb"),
    )  # 回答后生成建议问题
    review_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # 审核配置
    version = Column(Integer, nullable=False, server_default=text("0"))  # 发布版本号
    config_type = Column(String(255), nullable=False, server_default=text("''::character varying"))  # 配置类型
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
        default=_utcnow_naive,
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))


class AppDatasetJoin(db.Model):
    """应用知识库关联表模型"""
    __tablename__ = "app_dataset_join"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_dataset_join_id"),
        Index("app_dataset_join_app_id_idx", "app_id"),
        Index("app_dataset_join_dataset_id_idx", "dataset_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    app_id = Column(UUID, nullable=False)
    dataset_id = Column(UUID, nullable=False)
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        server_onupdate=text("CURRENT_TIMESTAMP(0)"),
        default=_utcnow_naive,
    )
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))


class AppLike(db.Model):
    """用户点赞应用关联表"""
    __tablename__ = "app_like"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_like_id"),
        Index("app_like_app_id_idx", "app_id"),
        Index("app_like_account_id_idx", "account_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    app_id = Column(UUID, nullable=False)
    account_id = Column(UUID, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))


class AppFavorite(db.Model):
    """用户收藏应用关联表"""
    __tablename__ = "app_favorite"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_favorite_id"),
        Index("app_favorite_app_id_idx", "app_id"),
        Index("app_favorite_account_id_idx", "account_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    app_id = Column(UUID, nullable=False)
    account_id = Column(UUID, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP(0)"))
