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


class SafetyLevel(str, Enum):
    """Safety levels for command execution"""
    PARANOID = "paranoid"    # Only allow completely safe commands
    SAFE = "safe"           # Allow low-risk commands
    CAUTIOUS = "cautious"   # Allow medium-risk commands (default)
    NORMAL = "normal"       # Allow high-risk commands
    PERMISSIVE = "permissive"  # Allow all commands including dangerous ones


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


class CommandResponse(BaseModel):
    """Schema for command execution responses"""
    success: bool
    command: str
    explanation: str
    output: Optional[str] = None
    error: Optional[str] = None
    execution_time: float
    safety_level: str
    warnings: List[str] = []
    exit_code: Optional[int] = None
    requires_approval: Optional[bool] = None


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


# Operation Planning Schemas
class OperationType(str, Enum):
    """Types of operations"""
    SIMPLE = "simple"        # 3-5 steps, low complexity
    COMPLEX = "complex"      # 6-12 steps, medium complexity  
    ADVANCED = "advanced"    # 13+ steps, high complexity


class ExecutionMode(str, Enum):
    """Execution safety modes"""
    DRY_RUN = "dry_run"     # Validate only, don't execute
    SAFE = "safe"           # Execute safe commands only
    CAUTIOUS = "cautious"   # Execute with confirmation for risky commands
    FULL = "full"           # Execute all validated commands


class ExecutionStatus(str, Enum):
    """Execution status values"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    """Step execution status values"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    REQUIRES_APPROVAL = "requires_approval"


class OperationPlanRequest(BaseModel):
    """Request to generate an operation plan"""
    prompt: str = Field(..., min_length=1, max_length=2000, description="Natural language description of the operation")
    server_id: str = Field(..., description="Target server ID")
    reasoning_level: ReasoningLevel = Field(default=ReasoningLevel.MEDIUM, description="AI reasoning level")
    operation_type: Optional[OperationType] = Field(None, description="Hint for operation complexity")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context for planning")
    save_as_template: Optional[bool] = Field(False, description="Save as reusable template")
    template_name: Optional[str] = Field(None, description="Name for template if saving")


class OperationStepSchema(BaseModel):
    """Schema for operation step"""
    id: Optional[str] = None
    step_order: int = Field(..., ge=1, description="Order of execution")
    name: str = Field(..., min_length=1, max_length=255, description="Step name")
    description: Optional[str] = Field(None, description="Step description")
    command: str = Field(..., min_length=1, description="Command to execute")
    working_directory: Optional[str] = Field(None, description="Working directory for command")
    
    # Metadata
    estimated_duration_seconds: Optional[int] = Field(None, ge=0, description="Estimated execution time")
    risk_level: RiskLevel = Field(..., description="Risk assessment for this step")
    requires_approval: bool = Field(default=False, description="Requires user approval")
    is_prerequisite: bool = Field(default=False, description="Is a prerequisite check")
    is_rollback_step: bool = Field(default=False, description="Is part of rollback procedure")
    
    # Validation and rollback
    validation_command: Optional[str] = Field(None, description="Command to verify step success")
    rollback_command: Optional[str] = Field(None, description="Command to undo this step")
    rollback_description: Optional[str] = Field(None, description="Description of rollback action")
    
    # Dependencies
    depends_on_steps: List[int] = Field(default=[], description="Step orders this depends on")
    
    # AI reasoning
    ai_reasoning: Optional[str] = Field(None, description="AI reasoning for this step")


class OperationPlanSchema(BaseModel):
    """Schema for complete operation plan"""
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=255, description="Plan name")
    description: Optional[str] = Field(None, description="Plan description")
    user_prompt: str = Field(..., description="Original user request")
    
    # Plan metadata
    operation_type: OperationType = Field(..., description="Operation complexity type")
    estimated_duration_seconds: Optional[int] = Field(None, ge=0, description="Total estimated time")
    risk_level: RiskLevel = Field(..., description="Overall risk assessment")
    requires_approval: bool = Field(default=False, description="Plan requires approval")
    
    # Target server
    server_id: str = Field(..., description="Target server ID")
    
    # AI metadata
    ai_model_used: Optional[str] = Field(None, description="AI model used for generation")
    reasoning_level: ReasoningLevel = Field(..., description="Reasoning level used")
    generation_time_seconds: Optional[float] = Field(None, ge=0, description="Time to generate plan")
    
    # Steps
    steps: List[OperationStepSchema] = Field(..., min_length=1, description="Operation steps")
    prerequisite_steps: List[OperationStepSchema] = Field(default=[], description="Prerequisite checks")
    rollback_steps: List[OperationStepSchema] = Field(default=[], description="Rollback procedure")
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @validator('steps')
    def validate_step_order(cls, v):
        """Ensure step orders are sequential and unique"""
        orders = [step.step_order for step in v]
        if len(orders) != len(set(orders)):
            raise ValueError("Step orders must be unique")
        if orders != sorted(orders):
            raise ValueError("Step orders must be sequential")
        return v


