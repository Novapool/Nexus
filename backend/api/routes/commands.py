"""
Simple command execution routes without complex operation planning
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List, Optional
import logging

from backend.config.database import get_db
from backend.services.command_service import CommandService
from backend.models.schemas import SafetyLevel
from backend.core.exceptions import ServiceError, ValidationError, ExternalServiceError
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models
class ExecuteNaturalRequest(BaseModel):
    prompt: str
    server_id: str
    safety_level: SafetyLevel = SafetyLevel.CAUTIOUS
    user_id: Optional[str] = None


class ExecuteDirectRequest(BaseModel):
    command: str
    server_id: str
    explanation: Optional[str] = ""
    safety_level: SafetyLevel = SafetyLevel.CAUTIOUS
    user_id: Optional[str] = None


class ValidateCommandRequest(BaseModel):
    command: str
    server_id: Optional[str] = None


class CommandSuggestionsRequest(BaseModel):
    prompt: str
    server_id: Optional[str] = None


class CommandResponse(BaseModel):
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


class CommandSuggestion(BaseModel):
    command: str
    explanation: str
    risk_level: str


class CommandHistoryItem(BaseModel):
    id: str
    command: str
    output: Optional[str]
    error: Optional[str]
    exit_code: Optional[int]
    execution_time: Optional[float]
    executed_at: str
    is_ai_generated: bool
    ai_prompt: Optional[str]
    risk_level: Optional[str]


@router.post("/execute-natural", response_model=CommandResponse)
async def execute_natural_command(
    request: ExecuteNaturalRequest,
    db: AsyncSession = Depends(get_db)
):
    """Execute natural language command with AI translation"""
    
    try:
        command_service = CommandService(db)
        result = await command_service.execute_natural_command(
            prompt=request.prompt,
            server_id=request.server_id,
            safety_level=request.safety_level,
            user_id=request.user_id
        )
        
        return CommandResponse(**result)
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail={
            "error": "VALIDATION_ERROR",
            "message": e.message,
            "field": e.field if hasattr(e, 'field') else None
        })
    except ExternalServiceError as e:
        raise HTTPException(status_code=502, detail={
            "error": f"{e.service.upper()}_ERROR" if hasattr(e, 'service') else "EXTERNAL_SERVICE_ERROR",
            "message": e.message,
            "service": e.service if hasattr(e, 'service') else "unknown"
        })
    except ServiceError as e:
        raise HTTPException(status_code=500, detail={
            "error": "SERVICE_ERROR",
            "message": e.message
        })
    except Exception as e:
        logger.error(f"Unexpected error in execute_natural_command: {e}")
        raise HTTPException(status_code=500, detail={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred"
        })


@router.post("/execute-direct", response_model=CommandResponse)
async def execute_direct_command(
    request: ExecuteDirectRequest,
    db: AsyncSession = Depends(get_db)
):
    """Execute a direct command with validation"""
    
    try:
        command_service = CommandService(db)
        result = await command_service.validate_and_execute(
            command=request.command,
            server_id=request.server_id,
            explanation=request.explanation,
            safety_level=request.safety_level,
            user_id=request.user_id
        )
        
        return CommandResponse(**result)
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail={
            "error": "VALIDATION_ERROR",
            "message": e.message,
            "field": e.field if hasattr(e, 'field') else None
        })
    except ExternalServiceError as e:
        raise HTTPException(status_code=502, detail={
            "error": f"{e.service.upper()}_ERROR" if hasattr(e, 'service') else "EXTERNAL_SERVICE_ERROR",
            "message": e.message,
            "service": e.service if hasattr(e, 'service') else "unknown"
        })
    except ServiceError as e:
        raise HTTPException(status_code=500, detail={
            "error": "SERVICE_ERROR",
            "message": e.message
        })
    except Exception as e:
        logger.error(f"Unexpected error in execute_direct_command: {e}")
        raise HTTPException(status_code=500, detail={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred"
        })


@router.post("/validate")
async def validate_command(
    request: ValidateCommandRequest,
    db: AsyncSession = Depends(get_db)
):
    """Validate command safety without executing"""
    
    try:
        command_service = CommandService(db)
        
        # Get server context if server_id provided
        server_context = None
        if request.server_id:
            server = await command_service._get_server(request.server_id)
            if server:
                server_context = {
                    "hostname": server.hostname,
                    "os_type": server.os_type,
                    "username": server.username
                }
        
        validation = await command_service.ai_service.validate_command(
            command=request.command,
            server_context=server_context
        )
        
        return {
            "command": request.command,
            "is_safe": validation.is_safe,
            "risk_level": validation.risk_level.value,
            "warnings": validation.warnings,
            "explanation": validation.explanation,
            "suggested_fixes": validation.suggested_fixes
        }
        
    except ServiceError as e:
        raise HTTPException(status_code=500, detail={
            "error": "SERVICE_ERROR",
            "message": e.message
        })
    except Exception as e:
        logger.error(f"Unexpected error in validate_command: {e}")
        raise HTTPException(status_code=500, detail={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred"
        })


@router.post("/suggestions", response_model=List[CommandSuggestion])
async def get_command_suggestions(
    request: CommandSuggestionsRequest,
    db: AsyncSession = Depends(get_db)
):
    """Get command suggestions for ambiguous requests"""
    
    try:
        command_service = CommandService(db)
        
        # Get server context if server_id provided
        server_context = None
        if request.server_id:
            server = await command_service._get_server(request.server_id)
            if server:
                server_context = {
                    "hostname": server.hostname,
                    "os_type": server.os_type,
                    "username": server.username
                }
        
        suggestions = await command_service.get_command_suggestions(
            prompt=request.prompt,
            server_context=server_context
        )
        
        return [CommandSuggestion(**suggestion) for suggestion in suggestions]
        
    except ServiceError as e:
        raise HTTPException(status_code=500, detail={
            "error": "SERVICE_ERROR",
            "message": e.message
        })
    except Exception as e:
        logger.error(f"Unexpected error in get_command_suggestions: {e}")
        raise HTTPException(status_code=500, detail={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred"
        })


@router.get("/history/{server_id}", response_model=List[CommandHistoryItem])
async def get_command_history(
    server_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    user_id: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db)
):
    """Get simple command history for a server"""
    
    try:
        command_service = CommandService(db)
        history = await command_service.get_command_history(
            server_id=server_id,
            limit=limit,
            user_id=user_id
        )
        
        return [CommandHistoryItem(**item) for item in history]
        
    except ServiceError as e:
        raise HTTPException(status_code=500, detail={
            "error": "SERVICE_ERROR",
            "message": e.message
        })
    except Exception as e:
        logger.error(f"Unexpected error in get_command_history: {e}")
        raise HTTPException(status_code=500, detail={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred"
        })


@router.get("/safety-levels")
async def get_safety_levels():
    """Get available safety levels and their descriptions"""
    
    return {
        "safety_levels": [
            {
                "level": "paranoid",
                "description": "Only allow completely safe commands (read-only operations)",
                "max_risk": "safe"
            },
            {
                "level": "safe",
                "description": "Allow low-risk commands (basic file operations)",
                "max_risk": "low"
            },
            {
                "level": "cautious",
                "description": "Allow medium-risk commands (system modifications)",
                "max_risk": "medium"
            },
            {
                "level": "normal",
                "description": "Allow high-risk commands (significant system changes)",
                "max_risk": "high"
            },
            {
                "level": "permissive",
                "description": "Allow all commands including dangerous ones",
                "max_risk": "dangerous"
            }
        ]
    }


@router.get("/status")
async def get_command_service_status():
    """Get command service status and configuration"""
    
    from backend.config.settings import get_settings
    settings = get_settings()
    
    return {
        "service": "command_service",
        "status": "active",
        "ai_enabled": settings.enable_ai,
        "default_safety_level": settings.ssh_safety_level,
        "ssh_timeout": settings.ssh_timeout,
        "max_connections": settings.ssh_max_connections
    }
