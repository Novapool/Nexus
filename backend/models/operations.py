"""
Database models for operation planning and execution
"""

from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship
from backend.config.database import Base
import datetime


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
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    
    # Relationships
    server = relationship("Server")
    steps = relationship("OperationStep", back_populates="plan", cascade="all, delete-orphan", order_by="OperationStep.step_order")
    executions = relationship("OperationExecution", back_populates="plan", cascade="all, delete-orphan")


class OperationStep(Base):
    """Individual steps within an operation plan"""
    __tablename__ = "operation_steps"
    
    id = Column(String, primary_key=True)
    plan_id = Column(String, ForeignKey("operation_plans.id"), nullable=False)
    
    # Step details
    step_order = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    command = Column(Text, nullable=False)
    working_directory = Column(String(500), nullable=True)
    
    # Step metadata
    estimated_duration_seconds = Column(Integer, nullable=True)
    risk_level = Column(String(20), nullable=False)
    requires_approval = Column(Boolean, default=False, nullable=False)
    is_prerequisite = Column(Boolean, default=False, nullable=False)
    is_rollback_step = Column(Boolean, default=False, nullable=False)
    
    # Validation and rollback
    validation_command = Column(Text, nullable=True)  # Command to verify step success
    rollback_command = Column(Text, nullable=True)   # Command to undo this step
    rollback_description = Column(Text, nullable=True)
    
    # Dependencies
    depends_on_steps = Column(JSON, nullable=True)  # List of step IDs this depends on
    
    # AI reasoning
    ai_reasoning = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    
    # Relationships
    plan = relationship("OperationPlan", back_populates="steps")
    step_executions = relationship("OperationStepExecution", back_populates="step", cascade="all, delete-orphan")


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
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    
    # Relationships
    plan = relationship("OperationPlan", back_populates="executions")
    step_executions = relationship("OperationStepExecution", back_populates="execution", cascade="all, delete-orphan")


class OperationStepExecution(Base):
    """Execution results for individual steps"""
    __tablename__ = "operation_step_executions"
    
    id = Column(String, primary_key=True)
    execution_id = Column(String, ForeignKey("operation_executions.id"), nullable=False)
    step_id = Column(String, ForeignKey("operation_steps.id"), nullable=False)
    
    # Execution details
    status = Column(String(50), default="pending", nullable=False)  # pending, running, completed, failed, skipped, requires_approval
    command_executed = Column(Text, nullable=True)  # Actual command that was run
    working_directory = Column(String(500), nullable=True)
    
    # Results
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    exit_code = Column(Integer, nullable=True)
    success = Column(Boolean, nullable=True)
    
    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    execution_time_seconds = Column(Float, nullable=True)
    
    # Validation
    validation_performed = Column(Boolean, default=False, nullable=False)
    validation_success = Column(Boolean, nullable=True)
    validation_output = Column(Text, nullable=True)
    
    # Rollback info
    rollback_executed = Column(Boolean, default=False, nullable=False)
    rollback_success = Column(Boolean, nullable=True)
    rollback_output = Column(Text, nullable=True)
    
    # User interaction
    user_approved = Column(Boolean, nullable=True)
    approval_timestamp = Column(DateTime, nullable=True)
    user_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    
    # Relationships
    execution = relationship("OperationExecution", back_populates="step_executions")
    step = relationship("OperationStep", back_populates="step_executions")


class OperationTemplate(Base):
    """Reusable operation templates"""
    __tablename__ = "operation_templates"
    
    id = Column(String, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=False)  # web_server, database, security, etc.
    
    # Template data
    operation_type = Column(String(50), nullable=False)
    template_data = Column(JSON, nullable=False)  # Serialized plan structure
    
    # Metadata
    os_compatibility = Column(JSON, nullable=True)  # List of compatible OS types
    min_requirements = Column(JSON, nullable=True)  # Minimum system requirements
    tags = Column(JSON, nullable=True)  # Search tags
    
    # Usage statistics
    usage_count = Column(Integer, default=0, nullable=False)
    success_rate = Column(Float, nullable=True)
    avg_execution_time = Column(Float, nullable=True)
    
    # Template status
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
