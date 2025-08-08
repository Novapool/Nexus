"""
SQLAlchemy database models for Nexus
"""

from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, ForeignKey, Float
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
    terminal_sessions = relationship("TerminalSession", back_populates="server", cascade="all, delete-orphan")


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
    terminal_sessions = relationship("TerminalSession", back_populates="user")


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


class TerminalSession(Base):
    """Active terminal sessions"""
    __tablename__ = "terminal_sessions"
    
    id = Column(String, primary_key=True)
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    working_directory = Column(String(500), default="/", nullable=False)
    environment_vars = Column(Text, nullable=True)  # JSON string
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Connection details
    connection_id = Column(String(255), nullable=True)  # SSH connection identifier
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    last_activity = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    closed_at = Column(DateTime, nullable=True)
    
    # Relationships
    server_id = Column(String, ForeignKey("servers.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    server = relationship("Server", back_populates="terminal_sessions")
    user = relationship("User", back_populates="terminal_sessions")


class AIModel(Base):
    """AI model configurations"""
    __tablename__ = "ai_models"
    
    id = Column(String, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    provider = Column(String(50), nullable=False)  # ollama, transformers, etc.
    model_path = Column(String(500), nullable=True)
    config = Column(Text, nullable=True)  # JSON configuration
    
    is_active = Column(Boolean, default=False, nullable=False)
    is_available = Column(Boolean, default=False, nullable=False)
    
    # Performance metrics
    avg_response_time = Column(Float, nullable=True)
    total_requests = Column(Integer, default=0, nullable=False)
    success_rate = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)


class ServerSnapshot(Base):
    """Periodic server state snapshots"""
    __tablename__ = "server_snapshots"
    
    id = Column(String, primary_key=True)
    server_id = Column(String, ForeignKey("servers.id"), nullable=False)
    
    # System information
    hostname = Column(String(255), nullable=True)
    os_version = Column(String(100), nullable=True)
    kernel_version = Column(String(100), nullable=True)
    architecture = Column(String(50), nullable=True)
    
    # Performance metrics
    cpu_percent = Column(Float, nullable=True)
    memory_percent = Column(Float, nullable=True)
    disk_percent = Column(Float, nullable=True)
    load_average = Column(String(100), nullable=True)  # "1.0,1.2,1.1"
    uptime_seconds = Column(Integer, nullable=True)
    
    # Software information
    installed_packages = Column(Text, nullable=True)  # JSON array
    running_services = Column(Text, nullable=True)  # JSON array
    open_ports = Column(Text, nullable=True)  # JSON array
    
    # Security
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    last_package_update = Column(DateTime, nullable=True)
    
    captured_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    
    # Relationship
    server = relationship("Server")


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