"""
Pydantic schemas for request/response validation
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class OSType(str, Enum):
    """Operating system types"""
    LINUX = "linux"
    UBUNTU = "ubuntu"
    DEBIAN = "debian"
    CENTOS = "centos"
    RHEL = "rhel"
    ALPINE = "alpine"
    MACOS = "macos"
    UNKNOWN = "unknown"


class ReasoningLevel(str, Enum):
    """AI reasoning levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskLevel(str, Enum):
    """Command risk levels"""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    DANGEROUS = "dangerous"


# Server Schemas
class ServerBase(BaseModel):
    """Base server schema"""
    hostname: str = Field(..., min_length=1, max_length=255)
    username: str = Field(..., min_length=1, max_length=100)
    port: int = Field(default=22, ge=1, le=65535)
    description: Optional[str] = Field(None, max_length=500)
    os_type: Optional[OSType] = OSType.LINUX


class ServerCreate(ServerBase):
    """Schema for creating a new server"""
    password: Optional[str] = Field(None, min_length=1)
    private_key: Optional[str] = Field(None, min_length=10)
    
    @validator('private_key', 'password')
    def validate_auth_method(cls, v, values):
        """Ensure at least one authentication method is provided"""
        if not v and not values.get('password') and not values.get('private_key'):
            raise ValueError('Either password or private_key must be provided')
        return v


class ServerUpdate(BaseModel):
    """Schema for updating server configuration"""
    hostname: Optional[str] = Field(None, min_length=1, max_length=255)
    username: Optional[str] = Field(None, min_length=1, max_length=100)
    port: Optional[int] = Field(None, ge=1, le=65535)
    description: Optional[str] = Field(None, max_length=500)
    password: Optional[str] = Field(None, min_length=1)
    private_key: Optional[str] = Field(None, min_length=10)
    os_type: Optional[OSType] = None


class ServerResponse(ServerBase):
    """Schema for server responses"""
    id: str
    created_at: datetime
    updated_at: datetime
    last_connected: Optional[datetime] = None
    connection_status: Optional[str] = "unknown"
    
    class Config:
        from_attributes = True


class ServerListResponse(BaseModel):
    """Schema for paginated server list"""
    servers: List[ServerResponse]
    total: int
    skip: int
    limit: int


# AI Schemas
class AICommandRequest(BaseModel):
    """Schema for AI command generation requests"""
    prompt: str = Field(..., min_length=1, max_length=1000)
    server_id: Optional[str] = None
    reasoning_level: ReasoningLevel = ReasoningLevel.MEDIUM
    os_type: Optional[OSType] = OSType.LINUX
    context: Optional[Dict[str, Any]] = None


class AICommandResponse(BaseModel):
    """Schema for AI command generation responses"""
    command: str
    explanation: str
    is_safe: bool
    risk_level: RiskLevel
    warnings: List[str] = []
    reasoning: Optional[str] = None
    alternatives: List[str] = []


class AIExplainRequest(BaseModel):
    """Schema for command explanation requests"""
    command: str = Field(..., min_length=1, max_length=1000)
    context: Optional[str] = None


class AIExplainResponse(BaseModel):
    """Schema for command explanation responses"""
    command: str
    explanation: str
    breakdown: List[Dict[str, str]] = []
    warnings: List[str] = []
    examples: List[str] = []


class CommandValidationResult(BaseModel):
    """Schema for command validation results"""
    is_safe: bool
    risk_level: RiskLevel
    warnings: List[str] = []
    explanation: str
    suggested_fixes: List[str] = []


# Terminal Schemas
class TerminalCommandRequest(BaseModel):
    """Schema for terminal command execution"""
    command: str = Field(..., min_length=1, max_length=1000)
    server_id: str
    working_directory: Optional[str] = None
    timeout: Optional[int] = Field(default=30, ge=1, le=300)


class TerminalCommandResponse(BaseModel):
    """Schema for terminal command responses"""
    command: str
    output: str
    error: Optional[str] = None
    exit_code: int
    execution_time: float
    working_directory: str


# Authentication Schemas
class UserLogin(BaseModel):
    """Schema for user login"""
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    """Schema for user responses"""
    id: str
    username: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    """Schema for authentication tokens"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# System Schemas
class SystemInfo(BaseModel):
    """Schema for system information"""
    hostname: str
    os_type: OSType
    os_version: str
    architecture: str
    cpu_count: int
    memory_total: int
    disk_usage: Dict[str, Any]
    uptime: int
    load_average: List[float] = []


class ServerStats(BaseModel):
    """Schema for server statistics"""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_io: Dict[str, int]
    processes: int
    timestamp: datetime


# Audit/History Schemas
class CommandHistory(BaseModel):
    """Schema for command history"""
    id: str
    command: str
    server_id: str
    user_id: str
    executed_at: datetime
    exit_code: int
    output_preview: str
    is_ai_generated: bool
    
    class Config:
        from_attributes = True


class CommandHistoryResponse(BaseModel):
    """Schema for command history responses"""
    history: List[CommandHistory]
    total: int
    skip: int
    limit: int