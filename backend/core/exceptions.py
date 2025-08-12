"""
Custom exceptions for Nexus application - Updated to use centralized error handling
"""

from typing import Optional

# Import centralized error handling
from backend.core.error_handler import (
    ServiceError,
    ValidationError,
    ExternalServiceError,
    DatabaseError,
    AuthenticationError,
    ConfigurationError
)

# Keep the original NexusException for backwards compatibility
class NexusException(Exception):
    """Base exception class for Nexus application - kept for backwards compatibility"""
    
    def __init__(
        self, 
        message: str, 
        status_code: int = 500, 
        detail: Optional[str] = None
    ):
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(self.message)


# Specific exception classes that extend our centralized error types
class ServerNotFoundError(ValidationError):
    """Server not found errors"""
    
    def __init__(self, server_id: str):
        super().__init__(f"Server '{server_id}' not found", "server_id", {"server_id": server_id})


class SSHConnectionError(ExternalServiceError):
    """SSH connection related errors"""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__("ssh", message, details)


class AIServiceError(ExternalServiceError):
    """AI service related errors"""
    
    def __init__(self, message: str, model: str = None):
        details = {"model": model} if model else None
        super().__init__("ai", message, details)


class CommandValidationError(ValidationError):
    """Command validation errors"""
    
    def __init__(self, command: str, reason: str):
        super().__init__(f"Command validation failed: {reason}", "command", {"command": command, "reason": reason})


# Re-export centralized error classes for convenience
__all__ = [
    # Backwards compatibility
    "NexusException",
    "ServerNotFoundError", 
    "SSHConnectionError",
    "AIServiceError",
    "CommandValidationError",
    
    # Centralized error classes
    "ServiceError",
    "ValidationError", 
    "ExternalServiceError",
    "DatabaseError",
    "AuthenticationError",
    "ConfigurationError"
]
