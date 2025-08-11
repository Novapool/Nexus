"""Add operation planning and execution tables

Revision ID: 002_add_operations
Revises: 001_initial
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '002_add_operations'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade():
    # Create operation_plans table
    op.create_table('operation_plans',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('user_prompt', sa.Text(), nullable=False),
        sa.Column('operation_type', sa.String(length=50), nullable=False),
        sa.Column('estimated_duration_seconds', sa.Integer(), nullable=True),
        sa.Column('risk_level', sa.String(length=20), nullable=False),
        sa.Column('requires_approval', sa.Boolean(), nullable=False),
        sa.Column('server_id', sa.String(), nullable=False),
        sa.Column('ai_model_used', sa.String(length=100), nullable=True),
        sa.Column('reasoning_level', sa.String(length=20), nullable=False),
        sa.Column('generation_time_seconds', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['server_id'], ['servers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create operation_steps table
    op.create_table('operation_steps',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('plan_id', sa.String(), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('command', sa.Text(), nullable=False),
        sa.Column('working_directory', sa.String(length=500), nullable=True),
        sa.Column('estimated_duration_seconds', sa.Integer(), nullable=True),
        sa.Column('risk_level', sa.String(length=20), nullable=False),
        sa.Column('requires_approval', sa.Boolean(), nullable=False),
        sa.Column('is_prerequisite', sa.Boolean(), nullable=False),
        sa.Column('is_rollback_step', sa.Boolean(), nullable=False),
        sa.Column('validation_command', sa.Text(), nullable=True),
        sa.Column('rollback_command', sa.Text(), nullable=True),
        sa.Column('rollback_description', sa.Text(), nullable=True),
        sa.Column('depends_on_steps', sa.JSON(), nullable=True),
        sa.Column('ai_reasoning', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['operation_plans.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create operation_executions table
    op.create_table('operation_executions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('plan_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('execution_mode', sa.String(length=20), nullable=False),
        sa.Column('auto_approve', sa.Boolean(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('current_step_order', sa.Integer(), nullable=True),
        sa.Column('total_steps', sa.Integer(), nullable=False),
        sa.Column('completed_steps', sa.Integer(), nullable=False),
        sa.Column('failed_steps', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('total_execution_time_seconds', sa.Float(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('rollback_performed', sa.Boolean(), nullable=False),
        sa.Column('rollback_success', sa.Boolean(), nullable=True),
        sa.Column('execution_log', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['operation_plans.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create operation_step_executions table
    op.create_table('operation_step_executions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('execution_id', sa.String(), nullable=False),
        sa.Column('step_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('command_executed', sa.Text(), nullable=True),
        sa.Column('working_directory', sa.String(length=500), nullable=True),
        sa.Column('stdout', sa.Text(), nullable=True),
        sa.Column('stderr', sa.Text(), nullable=True),
        sa.Column('exit_code', sa.Integer(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('execution_time_seconds', sa.Float(), nullable=True),
        sa.Column('validation_performed', sa.Boolean(), nullable=False),
        sa.Column('validation_success', sa.Boolean(), nullable=True),
        sa.Column('validation_output', sa.Text(), nullable=True),
        sa.Column('rollback_executed', sa.Boolean(), nullable=False),
        sa.Column('rollback_success', sa.Boolean(), nullable=True),
        sa.Column('rollback_output', sa.Text(), nullable=True),
        sa.Column('user_approved', sa.Boolean(), nullable=True),
        sa.Column('approval_timestamp', sa.DateTime(), nullable=True),
        sa.Column('user_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['execution_id'], ['operation_executions.id'], ),
        sa.ForeignKeyConstraint(['step_id'], ['operation_steps.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create operation_templates table
    op.create_table('operation_templates',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('operation_type', sa.String(length=50), nullable=False),
        sa.Column('template_data', sa.JSON(), nullable=False),
        sa.Column('os_compatibility', sa.JSON(), nullable=True),
        sa.Column('min_requirements', sa.JSON(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=False),
        sa.Column('success_rate', sa.Float(), nullable=True),
        sa.Column('avg_execution_time', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_verified', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # Create indexes for better performance
    op.create_index('idx_operation_plans_server_id', 'operation_plans', ['server_id'])
    op.create_index('idx_operation_plans_status', 'operation_plans', ['status'])
    op.create_index('idx_operation_plans_operation_type', 'operation_plans', ['operation_type'])
    op.create_index('idx_operation_steps_plan_id', 'operation_steps', ['plan_id'])
    op.create_index('idx_operation_steps_step_order', 'operation_steps', ['step_order'])
    op.create_index('idx_operation_executions_plan_id', 'operation_executions', ['plan_id'])
    op.create_index('idx_operation_executions_status', 'operation_executions', ['status'])
    op.create_index('idx_operation_step_executions_execution_id', 'operation_step_executions', ['execution_id'])
    op.create_index('idx_operation_step_executions_step_id', 'operation_step_executions', ['step_id'])
    op.create_index('idx_operation_templates_category', 'operation_templates', ['category'])
    op.create_index('idx_operation_templates_is_active', 'operation_templates', ['is_active'])


def downgrade():
    # Drop indexes
    op.drop_index('idx_operation_templates_is_active', table_name='operation_templates')
    op.drop_index('idx_operation_templates_category', table_name='operation_templates')
    op.drop_index('idx_operation_step_executions_step_id', table_name='operation_step_executions')
    op.drop_index('idx_operation_step_executions_execution_id', table_name='operation_step_executions')
    op.drop_index('idx_operation_executions_status', table_name='operation_executions')
    op.drop_index('idx_operation_executions_plan_id', table_name='operation_executions')
    op.drop_index('idx_operation_steps_step_order', table_name='operation_steps')
    op.drop_index('idx_operation_steps_plan_id', table_name='operation_steps')
    op.drop_index('idx_operation_plans_operation_type', table_name='operation_plans')
    op.drop_index('idx_operation_plans_status', table_name='operation_plans')
    op.drop_index('idx_operation_plans_server_id', table_name='operation_plans')
    
    # Drop tables
    op.drop_table('operation_templates')
    op.drop_table('operation_step_executions')
    op.drop_table('operation_executions')
    op.drop_table('operation_steps')
    op.drop_table('operation_plans')