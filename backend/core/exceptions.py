"""
Custom exception classes for Nexus application
"""

from typing import Optional


class NexusException(Exception):
    """Base exception class for Nexus application"""
    
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


class AuthenticationError(NexusException):
    """Authentication related errors"""
    
    def __init__(self, message: str = "Authentication failed", detail: Optional[str] = None):
        super().__init__(message, status_code=401, detail=detail)


class AuthorizationError(NexusException):
    """Authorization related errors"""
    
    def __init__(self, message: str = "Access denied", detail: Optional[str] = None):
        super().__init__(message, status_code=403, detail=detail)


class ServerNotFoundError(NexusException):
    """Server not found errors"""
    
    def __init__(self, server_id: str, detail: Optional[str] = None):
        message = f"Server '{server_id}' not found"
        super().__init__(message, status_code=404, detail=detail)


class SSHConnectionError(NexusException):
    """SSH connection related errors"""
    
    def __init__(self, message: str, detail: Optional[str] = None):
        super().__init__(message, status_code=500, detail=detail)


class AIServiceError(NexusException):
    """AI service related errors"""
    
    def __init__(self, message: str = "AI service error", detail: Optional[str] = None):
        super().__init__(message, status_code=500, detail=detail)


class CommandValidationError(NexusException):
    """Command validation errors"""
    
    def __init__(self, command: str, reason: str, detail: Optional[str] = None):
        message = f"Command validation failed: {reason}"
        super().__init__(message, status_code=400, detail=detail)


class ConfigurationError(NexusException):
    """Configuration related errors"""
    
    def __init__(self, message: str, detail: Optional[str] = None):
        super().__init__(message, status_code=500, detail=detail)