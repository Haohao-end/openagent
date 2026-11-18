"""Add evaluation table.

Revision ID: 7fb49b181536
Revises: c2d4e6f8a0b1
Create Date: 2026-11-18 14:19:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '7fb49b181536'
down_revision = 'c2d4e6f8a0b1'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'evaluation',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('app_id', UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP(0)')),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP(0)'), onupdate=sa.text('CURRENT_TIMESTAMP(0)')),
    )
    op.create_index('evaluation_app_id_idx', 'evaluation', ['app_id'])

def downgrade():
    op.drop_index('evaluation_app_id_idx', table_name='evaluation')
    op.drop_table('evaluation')
