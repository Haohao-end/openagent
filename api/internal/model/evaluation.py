from datetime import datetime
from uuid import UUID

from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from internal.extension.database_extension import db

class Evaluation(db.Model):
    __tablename__ = 'evaluation'
    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=db.text('uuid_generate_v4()'))
    app_id = Column(PG_UUID(as_uuid=True), nullable=False)
    name = Column(String(255), nullable=False)
    created_by = Column(PG_UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=db.text('CURRENT_TIMESTAMP(0)'))
    updated_at = Column(DateTime, nullable=False, server_default=db.text('CURRENT_TIMESTAMP(0)'), onupdate=db.text('CURRENT_TIMESTAMP(0)'))

    __table_args__ = (
        Index('evaluation_app_id_idx', 'app_id'),
    )
