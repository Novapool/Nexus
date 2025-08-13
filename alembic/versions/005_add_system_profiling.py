"""Add system profiling columns

Revision ID: 005
Revises: 004
Create Date: 2025-01-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers
revision = '005_add_system_profiling'
down_revision = '004_add_performance_indexes'
branch_labels = None
depends_on = None


def upgrade():
    """Add system profiling columns to servers table"""
    
    # Add system_info JSON column to servers table
    op.add_column('servers', 
        sa.Column('system_info', sa.JSON, nullable=True)
    )
    
    # Add last_scan_date column
    op.add_column('servers',
        sa.Column('last_scan_date', sa.DateTime, nullable=True)
    )
    
    # Create server_profiles table
    op.create_table('server_profiles',
        sa.Column('id', sa.String, primary_key=True),
        sa.Column('server_id', sa.String, sa.ForeignKey('servers.id'), nullable=False, unique=True),
        sa.Column('os_family', sa.String(50), nullable=True),
        sa.Column('os_distribution', sa.String(100), nullable=True),
        sa.Column('os_version', sa.String(50), nullable=True),
        sa.Column('kernel_version', sa.String(100), nullable=True),
        sa.Column('architecture', sa.String(50), nullable=True),
        sa.Column('package_manager', sa.String(50), nullable=True),
        sa.Column('init_system', sa.String(50), nullable=True),
        sa.Column('last_scanned', sa.DateTime, nullable=True),
        sa.Column('scan_data', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False)
    )
    
    # Create server_hardware table
    op.create_table('server_hardware',
        sa.Column('id', sa.String, primary_key=True),
        sa.Column('server_id', sa.String, sa.ForeignKey('servers.id'), nullable=False, unique=True),
        sa.Column('cpu_count', sa.Integer, nullable=True),
        sa.Column('cpu_model', sa.String(255), nullable=True),
        sa.Column('memory_total_mb', sa.Integer, nullable=True),
        sa.Column('memory_available_mb', sa.Integer, nullable=True),
        sa.Column('swap_total_mb', sa.Integer, nullable=True),
        sa.Column('cpu_info', sa.JSON, nullable=True),
        sa.Column('memory_info', sa.JSON, nullable=True),
        sa.Column('storage_info', sa.JSON, nullable=True),
        sa.Column('gpu_info', sa.JSON, nullable=True),
        sa.Column('network_info', sa.JSON, nullable=True),
        sa.Column('last_updated', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False)
    )
    
    # Create server_services table
    op.create_table('server_services',
        sa.Column('id', sa.String, primary_key=True),
        sa.Column('server_id', sa.String, sa.ForeignKey('servers.id'), nullable=False, unique=True),
        sa.Column('has_docker', sa.Boolean, default=False, nullable=False),
        sa.Column('docker_version', sa.String(100), nullable=True),
        sa.Column('has_systemd', sa.Boolean, default=False, nullable=False),
        sa.Column('systemd_version', sa.String(100), nullable=True),
        sa.Column('has_sudo', sa.Boolean, default=False, nullable=False),
        sa.Column('firewall_type', sa.String(50), nullable=True),
        sa.Column('listening_ports', sa.JSON, nullable=True),
        sa.Column('running_services', sa.JSON, nullable=True),
        sa.Column('last_updated', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False)
    )
    
    # Create indexes for better performance
    op.create_index('idx_server_profiles_server_id', 'server_profiles', ['server_id'])
    op.create_index('idx_server_hardware_server_id', 'server_hardware', ['server_id'])
    op.create_index('idx_server_services_server_id', 'server_services', ['server_id'])


def downgrade():
    """Remove system profiling columns and tables"""
    
    # Drop indexes
    op.drop_index('idx_server_services_server_id', 'server_services')
    op.drop_index('idx_server_hardware_server_id', 'server_hardware')
    op.drop_index('idx_server_profiles_server_id', 'server_profiles')
    
    # Drop tables
    op.drop_table('server_services')
    op.drop_table('server_hardware')
    op.drop_table('server_profiles')
    
    # Remove columns from servers table
    op.drop_column('servers', 'last_scan_date')
    op.drop_column('servers', 'system_info')
