from sqlalchemy import (
    Column,
    UUID,
    String,
    Integer,
    DateTime,
    PrimaryKeyConstraint,
    text,
    Index
)

from internal.extension.database_extension import db


class UploadFile(db.Model):
    """上传文件模型"""
    __tablename__ = "upload_file"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_upload_file_id"),
        Index("upload_file_account_id", "account_id"),
    )

    id = Column(UUID, nullable=False, server_default=text('uuid_generate_v4()'))
    account_id = Column(UUID, nullable=False)
    name = Column(String(255), nullable=False, server_default=text("''::character varying"))
    key = Column(String(255), nullable=False, server_default=text("''::character varying"))
    size = Column(Integer, nullable=False, server_default=text('0'))
    extension = Column(String(255), nullable=False, server_default=text("''::character varying"))
    mime_type = Column(String(255), nullable=False, server_default=text("''::character varying"))
    hash = Column(String(255), nullable=False, server_default=text("''::character varying"))
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP(0)'),
        server_onupdate=text('CURRENT_TIMESTAMP(0)'),
    )
    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP(0)'))