class OperationPlanResponse(BaseModel):
    """Response schema for operation plan"""
    id: str
    name: str = Field(..., min_length=1, max_length=255, description="Plan name")
    description: Optional[str] = Field(None, description="Plan description")
    user_prompt: str = Field(..., description="Original user request")
    
    # Plan metadata
    operation_type: OperationType = Field(..., description="Operation complexity type")
    estimated_duration_seconds: Optional[int] = Field(None, ge=0, description="Total estimated time")
    risk_level: RiskLevel = Field(..., description="Overall risk assessment")
    requires_approval: bool = Field(default=False, description="Plan requires approval")
    
    # Target server
    server_id: str = Field(..., description="Target server ID")
    
    # AI metadata
    ai_model_used: Optional[str] = Field(None, description="AI model used for generation")
    reasoning_level: ReasoningLevel = Field(..., description="Reasoning level used")
    generation_time_seconds: Optional[float] = Field(None, ge=0, description="Time to generate plan")
    
    # Steps
    steps: List[OperationStepSchema] = Field(..., min_length=1, description="Operation steps")
    prerequisite_steps: List[OperationStepSchema] = Field(default=[], description="Prerequisite checks")
    rollback_steps: List[OperationStepSchema] = Field(default=[], description="Rollback procedure")
    
    # Response-specific fields
    status: str = Field(..., description="Plan status")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Execution Schemas
class OperationExecutionRequest(BaseModel):
    """Request to execute an operation plan"""
    plan_id: str = Field(..., description="Operation plan ID to execute")
    execution_mode: ExecutionMode = Field(default=ExecutionMode.CAUTIOUS, description="Execution safety mode")
    auto_approve: bool = Field(default=False, description="Automatically approve low-risk steps")
    start_from_step: Optional[int] = Field(None, ge=1, description="Step to start from (for resuming)")
    execute_only_steps: Optional[List[int]] = Field(None, description="Execute only specific steps")
    timeout_seconds: Optional[int] = Field(default=3600, ge=1, description="Overall execution timeout")
    
    @validator('execute_only_steps')
    def validate_execute_only_steps(cls, v):
        """Ensure step numbers are valid"""
        if v is not None and len(v) == 0:
            raise ValueError("execute_only_steps cannot be empty list")
        return v


class OperationStepExecutionSchema(BaseModel):
    """Schema for step execution result"""
    id: Optional[str] = None
    step_id: str = Field(..., description="Step ID")
    step_order: int = Field(..., description="Step order")
    step_name: str = Field(..., description="Step name")
    
    # Execution details
    status: StepStatus = Field(..., description="Execution status")
    command_executed: Optional[str] = Field(None, description="Actual command executed")
    working_directory: Optional[str] = Field(None, description="Working directory used")
    
    # Results
    stdout: Optional[str] = Field(None, description="Command output")
    stderr: Optional[str] = Field(None, description="Command errors")
    exit_code: Optional[int] = Field(None, description="Command exit code")
    success: Optional[bool] = Field(None, description="Step success")
    
    # Timing
    started_at: Optional[datetime] = Field(None, description="Step start time")
    completed_at: Optional[datetime] = Field(None, description="Step completion time")
    execution_time_seconds: Optional[float] = Field(None, description="Step execution time")
    
    # Validation
    validation_performed: bool = Field(default=False, description="Was validation performed")
    validation_success: Optional[bool] = Field(None, description="Validation result")
    validation_output: Optional[str] = Field(None, description="Validation command output")
    
    # User interaction
    user_approved: Optional[bool] = Field(None, description="User approval status")
    approval_timestamp: Optional[datetime] = Field(None, description="Approval timestamp")
    user_notes: Optional[str] = Field(None, description="User notes")


