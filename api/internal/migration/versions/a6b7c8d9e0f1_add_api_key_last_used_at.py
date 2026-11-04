"""add API key last-used timestamp

Revision ID: a6b7c8d9e0f1
Revises: f9a1b2c3d4e5
Create Date: 2026-10-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a6b7c8d9e0f1'
down_revision = 'f9a1b2c3d4e5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('api_key', sa.Column('last_used_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('api_key', 'last_used_at')
