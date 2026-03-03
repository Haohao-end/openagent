from sqlalchemy import (
    Column,
    UUID,
    String,
    DateTime,
    Boolean,
    text,
    PrimaryKeyConstraint,
    Index
)

from internal.extension.database_extension import db
from .account import Account


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
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP(0)'),
        server_onupdate=text('CURRENT_TIMESTAMP(0)')
    )
    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP(0)'))

    @property
    def account(self) -> "Account":
        """只读属性，返回该秘钥归属的账号信息"""
        return db.session.query(Account).get(self.account_id)
