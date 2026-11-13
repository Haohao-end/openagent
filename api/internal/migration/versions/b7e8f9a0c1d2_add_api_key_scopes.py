"""Add optional scopes to API keys.

Revision ID: b7e8f9a0c1d2
Revises: d7a4c9e2f5b1
Create Date: 2026-11-13
"""

from alembic import op
import sqlalchemy as sa


revision = "b7e8f9a0c1d2"
down_revision = "d7a4c9e2f5b1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("api_key", sa.Column("scopes", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("api_key", "scopes")
