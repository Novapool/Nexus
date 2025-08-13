"""
SQLAlchemy database models for Nexus
"""

from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship
from backend.config.database import Base
import datetime


class Server(Base):
    """Server configuration model"""
    __tablename__ = "servers"
    
    id = Column(String, primary_key=True)
    hostname = Column(String(255), nullable=False, index=True)
    username = Column(String(100), nullable=False)
    port = Column(Integer, default=22, nullable=False)
    description = Column(Text, nullable=True)
    os_type = Column(String(50), default="linux", nullable=False)
    
    # Encrypted authentication data
    password = Column(Text, nullable=True)  # Encrypted password
    private_key = Column(Text, nullable=True)  # Encrypted private key
    
    # Status and timestamps
    connection_status = Column(String(50), default="unknown")
    last_connected = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    
    # System profiling columns
    system_info = Column(JSON, nullable=True)  # Stores comprehensive scan results
    last_scan_date = Column(DateTime, nullable=True)
    
    # Relationships
    command_history = relationship("CommandHistory", back_populates="server", cascade="all, delete-orphan")
    profile = relationship("ServerProfile", back_populates="server", uselist=False, cascade="all, delete-orphan")
    hardware = relationship("ServerHardware", back_populates="server", uselist=False, cascade="all, delete-orphan")
    services = relationship("ServerServices", back_populates="server", uselist=False, cascade="all, delete-orphan")


class User(Base):
    """User model for authentication"""
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    command_history = relationship("CommandHistory", back_populates="user")


