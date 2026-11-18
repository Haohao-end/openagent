from datetime import datetime
from uuid import UUID

from sqlalchemy import Column, String, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from internal.extension.database_extension import db

class EvaluationCase(db.Model):
    __tablename__ = 'evaluation_case'
    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=db.text('uuid_generate_v4()'))
    evaluation_id = Column(PG_UUID(as_uuid=True), ForeignKey('evaluation.id'), nullable=False)
    query = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=db.text('CURRENT_TIMESTAMP(0)'))
    updated_at = Column(DateTime, nullable=False, server_default=db.text('CURRENT_TIMESTAMP(0)'), onupdate=db.text('CURRENT_TIMESTAMP(0)'))

    __table_args__ = (
        Index('evaluation_case_evaluation_id_idx', 'evaluation_id'),
    )
