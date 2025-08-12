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
    
    # Relationships
    command_history = relationship("CommandHistory", back_populates="server", cascade="all, delete-orphan")


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
    is_ai_generated = Column(Boolean, default=False, nullable=False)
    ai_prompt = Column(Text, nullable=True)  # Original natural language prompt
    ai_reasoning = Column(Text, nullable=True)  # AI reasoning process
    risk_level = Column(String(20), nullable=True)
    
    # Relationships
    server_id = Column(String, ForeignKey("servers.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    executed_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    
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
    operation_type = Column(String(50), nullable=False)  # simple, complex, advanced
    estimated_duration_seconds = Column(Integer, nullable=True)
    risk_level = Column(String(20), nullable=False)  # safe, low, medium, high, dangerous
    requires_approval = Column(Boolean, default=False, nullable=False)
    
    # Target server
    server_id = Column(String, ForeignKey("servers.id"), nullable=False)
    
    # AI generation metadata
    ai_model_used = Column(String(100), nullable=True)
    reasoning_level = Column(String(20), nullable=False)
    generation_time_seconds = Column(Float, nullable=True)
    
    # Plan status
    status = Column(String(50), default="draft", nullable=False)  # draft, approved, executing, completed, failed, rolled_back
    
    # JSON fields to replace separate tables
    steps_json = Column(JSON, nullable=True)  # Consolidated steps data
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    
    # Relationships
    server = relationship("Server")
    executions = relationship("OperationExecution", back_populates="plan", cascade="all, delete-orphan")


# OperationStep class removed - data consolidated into OperationPlan.steps_json


class OperationExecution(Base):
    """Execution instances of operation plans"""
    __tablename__ = "operation_executions"
    
    id = Column(String, primary_key=True)
    plan_id = Column(String, ForeignKey("operation_plans.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    
    # Execution metadata
    execution_mode = Column(String(20), nullable=False)  # dry_run, safe, cautious, full
    auto_approve = Column(Boolean, default=False, nullable=False)
    
    # Status tracking
    status = Column(String(50), default="pending", nullable=False)  # pending, running, paused, completed, failed, rolled_back, cancelled
    current_step_order = Column(Integer, nullable=True)
    total_steps = Column(Integer, nullable=False)
    completed_steps = Column(Integer, default=0, nullable=False)
    failed_steps = Column(Integer, default=0, nullable=False)
    
    # Timing
    started_at = Column(DateTime, nullable=True)
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
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    
    # Relationships
    plan = relationship("OperationPlan", back_populates="executions")


# OperationStepExecution and OperationTemplate classes removed
# Data consolidated into OperationExecution.step_results_json
# Templates are not essential for core functionality
