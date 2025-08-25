"""Add terminal sessions support

Revision ID: 006_add_terminal_sessions
Revises: 005_add_system_profiling
Create Date: 2025-01-22 14:26:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '006_add_terminal_sessions'
down_revision = '005_add_system_profiling'
branch_labels = None
depends_on = None


def upgrade():
    """Add terminal sessions table with enhanced fields"""
    
    # Create terminal_sessions table with enhanced schema
    op.create_table('terminal_sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_token', sa.String(length=255), nullable=False),
        sa.Column('server_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('working_directory', sa.String(length=500), nullable=False, server_default='/home'),
        sa.Column('environment_vars', sa.Text(), nullable=True),
        sa.Column('terminal_size', sa.JSON(), nullable=True),  # {"cols": 80, "rows": 24}
        sa.Column('command_history', sa.JSON(), nullable=True),  # List of recent commands
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('connection_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_activity', sa.DateTime(), nullable=False),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('session_type', sa.String(length=50), nullable=False, server_default='shell'),  # shell, sftp, etc.
        sa.Column('session_metadata', sa.JSON(), nullable=True),  # Additional session metadata
        sa.ForeignKeyConstraint(['server_id'], ['servers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_token')
    )
    
    # Create indexes for better query performance
    op.create_index('ix_terminal_sessions_session_token', 'terminal_sessions', ['session_token'])
    op.create_index('ix_terminal_sessions_server_id', 'terminal_sessions', ['server_id'])
    op.create_index('ix_terminal_sessions_user_id', 'terminal_sessions', ['user_id'])
    op.create_index('ix_terminal_sessions_is_active', 'terminal_sessions', ['is_active'])
    op.create_index('ix_terminal_sessions_last_activity', 'terminal_sessions', ['last_activity'])
    
    # Create terminal_session_logs table for audit trail
    op.create_table('terminal_session_logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),  # command, output, error, connect, disconnect
        sa.Column('data', sa.Text(), nullable=True),
        sa.Column('log_metadata', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['terminal_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_terminal_session_logs_session_id', 'terminal_session_logs', ['session_id'])
    op.create_index('ix_terminal_session_logs_timestamp', 'terminal_session_logs', ['timestamp'])


def downgrade():
    """Remove terminal sessions support"""
    
    # Drop indexes
    op.drop_index('ix_terminal_session_logs_timestamp', table_name='terminal_session_logs')
    op.drop_index('ix_terminal_session_logs_session_id', table_name='terminal_session_logs')
    op.drop_index('ix_terminal_sessions_last_activity', table_name='terminal_sessions')
    op.drop_index('ix_terminal_sessions_is_active', table_name='terminal_sessions')
    op.drop_index('ix_terminal_sessions_user_id', table_name='terminal_sessions')
    op.drop_index('ix_terminal_sessions_server_id', table_name='terminal_sessions')
    op.drop_index('ix_terminal_sessions_session_token', table_name='terminal_sessions')
    
    # Drop tables
    op.drop_table('terminal_session_logs')
    op.drop_table('terminal_sessions')