class OperationExecutionSchema(BaseModel):
    """Schema for operation execution"""
    id: Optional[str] = None
    plan_id: str = Field(..., description="Operation plan ID")
    
    # Execution metadata
    execution_mode: ExecutionMode = Field(..., description="Execution mode")
    auto_approve: bool = Field(default=False, description="Auto-approve setting")
    
    # Status tracking
    status: ExecutionStatus = Field(..., description="Execution status")
    current_step_order: Optional[int] = Field(None, description="Currently executing step")
    total_steps: int = Field(..., ge=1, description="Total number of steps")
    completed_steps: int = Field(default=0, ge=0, description="Completed steps")
    failed_steps: int = Field(default=0, ge=0, description="Failed steps")
    
    # Timing
    started_at: Optional[datetime] = Field(None, description="Execution start time")
    completed_at: Optional[datetime] = Field(None, description="Execution completion time")
    total_execution_time_seconds: Optional[float] = Field(None, description="Total execution time")
    
    # Results
    success: Optional[bool] = Field(None, description="Overall success")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    rollback_performed: bool = Field(default=False, description="Was rollback performed")
    rollback_success: Optional[bool] = Field(None, description="Rollback success")
    
    # Step results
    step_executions: List[OperationStepExecutionSchema] = Field(default=[], description="Step execution results")
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class OperationExecutionResponse(BaseModel):
    """Response schema for operation execution"""
    id: str
    plan_id: str = Field(..., description="Operation plan ID")
    
    # Execution metadata
    execution_mode: ExecutionMode = Field(..., description="Execution mode")
    auto_approve: bool = Field(default=False, description="Auto-approve setting")
    
    # Status tracking
    status: ExecutionStatus = Field(..., description="Execution status")
    current_step_order: Optional[int] = Field(None, description="Currently executing step")
    total_steps: int = Field(..., ge=1, description="Total number of steps")
    completed_steps: int = Field(default=0, ge=0, description="Completed steps")
    failed_steps: int = Field(default=0, ge=0, description="Failed steps")
    
    # Timing
    started_at: Optional[datetime] = Field(None, description="Execution start time")
    completed_at: Optional[datetime] = Field(None, description="Execution completion time")
    total_execution_time_seconds: Optional[float] = Field(None, description="Total execution time")
    
    # Results
    success: Optional[bool] = Field(None, description="Overall success")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    rollback_performed: bool = Field(default=False, description="Was rollback performed")
    rollback_success: Optional[bool] = Field(None, description="Rollback success")
    
    # Step results
    step_executions: List[OperationStepExecutionSchema] = Field(default=[], description="Step execution results")
    
    # Response-specific fields
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Template Schemas
class OperationTemplateSchema(BaseModel):
    """Schema for operation template"""
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=255, description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    category: str = Field(..., min_length=1, max_length=100, description="Template category")
    
    # Template data
    operation_type: OperationType = Field(..., description="Operation type")
    template_data: Dict[str, Any] = Field(..., description="Template plan structure")
    
    # Metadata
    os_compatibility: List[OSType] = Field(default=[], description="Compatible OS types")
    min_requirements: Optional[Dict[str, Any]] = Field(None, description="Minimum requirements")
    tags: List[str] = Field(default=[], description="Search tags")
    
    # Usage statistics
    usage_count: int = Field(default=0, ge=0, description="Usage count")
    success_rate: Optional[float] = Field(None, ge=0, le=1, description="Success rate")
    avg_execution_time: Optional[float] = Field(None, ge=0, description="Average execution time")
    
    # Status
    is_active: bool = Field(default=True, description="Template is active")
    is_verified: bool = Field(default=False, description="Template is verified")
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class OperationTemplateResponse(BaseModel):
    """Response schema for operation template"""
    id: str
    name: str = Field(..., min_length=1, max_length=255, description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    category: str = Field(..., min_length=1, max_length=100, description="Template category")
    
    # Template data
    operation_type: OperationType = Field(..., description="Operation type")
    template_data: Dict[str, Any] = Field(..., description="Template plan structure")
    
    # Metadata
    os_compatibility: List[OSType] = Field(default=[], description="Compatible OS types")
    min_requirements: Optional[Dict[str, Any]] = Field(None, description="Minimum requirements")
    tags: List[str] = Field(default=[], description="Search tags")
    
    # Usage statistics
    usage_count: int = Field(default=0, ge=0, description="Usage count")
    success_rate: Optional[float] = Field(None, ge=0, le=1, description="Success rate")
    avg_execution_time: Optional[float] = Field(None, ge=0, description="Average execution time")
    
    # Status
    is_active: bool = Field(default=True, description="Template is active")
    is_verified: bool = Field(default=False, description="Template is verified")
    
    # Response-specific fields
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Progress and Status Schemas
class ExecutionProgress(BaseModel):
    """Real-time execution progress"""
    execution_id: str
    status: ExecutionStatus
    current_step: Optional[int] = None
    current_step_name: Optional[str] = None
    progress_percentage: float = Field(..., ge=0, le=100)
    completed_steps: int
    total_steps: int
    elapsed_time_seconds: float
    estimated_remaining_seconds: Optional[float] = None
    last_output: Optional[str] = None


class StepApprovalRequest(BaseModel):
    """Request for step approval"""
    execution_id: str
    step_id: str
    approved: bool
    user_notes: Optional[str] = Field(None, max_length=1000)


# Validation and Error Schemas
class PlanValidationResult(BaseModel):
    """Plan validation result"""
    is_valid: bool
    warnings: List[str] = []
    errors: List[str] = []
    risk_assessment: RiskLevel
    estimated_duration: Optional[int] = None
    required_approvals: List[int] = []  # Step orders requiring approval


class OperationError(BaseModel):
    """Operation error details"""
    error_type: str
    message: str
    step_order: Optional[int] = None
    recovery_suggestions: List[str] = []
    rollback_available: bool = True
