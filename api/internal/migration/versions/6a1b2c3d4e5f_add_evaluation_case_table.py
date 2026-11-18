"""Add evaluation_case table.

Revision ID: 6a1b2c3d4e5f
Revises: 7fb49b181536
Create Date: 2026-11-18 14:19:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '6a1b2c3d4e5f'
down_revision = '7fb49b181536'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'evaluation_case',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('evaluation_id', UUID(as_uuid=True), sa.ForeignKey('evaluation.id'), nullable=False),
        sa.Column('query', sa.Text, nullable=False),
        sa.Column('answer', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP(0)')),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP(0)'), onupdate=sa.text('CURRENT_TIMESTAMP(0)')),
    )
    op.create_index('evaluation_case_evaluation_id_idx', 'evaluation_case', ['evaluation_id'])

def downgrade():
    op.drop_index('evaluation_case_evaluation_id_idx', table_name='evaluation_case')
    op.drop_table('evaluation_case')
