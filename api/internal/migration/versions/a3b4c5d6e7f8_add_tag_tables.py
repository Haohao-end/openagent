"""add tag, app_tag, workflow_tag tables

Revision ID: a3b4c5d6e7f8
Revises: 7ffffccfd101
Create Date: 2026-11-22 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "a3b4c5d6e7f8"
down_revision = "7ffffccfd101"
branch_labels = None
depends_on = None


def _utcnow_server_default():
    return sa.text("CURRENT_TIMESTAMP(0)")


def upgrade():
    op.create_table(
        "tag",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''::text"), nullable=True),
        sa.Column("tag_type", sa.String(length=50), server_default=sa.text("'custom'::character varying"), nullable=False),
        sa.Column("status", sa.String(length=50), server_default=sa.text("'active'::character varying"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=_utcnow_server_default(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=_utcnow_server_default(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_tag_id"),
    )
    op.create_index("tag_account_id_idx", "tag", ["account_id"], unique=False)
    op.create_index("tag_status_idx", "tag", ["status"], unique=False)
    op.create_index("tag_type_idx", "tag", ["tag_type"], unique=False)

    op.create_table(
        "app_tag",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("app_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=_utcnow_server_default(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=_utcnow_server_default(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_app_tag_id"),
    )
    op.create_index("app_tag_app_id_idx", "app_tag", ["app_id"], unique=False)
    op.create_index("app_tag_tag_id_idx", "app_tag", ["tag_id"], unique=False)
    op.create_index("app_tag_account_id_idx", "app_tag", ["account_id"], unique=False)

    op.create_table(
        "workflow_tag",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=_utcnow_server_default(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=_utcnow_server_default(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_tag_id"),
    )
    op.create_index("workflow_tag_workflow_id_idx", "workflow_tag", ["workflow_id"], unique=False)
    op.create_index("workflow_tag_tag_id_idx", "workflow_tag", ["tag_id"], unique=False)
    op.create_index("workflow_tag_account_id_idx", "workflow_tag", ["account_id"], unique=False)


def downgrade():
    op.drop_table("workflow_tag")
    op.drop_table("app_tag")
    op.drop_table("tag")
