from sqlalchemy import (
    Column,
    UUID,
    String,
    Text,
    Integer,
    DateTime,
    Boolean,
    Numeric,
    Float,
    text,
    PrimaryKeyConstraint, func, asc,
    Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import UTC, datetime

from internal.extension.database_extension import db


def _utcnow_naive() -> datetime:
    """返回无时区的 UTC 时间，兼容数据库 DateTime 列且避免 utcnow 退化警告。"""
    return datetime.now(UTC).replace(tzinfo=None)


class Conversation(db.Model):
    """交流会话模型"""
    __tablename__ = "conversation"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_conversation_id"),
        Index("conversation_app_id_idx", "app_id"),
        Index("conversation_created_by_idx", "created_by"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    app_id = Column(UUID, nullable=False)  # 关联应用id
    name = Column(String(255), nullable=False, server_default=text("''::character varying"))  # 会话名称
    summary = Column(Text, nullable=False, server_default=text("''::text"))  # 会话摘要/长期记忆
    is_pinned = Column(Boolean, nullable=False, server_default=text("false"))  # 是否置顶
    is_deleted = Column(Boolean, nullable=False, server_default=text("false"))  # 是否删除
    invoke_from = Column(String(255), nullable=False, server_default=text("''::character varying"))  # 调用来源
    created_by = Column(
        UUID,
        nullable=True,
    )  # 会话创建者，会随着invoke_from的差异记录不同的信息，其中web_app和debugger会记录账号id、service_api会记录终端用户id
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP(0)'),
        server_onupdate=text('CURRENT_TIMESTAMP(0)'),
        default=_utcnow_naive,
    )
    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP(0)'))

    @property
    def is_new(self) -> bool:
        """只读属性，用于判断该会话是否是第一次创建"""
        message_count = db.session.query(func.count(Message.id)).filter(
            Message.conversation_id == self.id,
        ).scalar()

        return False if message_count > 1 else True


class Message(db.Model):
    """交流消息模型"""
    __tablename__ = "message"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_message_id"),
        Index("message_app_id_idx", "app_id"),
        Index("message_conversation_id_idx", "conversation_id"),
        Index("message_created_by_idx", "created_by"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))

    # 消息关联的记录
    app_id = Column(UUID, nullable=False)  # 关联应用id
    conversation_id = Column(UUID, nullable=False)  # 关联会话id
    invoke_from = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
    )  # 调用来源，涵盖service_api、web_app、debugger等
    created_by = Column(UUID, nullable=False)  # 消息的创建来源，有可能是 OpenAgent 的用户，也有可能是开放 API 的终端用户

    # 消息关联的原始问题
    query = Column(Text, nullable=False, server_default=text("''::text"))  # 用户提问的原始query
    image_urls = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # 用户提问的图片URL列表信息
    message = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # 产生answer的消息列表
    message_token_count = Column(Integer, nullable=False, server_default=text("0"))  # 消息列表的token总数
    message_unit_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))  # 消息的单价
    message_price_unit = Column(Numeric(10, 4), nullable=False, server_default=text("0.0"))  # 消息的价格单位

    # 消息关联的答案信息
    answer = Column(Text, nullable=False, server_default=text("''::text"))  # Agent生成的消息答案
    answer_token_count = Column(Integer, nullable=False, server_default=text("0"))  # 消息答案的token数
    answer_unit_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))  # token的单位价格
    answer_price_unit = Column(Numeric(10, 4), nullable=False, server_default=text("0.0"))  # token的价格单位

    # 消息的相关统计信息
    latency = Column(Float, nullable=False, server_default=text("0.0"))  # 消息的总耗时
    is_deleted = Column(Boolean, nullable=False, server_default=text("false"))  # 软删除标记
    status = Column(String(255), nullable=False, server_default=text("''::character varying"))  # 消息的状态，涵盖正常、错误、停止
    error = Column(Text, nullable=False, server_default=text("''::text"))  # 发生错误时记录的信息
    total_token_count = Column(Integer, nullable=False, server_default=text("0"))  # 消耗的总token数，计算步骤的消耗
    total_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))  # 消耗的总价格，计算步骤的总消耗
    suggested_questions = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # AI生成的建议问题列表

    # 消息时间相关信息
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP(0)'),
        server_onupdate=text('CURRENT_TIMESTAMP(0)'),
        default=_utcnow_naive,
    )
    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP(0)'))

    # 智能体推理列表 创建表关联
    agent_thoughts = relationship(
        "MessageAgentThought",
        backref="msg",
        lazy="raise",
        passive_deletes="all",
        uselist=True,
        foreign_keys=[id],
        primaryjoin="MessageAgentThought.message_id == Message.id",
    )

    @property
    def conversation(self) -> Conversation:
        """只读属性，返回该消息对应的会话记录"""
        return db.session.query(Conversation).get(self.conversation_id)


