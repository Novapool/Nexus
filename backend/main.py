"""
Nexus - AI-Powered Server Management System
FastAPI Application Entry Point
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import logging
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from backend.config.settings import get_settings
from backend.config.database import init_db, close_db
from backend.api.routes import api_router
from backend.core.exceptions import NexusException


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events"""
    # Startup
    logger.info("Starting Nexus application...")
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Nexus application...")
    await close_db()
    logger.info("Database connections closed")


def create_application() -> FastAPI:
    """Factory function to create FastAPI application"""
    settings = get_settings()
    
    app = FastAPI(
        title="Nexus Server Management API",
        description="AI-powered server management system with natural language interface",
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan
    )
    
    # Add security middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts
    )
    
    # Add CORS middleware for local development
    if settings.debug:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    # Include API routes
    app.include_router(api_router, prefix="/api/v1")
    
    # Serve static files (frontend)
    if settings.serve_static:
        try:
            static_dir = project_root / "frontend" / "static"
            if static_dir.exists():
                app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
            
            frontend_dir = project_root / "frontend"
            if frontend_dir.exists():
                app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
        except Exception as e:
            logger.warning(f"Could not mount static files: {e}")
    
    return app


# Global exception handler
async def nexus_exception_handler(request, exc: NexusException):
    """Handle custom Nexus exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "detail": exc.detail}
    )


# Create the application instance
app = create_application()

# Register exception handlers
app.add_exception_handler(NexusException, nexus_exception_handler)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "nexus-api",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )