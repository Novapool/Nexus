"""Add performance indexes

Revision ID: 004_add_performance_indexes
Revises: 003_simplify_schema
Create Date: 2025-01-08 21:29:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_add_performance_indexes'
down_revision = '003_simplify_schema'
branch_labels = None
depends_on = None


def upgrade():
    """Add performance indexes to improve query speed"""
    
    # Add indexes to command_history table for better query performance
    op.create_index('ix_command_history_is_ai_generated', 'command_history', ['is_ai_generated'])
    op.create_index('ix_command_history_risk_level', 'command_history', ['risk_level'])
    op.create_index('ix_command_history_server_id', 'command_history', ['server_id'])
    op.create_index('ix_command_history_user_id', 'command_history', ['user_id'])
    op.create_index('ix_command_history_executed_at', 'command_history', ['executed_at'])
    
    # Add indexes to operation_plans table
    op.create_index('ix_operation_plans_operation_type', 'operation_plans', ['operation_type'])
    op.create_index('ix_operation_plans_risk_level', 'operation_plans', ['risk_level'])
    op.create_index('ix_operation_plans_server_id', 'operation_plans', ['server_id'])
    op.create_index('ix_operation_plans_status', 'operation_plans', ['status'])
    op.create_index('ix_operation_plans_created_at', 'operation_plans', ['created_at'])
    
    # Add indexes to operation_executions table
    op.create_index('ix_operation_executions_plan_id', 'operation_executions', ['plan_id'])
    op.create_index('ix_operation_executions_user_id', 'operation_executions', ['user_id'])
    op.create_index('ix_operation_executions_status', 'operation_executions', ['status'])
    op.create_index('ix_operation_executions_started_at', 'operation_executions', ['started_at'])
    op.create_index('ix_operation_executions_created_at', 'operation_executions', ['created_at'])


def downgrade():
    """Remove performance indexes"""
    
    # Remove indexes from operation_executions table
    op.drop_index('ix_operation_executions_created_at', 'operation_executions')
    op.drop_index('ix_operation_executions_started_at', 'operation_executions')
    op.drop_index('ix_operation_executions_status', 'operation_executions')
    op.drop_index('ix_operation_executions_user_id', 'operation_executions')
    op.drop_index('ix_operation_executions_plan_id', 'operation_executions')
    
    # Remove indexes from operation_plans table
    op.drop_index('ix_operation_plans_created_at', 'operation_plans')
    op.drop_index('ix_operation_plans_status', 'operation_plans')
    op.drop_index('ix_operation_plans_server_id', 'operation_plans')
    op.drop_index('ix_operation_plans_risk_level', 'operation_plans')
    op.drop_index('ix_operation_plans_operation_type', 'operation_plans')
    
    # Remove indexes from command_history table
    op.drop_index('ix_command_history_executed_at', 'command_history')
    op.drop_index('ix_command_history_user_id', 'command_history')
    op.drop_index('ix_command_history_server_id', 'command_history')
    op.drop_index('ix_command_history_risk_level', 'command_history')
    op.drop_index('ix_command_history_is_ai_generated', 'command_history')