class MessageAgentThought(db.Model):
    """智能体消息推理模型，用于记录Agent生成最终消息答案时"""
    __tablename__ = "message_agent_thought"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_message_agent_thought_id"),
        Index("message_agent_thought_app_id_idx", "app_id"),
        Index("message_agent_thought_conversation_id_idx", "conversation_id"),
        Index("message_agent_thought_message_id_idx", "message_id"),
        Index("message_agent_thought_created_by_idx", "created_by"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))

    # 推理步骤关联信息
    app_id = Column(UUID, nullable=False)  # 关联的应用id
    conversation_id = Column(UUID, nullable=False)  # 关联的会话id
    message_id = Column(UUID, nullable=False)  # 关联的消息id
    invoke_from = Column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
    )  # 调用来源，涵盖service_api、web_app、debugger等
    created_by = Column(UUID, nullable=False)  # 消息的创建来源，有可能是 OpenAgent 的用户，也有可能是开放 API 的终端用户

    # 该步骤在消息中执行的位置
    position = Column(Integer, nullable=False, server_default=text("0"))  # 推理观察的位置

    # 推理与观察，分别记录LLM和非LLM产生的消息
    event = Column(String(255), nullable=False, server_default=text("''::character varying"))  # 事件名称
    thought = Column(Text, nullable=False, server_default=text("''::text"))  # 推理内容(存储LLM生成的内容)
    observation = Column(Text, nullable=False, server_default=text("''::text"))  # 观察内容(存储知识库、工具等非LLM生成的内容，用于让LLM观察)

    # 工具相关，涵盖工具名称、输入，在调用工具时会生成
    tool = Column(Text, nullable=False, server_default=text("''::text"))  # 调用工具名称
    tool_input = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # LLM调用工具的输入，如果没有则为空字典

    # Agent推理观察步骤使用的消息列表(传递prompt消息内容)
    message = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # 该步骤调用LLM使用的提示消息
    message_token_count = Column(Integer, nullable=False, server_default=text("0"))  # 消息花费的token数
    message_unit_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))  # 单价，所有LLM的计算方式统一为CNY
    message_price_unit = Column(
        Numeric(10, 4),
        nullable=False,
        server_default=text("0"),
    )  # 价格单位，值为1000代表1000token对应的单价

    # LLM生成内容相关(生成内容)
    answer = Column(Text, nullable=False, server_default=text("''::text"))  # LLM生成的答案内容，值和thought保持一致
    answer_token_count = Column(Integer, nullable=False, server_default=text("0"))  # LLM生成答案消耗token数
    answer_unit_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))  # 单价，所有LLM的计算方式统一为CNY
    answer_price_unit = Column(
        Numeric(10, 4),
        nullable=False,
        server_default=text("0.0"),
    )  # 价格单位，值为1000代表1000token对应的单价

    # Agent推理观察统计相关
    total_token_count = Column(Integer, nullable=False, server_default=text("0"))  # 总消耗token
    total_price = Column(Numeric(10, 7), nullable=False, server_default=text("0.0"))  # 总消耗
    latency = Column(Float, nullable=False, server_default=text("0.0"))  # 推理观察步骤耗时

    # 时间相关信息
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP(0)'),
        server_onupdate=text('CURRENT_TIMESTAMP(0)'),
        default=_utcnow_naive,
    )  # 更新时间
    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP(0)'))  # 创建时间
