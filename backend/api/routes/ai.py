"""
AI command generation and processing endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.config.database import get_db
from backend.models.schemas import (
    AICommandRequest,
    AICommandResponse,
    AIExplainRequest,
    AIExplainResponse
)
from backend.services.ai_service import AIService
from backend.services.server_service import ServerService
from backend.core.exceptions import ServerNotFoundError, AIServiceError
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/generate-command", response_model=AICommandResponse)
async def generate_command(
    request: AICommandRequest,
    db: AsyncSession = Depends(get_db)
):
    """Generate shell command from natural language description"""
    ai_service = AIService()
    server_service = ServerService(db)
    
    try:
        # Get server context if server_id provided
        server_context = None
        if request.server_id:
            server = await server_service.get_server(request.server_id)
            if not server:
                raise ServerNotFoundError(request.server_id)
            server_context = await server_service.get_server_context(request.server_id)
        
        # Generate command using AI
        result = await ai_service.generate_command(
            prompt=request.prompt,
            server_context=server_context,
            reasoning_level=request.reasoning_level,
            os_type=request.os_type
        )
        
        logger.info(f"Generated command for prompt: '{request.prompt[:50]}...'")
        return result
        
    except (ServerNotFoundError, AIServiceError):
        raise
    except Exception as e:
        logger.error(f"Command generation failed: {e}")
        raise HTTPException(status_code=500, detail="Command generation failed")


@router.post("/explain-command", response_model=AIExplainResponse)
async def explain_command(
    request: AIExplainRequest
):
    """Explain what a shell command does"""
    ai_service = AIService()
    
    try:
        explanation = await ai_service.explain_command(
            command=request.command,
            context=request.context
        )
        
        logger.info(f"Explained command: {request.command[:50]}...")
        return explanation
        
    except AIServiceError:
        raise
    except Exception as e:
        logger.error(f"Command explanation failed: {e}")
        raise HTTPException(status_code=500, detail="Command explanation failed")


@router.post("/validate-command")
async def validate_command(
    command: str,
    server_id: str = None,
    db: AsyncSession = Depends(get_db)
):
    """Validate if a command is safe to execute"""
    ai_service = AIService()
    
    try:
        # Get server context if provided
        server_context = None
        if server_id:
            server_service = ServerService(db)
            server = await server_service.get_server(server_id)
            if server:
                server_context = await server_service.get_server_context(server_id)
        
        validation_result = await ai_service.validate_command(
            command=command,
            server_context=server_context
        )
        
        return {
            "command": command,
            "is_safe": validation_result.is_safe,
            "risk_level": validation_result.risk_level,
            "warnings": validation_result.warnings,
            "explanation": validation_result.explanation
        }
        
    except Exception as e:
        logger.error(f"Command validation failed: {e}")
        raise HTTPException(status_code=500, detail="Command validation failed")


@router.get("/models")
async def list_available_models():
    """List available AI models"""
    ai_service = AIService()
    
    try:
        models = await ai_service.list_models()
        return {
            "available_models": models,
            "current_model": ai_service.current_model
        }
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve model list")


@router.post("/switch-model")
async def switch_model(model_name: str):
    """Switch to a different AI model"""
    ai_service = AIService()
    
    try:
        success = await ai_service.switch_model(model_name)
        if success:
            return {"message": f"Switched to model: {model_name}"}
        else:
            raise HTTPException(status_code=400, detail=f"Model {model_name} not available")
    except Exception as e:
        logger.error(f"Failed to switch model: {e}")
        raise HTTPException(status_code=500, detail="Failed to switch model")