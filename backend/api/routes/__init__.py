"""
Simplified API Routes initialization
"""

from fastapi import APIRouter
from backend.api.routes import health, servers, ai, operations, commands, terminal
from backend.config.settings import get_settings

# Create main API router
api_router = APIRouter()

# Include core routes (always available)
api_router.include_router(
    health.router,
    prefix="/health",
    tags=["health"]
)

api_router.include_router(
    servers.router,
    prefix="/servers",
    tags=["servers"]
)

api_router.include_router(
    ai.router,
    prefix="/ai",
    tags=["ai"]
)

# Include simple commands router (default enabled)
settings = get_settings()
if settings.enable_quick_commands:
    api_router.include_router(
        commands.router,
        prefix="/commands",
        tags=["commands"]
    )

# Operations router is optional - include only if operation planning is enabled
if settings.enable_operation_planning:
    api_router.include_router(
        operations.router,
        prefix="/operations",
        tags=["operations"]
    )

# Include terminal routes for real-time SSH sessions
api_router.include_router(
    terminal.router,
    tags=["terminal"]
)

# Note: auth routes not implemented
