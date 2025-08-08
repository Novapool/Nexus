"""
Health check and system status endpoints
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from backend.config.database import get_db
from backend.config.settings import get_settings
import httpx
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def basic_health():
    """Basic health check"""
    return {
        "status": "healthy",
        "service": "nexus-api"
    }


@router.get("/detailed")
async def detailed_health(
    db: AsyncSession = Depends(get_db)
):
    """Detailed health check including dependencies"""
    settings = get_settings()
    health_status = {
        "status": "healthy",
        "service": "nexus-api",
        "version": "1.0.0",
        "components": {}
    }
    
    # Check database
    try:
        await db.execute(text("SELECT 1"))
        health_status["components"]["database"] = {
            "status": "healthy",
            "url": settings.database_url.split("://")[0] + "://***"
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # Check AI service (Ollama)
    if settings.enable_ai:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{settings.ollama_base_url}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    health_status["components"]["ai_service"] = {
                        "status": "healthy",
                        "provider": settings.ai_provider,
                        "models_available": len(models),
                        "url": settings.ollama_base_url
                    }
                else:
                    health_status["components"]["ai_service"] = {
                        "status": "unhealthy",
                        "error": f"HTTP {response.status_code}"
                    }
                    health_status["status"] = "degraded"
        except Exception as e:
            logger.error(f"AI service health check failed: {e}")
            health_status["components"]["ai_service"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "degraded"
    
    return health_status