class CommandHistory(Base):
    """Command execution history"""
    __tablename__ = "command_history"
    
    id = Column(String, primary_key=True)
    command = Column(Text, nullable=False)
    output = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    exit_code = Column(Integer, nullable=True)
    execution_time = Column(Float, nullable=True)  # Seconds
    working_directory = Column(String(500), nullable=True)
    
    # AI-related fields
    is_ai_generated = Column(Boolean, default=False, nullable=False, index=True)
    ai_prompt = Column(Text, nullable=True)  # Original natural language prompt
    ai_reasoning = Column(Text, nullable=True)  # AI reasoning process
    risk_level = Column(String(20), nullable=True, index=True)
    
    # Relationships
    server_id = Column(String, ForeignKey("servers.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    executed_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    
    server = relationship("Server", back_populates="command_history")
    user = relationship("User", back_populates="command_history")


# Removed TerminalSession, AIModel, and ServerSnapshot classes
# These tables are dropped in the schema simplification


class AuditLog(Base):
    """Audit log for all system actions"""
    __tablename__ = "audit_logs"
    
    id = Column(String, primary_key=True)
    action = Column(String(100), nullable=False, index=True)  # CREATE_SERVER, EXECUTE_COMMAND, etc.
    resource_type = Column(String(50), nullable=False)  # server, command, user, etc.
    resource_id = Column(String(255), nullable=True)
    
    # Action details
    details = Column(Text, nullable=True)  # JSON details
    ip_address = Column(String(45), nullable=True)  # IPv4/IPv6
    user_agent = Column(String(500), nullable=True)
    
    # Result
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Relationships
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    performed_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    
    user = relationship("User")


class OperationPlan(Base):
    """Operation plan model for multi-step operations"""
    __tablename__ = "operation_plans"
    
    id = Column(String, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    user_prompt = Column(Text, nullable=False)  # Original user request
    
    # Plan metadata
    operation_type = Column(String(50), nullable=False, index=True)  # simple, complex, advanced
    estimated_duration_seconds = Column(Integer, nullable=True)
    risk_level = Column(String(20), nullable=False, index=True)  # safe, low, medium, high, dangerous
    requires_approval = Column(Boolean, default=False, nullable=False)
    
    # Target server
    server_id = Column(String, ForeignKey("servers.id"), nullable=False, index=True)
    
    # AI generation metadata
    ai_model_used = Column(String(100), nullable=True)
    reasoning_level = Column(String(20), nullable=False)
    generation_time_seconds = Column(Float, nullable=True)
    
    # Plan status
    status = Column(String(50), default="draft", nullable=False, index=True)  # draft, approved, executing, completed, failed, rolled_back
    
    # JSON fields to replace separate tables
    steps_json = Column(JSON, nullable=True)  # Consolidated steps data
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    
    # Relationships
    server = relationship("Server")
    executions = relationship("OperationExecution", back_populates="plan", cascade="all, delete-orphan")


# OperationStep class removed - data consolidated into OperationPlan.steps_json


class OperationExecution(Base):
    """Execution instances of operation plans"""
    __tablename__ = "operation_executions"
    
    id = Column(String, primary_key=True)
    plan_id = Column(String, ForeignKey("operation_plans.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    
    # Execution metadata
    execution_mode = Column(String(20), nullable=False)  # dry_run, safe, cautious, full
    auto_approve = Column(Boolean, default=False, nullable=False)
    
    # Status tracking
    status = Column(String(50), default="pending", nullable=False, index=True)  # pending, running, paused, completed, failed, rolled_back, cancelled
    current_step_order = Column(Integer, nullable=True)
    total_steps = Column(Integer, nullable=False)
    completed_steps = Column(Integer, default=0, nullable=False)
    failed_steps = Column(Integer, default=0, nullable=False)
    
    # Timing
    started_at = Column(DateTime, nullable=True, index=True)
    completed_at = Column(DateTime, nullable=True)
    total_execution_time_seconds = Column(Float, nullable=True)
    
    # Results
    success = Column(Boolean, nullable=True)
    error_message = Column(Text, nullable=True)
    rollback_performed = Column(Boolean, default=False, nullable=False)
    rollback_success = Column(Boolean, nullable=True)
    
    # Execution log
    execution_log = Column(JSON, nullable=True)  # Detailed log of execution events
    
    # JSON fields to replace separate tables
    step_results_json = Column(JSON, nullable=True)  # Consolidated step execution results
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    
    # Relationships
    plan = relationship("OperationPlan", back_populates="executions")


# OperationStepExecution and OperationTemplate classes removed
# Data consolidated into OperationExecution.step_results_json
# Templates are not essential for core functionality


class ServerProfile(Base):
    """Server system profile information"""
    __tablename__ = "server_profiles"
    
    id = Column(String, primary_key=True)
    server_id = Column(String, ForeignKey("servers.id"), nullable=False, unique=True, index=True)
    
    # OS Information
    os_family = Column(String(50), nullable=True)
    os_distribution = Column(String(100), nullable=True)
    os_version = Column(String(50), nullable=True)
    kernel_version = Column(String(100), nullable=True)
    architecture = Column(String(50), nullable=True)
    package_manager = Column(String(50), nullable=True)
    init_system = Column(String(50), nullable=True)
    
    # Scan metadata
    last_scanned = Column(DateTime, nullable=True)
    scan_data = Column(JSON, nullable=True)  # Complete scan results
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    
    # Relationships
    server = relationship("Server", back_populates="profile")


class ServerHardware(Base):
    """Server hardware information"""
    __tablename__ = "server_hardware"
    
    id = Column(String, primary_key=True)
    server_id = Column(String, ForeignKey("servers.id"), nullable=False, unique=True, index=True)
    
    # CPU Information
    cpu_count = Column(Integer, nullable=True)
    cpu_model = Column(String(255), nullable=True)
    
    # Memory Information
    memory_total_mb = Column(Integer, nullable=True)
    memory_available_mb = Column(Integer, nullable=True)
    swap_total_mb = Column(Integer, nullable=True)
    
    # JSON fields for detailed info
    cpu_info = Column(JSON, nullable=True)
    memory_info = Column(JSON, nullable=True)
    storage_info = Column(JSON, nullable=True)  # Array of storage devices
    gpu_info = Column(JSON, nullable=True)  # Array of GPU devices
    network_info = Column(JSON, nullable=True)  # Array of network interfaces
    
    # Metadata
    last_updated = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    
    # Relationships
    server = relationship("Server", back_populates="hardware")


class ServerServices(Base):
    """Server services and capabilities"""
    __tablename__ = "server_services"
    
    id = Column(String, primary_key=True)
    server_id = Column(String, ForeignKey("servers.id"), nullable=False, unique=True, index=True)
    
    # Service availability
    has_docker = Column(Boolean, default=False, nullable=False)
    docker_version = Column(String(100), nullable=True)
    has_systemd = Column(Boolean, default=False, nullable=False)
    systemd_version = Column(String(100), nullable=True)
    has_sudo = Column(Boolean, default=False, nullable=False)
    firewall_type = Column(String(50), nullable=True)
    
    # JSON fields for detailed info
    listening_ports = Column(JSON, nullable=True)  # Array of listening ports
    running_services = Column(JSON, nullable=True)  # Array of running services
    
    # Metadata
    last_updated = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    
    # Relationships
    server = relationship("Server", back_populates="services")
