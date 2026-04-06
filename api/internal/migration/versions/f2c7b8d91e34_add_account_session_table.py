"""add account session table

Revision ID: f2c7b8d91e34
Revises: 7ed81995696f
Create Date: 2026-03-30 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2c7b8d91e34'
down_revision = '7ed81995696f'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'account_session',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('account_id', sa.UUID(), nullable=False),
        sa.Column('user_agent', sa.String(length=1024), nullable=False, server_default=sa.text("''::character varying")),
        sa.Column('last_login_ip', sa.String(length=255), nullable=False, server_default=sa.text("''::character varying")),
        sa.Column('last_active_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP(0)')),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP(0)')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP(0)')),
        sa.PrimaryKeyConstraint('id', name='pk_account_session_id'),
    )
    op.create_index('account_session_account_id_idx', 'account_session', ['account_id'])
    op.create_index('account_session_revoked_at_idx', 'account_session', ['revoked_at'])
    op.create_index('account_session_expires_at_idx', 'account_session', ['expires_at'])


def downgrade():
    op.drop_index('account_session_expires_at_idx', table_name='account_session')
    op.drop_index('account_session_revoked_at_idx', table_name='account_session')
    op.drop_index('account_session_account_id_idx', table_name='account_session')
    op.drop_table('account_session')
