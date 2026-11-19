"""add feedback table

Revision ID: 7ffffccfd101
Revises: 5493f0207784, 6a1b2c3d4e5f
Create Date: 2026-11-19 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "7ffffccfd101"
down_revision = ("5493f0207784", "6a1b2c3d4e5f")
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("app_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_type", sa.String(length=255), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP(0)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP(0)"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_feedback_id")
    )
    op.create_index("feedback_app_id_idx", "feedback", ["app_id"], unique=False)
    op.create_index("feedback_target_id_idx", "feedback", ["target_id"], unique=False)
    op.create_index("feedback_created_by_idx", "feedback", ["created_by"], unique=False)


def downgrade():
    op.drop_table("feedback")
