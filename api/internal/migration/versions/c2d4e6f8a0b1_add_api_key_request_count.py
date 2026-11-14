"""Add a lifetime request counter to API keys.

Revision ID: c2d4e6f8a0b1
Revises: b7e8f9a0c1d2
Create Date: 2026-11-15
"""

from alembic import op
import sqlalchemy as sa


revision = "c2d4e6f8a0b1"
down_revision = "b7e8f9a0c1d2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "api_key",
        sa.Column("request_count", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
    )


def downgrade():
    op.drop_column("api_key", "request_count")
