"""Add unique constraint for MCP provider name per account.

Revision ID: 5493f0207784
Revises: c2d4e6f8a0b1
Create Date: 2026-11-18 13:28:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '5493f0207784'
down_revision = 'c2d4e6f8a0b1'
branch_labels = None
depends_on = None

def upgrade():
    op.create_unique_constraint('uq_mcp_provider_account_id_name', 'mcp_provider', ['account_id', 'name'])

def downgrade():
    op.drop_constraint('uq_mcp_provider_account_id_name', 'mcp_provider', type_='unique')
