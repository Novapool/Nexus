"""
API Routes initialization and router setup
"""

from fastapi import APIRouter
from backend.api.routes import health, servers, ai, terminal, auth

# Create main API router
api_router = APIRouter()

# Include all route modules
api_router.include_router(
    health.router,
    prefix="/health",
    tags=["health"]
)

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["authentication"]
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

api_router.include_router(
    terminal.router,
    prefix="/terminal",
    tags=["terminal"]
)