"""add optional API key expiration

Revision ID: c4a6f12d8b30
Revises: f9a1b2c3d4e5
Create Date: 2026-11-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c4a6f12d8b30"
down_revision = "f9a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("api_key", sa.Column("expires_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("api_key", "expires_at")
