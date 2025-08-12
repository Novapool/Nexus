"""
Centralized error handling for Nexus application
"""

import logging
from typing import Optional, Dict, Any
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class ServiceError(Exception):
    """Base service error"""
    def __init__(self, message: str, error_code: str = "SERVICE_ERROR", details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code  
        self.details = details or {}
        super().__init__(message)


class ValidationError(ServiceError):
    """Validation error"""
    def __init__(self, message: str, field: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "VALIDATION_ERROR", details)
        self.field = field


class ExternalServiceError(ServiceError):
    """External service error (SSH, AI, etc.)"""
    def __init__(self, service: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(f"{service}: {message}", f"{service.upper()}_ERROR", details)
        self.service = service


class DatabaseError(ServiceError):
    """Database operation error"""
    def __init__(self, message: str, operation: str = "unknown", details: Optional[Dict[str, Any]] = None):
        super().__init__(f"Database {operation}: {message}", "DATABASE_ERROR", details)
        self.operation = operation


class AuthenticationError(ServiceError):
    """Authentication/authorization error"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "AUTH_ERROR", details)


class ConfigurationError(ServiceError):
    """Configuration error"""
    def __init__(self, message: str, config_key: str = "unknown", details: Optional[Dict[str, Any]] = None):
        super().__init__(f"Configuration error for {config_key}: {message}", "CONFIG_ERROR", details)
        self.config_key = config_key


def handle_service_error(error: Exception) -> HTTPException:
    """Convert service errors to HTTP exceptions"""
    
    if isinstance(error, ValidationError):
        return HTTPException(status_code=400, detail={
            "error": error.error_code,
            "message": error.message,
            "field": error.field,
            "details": error.details
        })
    
    elif isinstance(error, AuthenticationError):
        return HTTPException(status_code=401, detail={
            "error": error.error_code,
            "message": error.message,
            "details": error.details
        })
    
    elif isinstance(error, ExternalServiceError):
        return HTTPException(status_code=502, detail={
            "error": error.error_code, 
            "message": error.message,
            "service": error.service,
            "details": error.details
        })
    
    elif isinstance(error, DatabaseError):
        return HTTPException(status_code=500, detail={
            "error": error.error_code,
            "message": error.message,
            "operation": error.operation,
            "details": error.details
        })
    
    elif isinstance(error, ConfigurationError):
        return HTTPException(status_code=500, detail={
            "error": error.error_code,
            "message": error.message,
            "config_key": error.config_key,
            "details": error.details
        })
    
    elif isinstance(error, ServiceError):
        return HTTPException(status_code=500, detail={
            "error": error.error_code,
            "message": error.message,
            "details": error.details
        })
    
    else:
        # Log unexpected errors
        logger.error(f"Unhandled error: {error}", exc_info=True)
        return HTTPException(status_code=500, detail={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred"
        })


def log_error(error: Exception, context: str = ""):
    """Log error with appropriate level and context"""
    
    if isinstance(error, ValidationError):
        logger.warning(f"Validation error in {context}: {error.message}")
    
    elif isinstance(error, ExternalServiceError):
        logger.error(f"External service error in {context}: {error.service} - {error.message}")
    
    elif isinstance(error, DatabaseError):
        logger.error(f"Database error in {context}: {error.operation} - {error.message}")
    
    elif isinstance(error, ServiceError):
        logger.error(f"Service error in {context}: {error.error_code} - {error.message}")
    
    else:
        logger.error(f"Unexpected error in {context}: {error}", exc_info=True)


def create_error_response(
    error_code: str,
    message: str,
    status_code: int = 500,
    details: Optional[Dict[str, Any]] = None
) -> HTTPException:
    """Create a standardized error response"""
    
    return HTTPException(status_code=status_code, detail={
        "error": error_code,
        "message": message,
        "details": details or {}
    })


# Common error responses
def not_found_error(resource: str, resource_id: str) -> HTTPException:
    """Standard not found error"""
    return create_error_response(
        error_code="NOT_FOUND",
        message=f"{resource} {resource_id} not found",
        status_code=404,
        details={"resource": resource, "resource_id": resource_id}
    )


def permission_denied_error(action: str, resource: str = "") -> HTTPException:
    """Standard permission denied error"""
    message = f"Permission denied for action: {action}"
    if resource:
        message += f" on resource: {resource}"
    
    return create_error_response(
        error_code="PERMISSION_DENIED",
        message=message,
        status_code=403,
        details={"action": action, "resource": resource}
    )


def rate_limit_error(limit: int, window: str) -> HTTPException:
    """Standard rate limit error"""
    return create_error_response(
        error_code="RATE_LIMIT_EXCEEDED",
        message=f"Rate limit exceeded: {limit} requests per {window}",
        status_code=429,
        details={"limit": limit, "window": window}
    )


def validation_error(field: str, message: str, value: Any = None) -> HTTPException:
    """Standard validation error"""
    return create_error_response(
        error_code="VALIDATION_ERROR",
        message=f"Validation failed for field '{field}': {message}",
        status_code=400,
        details={"field": field, "value": value}
    )


# Error context manager for consistent error handling
class ErrorContext:
    """Context manager for consistent error handling and logging"""
    
    def __init__(self, operation: str, resource: str = "", log_errors: bool = True):
        self.operation = operation
        self.resource = resource
        self.log_errors = log_errors
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val and self.log_errors:
            context = f"{self.operation}"
            if self.resource:
                context += f" on {self.resource}"
            log_error(exc_val, context)
        
        # Don't suppress the exception
        return False
    
    def handle_error(self, error: Exception) -> HTTPException:
        """Handle error within this context"""
        if self.log_errors:
            context = f"{self.operation}"
            if self.resource:
                context += f" on {self.resource}"
            log_error(error, context)
        
        return handle_service_error(error)


# Decorator for automatic error handling
def handle_errors(operation: str = "", resource: str = ""):
    """Decorator to automatically handle service errors in route handlers"""
    
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                context = operation or func.__name__
                if resource:
                    context += f" on {resource}"
                
                log_error(e, context)
                raise handle_service_error(e)
        
        return wrapper
    return decorator
