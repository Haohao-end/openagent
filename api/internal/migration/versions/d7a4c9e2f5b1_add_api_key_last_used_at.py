"""add last-used timestamp for API keys

Revision ID: d7a4c9e2f5b1
Revises: c4a6f12d8b30
Create Date: 2026-11-13

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d7a4c9e2f5b1"
down_revision = "c4a6f12d8b30"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("api_key", sa.Column("last_used_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("api_key", "last_used_at")
