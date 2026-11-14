from sqlalchemy import (
    Column,
    UUID,
    String,
    DateTime,
    Boolean,
    BigInteger,
    JSON,
    text,
    PrimaryKeyConstraint,
    Index
)
from datetime import UTC, datetime

from internal.extension.database_extension import db
from .account import Account

API_KEY_SCOPE_OPENAPI_CHAT = "openapi:chat"
API_KEY_SUPPORTED_SCOPES = frozenset({API_KEY_SCOPE_OPENAPI_CHAT})


def _utcnow_naive() -> datetime:
    """返回无时区的 UTC 时间，兼容数据库 DateTime 列且避免 utcnow 退化警告。"""
    return datetime.now(UTC).replace(tzinfo=None)
class ApiKey(db.Model):
    """API秘钥模型"""
    __tablename__ = "api_key"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_api_key_id"),
        Index("api_key_account_id_idx", "account_id"),
        Index("api_key_api_key_idx", "api_key"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))  # 记录id
    account_id = Column(UUID, nullable=False)  # 关联账号id
    api_key = Column(String(255), nullable=False, server_default=text("''::character varying"))  # API Key 哈希值
    is_active = Column(Boolean, nullable=False, server_default=text('false'))  # 是否激活，为true时可以使用
    remark = Column(String(255), nullable=False, server_default=text("''::character varying"))  # 备注信息
    expires_at = Column(DateTime, nullable=True)  # 可选的失效时间（UTC）
    last_used_at = Column(DateTime, nullable=True)  # 最近一次通过认证的时间（UTC）
    request_count = Column(BigInteger, nullable=False, server_default=text("0"))
    # NULL keeps existing keys unrestricted; new keys receive an explicit default scope.
    scopes = Column(JSON, nullable=True)
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP(0)'),
        server_onupdate=text('CURRENT_TIMESTAMP(0)'),
        default=_utcnow_naive,
    )
    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP(0)'))

    @property
    def account(self) -> "Account":
        """只读属性，返回该秘钥归属的账号信息"""
        return db.session.query(Account).get(self.account_id)
