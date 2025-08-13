"""
Simple command execution service without complex operation planning
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from backend.config.settings import get_settings
from backend.models.database import CommandHistory, Server
from backend.models.schemas import SafetyLevel, CommandResponse
from backend.services.ai_service import AIService
from backend.core.ssh_manager import ssh_factory
from backend.core.exceptions import ServiceError, ValidationError, ExternalServiceError
from backend.core.safety_validator import SafetyValidator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)


class CommandService:
    """Simple command execution without complex planning"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.ai_service = AIService()
    
    async def execute_natural_command(
        self, 
        prompt: str, 
        server_id: str,
        safety_level: SafetyLevel = SafetyLevel.CAUTIOUS,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute natural language command with AI translation"""
        
        try:
            # Get server context
            server = await self._get_server(server_id)
            if not server:
                raise ValidationError(f"Server {server_id} not found", "server_id")
            
            # Generate command using AI
            logger.info(f"Generating command for prompt: {prompt}")
            try:
                ai_response = await self.ai_service.generate_command(
                    prompt=prompt,
                    server_context={
                        "hostname": server.hostname,
                        "os_type": server.os_type,
                        "username": server.username
                    }
                )
                
                # Validate that we got a proper command
                if not ai_response.command or ai_response.command.startswith('{'):
                    logger.error(f"AI returned malformed command: {ai_response.command}")
                    return {
                        "success": False,
                        "command": "echo 'AI parsing error'",
                        "explanation": "AI returned malformed response",
                        "error": "AI response parsing failed",
                        "execution_time": 0.0,
                        "safety_level": safety_level.value,
                        "warnings": ["AI response parsing failed"]
                    }
                    
            except Exception as ai_error:
                logger.error(f"AI command generation failed: {ai_error}")
                return {
                    "success": False,
                    "command": "echo 'AI service error'",
                    "explanation": f"AI service error: {str(ai_error)}",
                    "error": f"Failed to generate command: {str(ai_error)}",
                    "execution_time": 0.0,
                    "safety_level": safety_level.value,
                    "warnings": ["AI service unavailable"]
                }
            
            # Validate safety level
            if not self._is_safety_acceptable(ai_response.risk_level, safety_level):
                return {
                    "success": False,
                    "command": ai_response.command,
                    "explanation": ai_response.explanation,
                    "error": f"Command risk level ({ai_response.risk_level.value}) exceeds safety level ({safety_level.value})",
                    "execution_time": 0.0,
                    "safety_level": safety_level.value,
                    "warnings": ai_response.warnings,
                    "requires_approval": True
                }
            
            # Execute the command
            return await self.validate_and_execute(
                command=ai_response.command,
                server_id=server_id,
                explanation=ai_response.explanation,
                safety_level=safety_level,
                user_id=user_id,
                ai_prompt=prompt,
                ai_reasoning=ai_response.reasoning,
                warnings=ai_response.warnings
            )
            
        except Exception as e:
            logger.error(f"Natural command execution failed: {e}")
            if isinstance(e, (ServiceError, ValidationError, ExternalServiceError)):
                raise
            raise ServiceError(f"Failed to execute natural command: {str(e)}")
    
    async def validate_and_execute(
        self,
        command: str,
        server_id: str,
        explanation: str = "",
        safety_level: SafetyLevel = SafetyLevel.CAUTIOUS,
        user_id: Optional[str] = None,
        ai_prompt: Optional[str] = None,
        ai_reasoning: Optional[str] = None,
        warnings: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Validate and execute a direct command"""
        
        start_time = time.time()
        
        try:
            # Get server
            server = await self._get_server(server_id)
            if not server:
                raise ValidationError(f"Server {server_id} not found", "server_id")
            
            # Validate command safety
            validation = await self.ai_service.validate_command(
                command=command,
                server_context={
                    "hostname": server.hostname,
                    "os_type": server.os_type,
                    "username": server.username
                }
            )
            
            # Check safety level
            if not self._is_safety_acceptable(validation.risk_level, safety_level):
                execution_time = time.time() - start_time
                return {
                    "success": False,
                    "command": command,
                    "explanation": explanation or validation.explanation,
                    "error": f"Command risk level ({validation.risk_level.value}) exceeds safety level ({safety_level.value})",
                    "execution_time": execution_time,
                    "safety_level": safety_level.value,
                    "warnings": (warnings or []) + validation.warnings,
                    "requires_approval": True
                }
            
            # Execute command via SSH
            logger.info(f"Executing command on {server.hostname}: {command}")
            
            try:
                # Get SSH manager for this server
                ssh_manager = await ssh_factory.get_manager(server_id)
                
                # Connect to server if not already connected
                if not ssh_manager.is_connected():
                    server_data = {
                        "hostname": server.hostname,
                        "username": server.username,
                        "password": server.password,  # This should be encrypted in the database
                        "port": server.port,
                        "timeout": self.settings.ssh_timeout
                    }
                    await ssh_factory.connect_to_server(server_id, server_data)
                
                # Execute command with correct parameters
                result = await ssh_manager.execute_command(
                    command=command,
                    timeout=self.settings.ssh_timeout
                )
                
                execution_time = time.time() - start_time
                success = result.exit_code == 0
                
                # Log to command history
                await self._log_command_history(
                    server_id=server_id,
                    user_id=user_id,
                    command=command,
                    output=result.stdout,
                    error=result.stderr,
                    exit_code=result.exit_code,
                    execution_time=execution_time,
                    ai_prompt=ai_prompt,
                    ai_reasoning=ai_reasoning,
                    risk_level=validation.risk_level.value
                )
                
                return {
                    "success": success,
                    "command": command,
                    "explanation": explanation or validation.explanation,
                    "output": result.stdout,
                    "error": result.stderr if not success else None,
                    "execution_time": execution_time,
                    "safety_level": safety_level.value,
                    "warnings": (warnings or []) + validation.warnings,
                    "exit_code": result.exit_code
                }
                
            except Exception as ssh_error:
                execution_time = time.time() - start_time
                error_msg = f"SSH execution failed: {str(ssh_error)}"
                
                # Log failed command
                await self._log_command_history(
                    server_id=server_id,
                    user_id=user_id,
                    command=command,
                    output="",
                    error=error_msg,
                    exit_code=1,
                    execution_time=execution_time,
                    ai_prompt=ai_prompt,
                    ai_reasoning=ai_reasoning,
                    risk_level=validation.risk_level.value
                )
                
                raise ExternalServiceError("ssh", error_msg)
                
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Command validation/execution failed: {e}")
            
            if isinstance(e, (ServiceError, ValidationError, ExternalServiceError)):
                raise
            
            return {
                "success": False,
                "command": command,
                "explanation": explanation,
                "error": f"Command execution failed: {str(e)}",
                "execution_time": execution_time,
                "safety_level": safety_level.value,
                "warnings": warnings or []
            }
    
    async def get_command_suggestions(
        self,
        prompt: str,
        server_context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, str]]:
        """Get command suggestions for ambiguous requests"""
        
        try:
            # Use AI to generate multiple command options
            ai_response = await self.ai_service.generate_command(
                prompt=f"Provide 3 different ways to accomplish: {prompt}",
                server_context=server_context
            )
            
            suggestions = []
            
            # Add the main suggestion
            suggestions.append({
                "command": ai_response.command,
                "explanation": ai_response.explanation,
                "risk_level": ai_response.risk_level.value
            })
            
            # Add alternatives if available
            for alt in ai_response.alternatives[:2]:  # Limit to 2 alternatives
                alt_validation = await self.ai_service.validate_command(alt, server_context)
                suggestions.append({
                    "command": alt,
                    "explanation": f"Alternative approach: {alt}",
                    "risk_level": alt_validation.risk_level.value
                })
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Failed to get command suggestions: {e}")
            return [{
                "command": "echo 'Unable to generate suggestions'",
                "explanation": f"Error generating suggestions: {str(e)}",
                "risk_level": "safe"
            }]
    
    async def get_command_history(
        self,
        server_id: str,
        limit: int = 50,
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get simple command history for a server"""
        
        try:
            # Build query
            query = select(CommandHistory).where(CommandHistory.server_id == server_id)
            
            if user_id:
                query = query.where(CommandHistory.user_id == user_id)
            
            query = query.order_by(CommandHistory.executed_at.desc()).limit(limit)
            
            # Execute query
            result = await self.db.execute(query)
            history_records = result.scalars().all()
            
            # Format response
            history = []
            for record in history_records:
                history.append({
                    "id": record.id,
                    "command": record.command,
                    "output": record.output,
                    "error": record.error,
                    "exit_code": record.exit_code,
                    "execution_time": record.execution_time,
                    "executed_at": record.executed_at.isoformat(),
                    "is_ai_generated": record.is_ai_generated,
                    "ai_prompt": record.ai_prompt,
                    "risk_level": record.risk_level
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Failed to get command history: {e}")
            raise ServiceError(f"Failed to retrieve command history: {str(e)}")
    
    async def _get_server(self, server_id: str) -> Optional[Server]:
        """Get server by ID"""
        try:
            stmt = select(Server).where(Server.id == server_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get server {server_id}: {e}")
            return None
    
    def _is_safety_acceptable(self, risk_level, safety_level: SafetyLevel) -> bool:
        """Check if command risk level is acceptable for given safety level using centralized validator"""
        return SafetyValidator.is_safety_acceptable(risk_level, safety_level)
    
    async def _log_command_history(
        self,
        server_id: str,
        user_id: Optional[str],
        command: str,
        output: str,
        error: str,
        exit_code: int,
        execution_time: float,
        ai_prompt: Optional[str] = None,
        ai_reasoning: Optional[str] = None,
        risk_level: Optional[str] = None
    ):
        """Log command execution to history"""
        
        try:
            history_record = CommandHistory(
                id=str(uuid.uuid4()),
                server_id=server_id,
                user_id=user_id or "system",
                command=command,
                output=output,
                error=error,
                exit_code=exit_code,
                execution_time=execution_time,
                is_ai_generated=ai_prompt is not None,
                ai_prompt=ai_prompt,
                ai_reasoning=ai_reasoning,
                risk_level=risk_level,
                executed_at=datetime.utcnow()
            )
            
            self.db.add(history_record)
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to log command history: {e}")
            # Don't raise - logging failure shouldn't break command execution
