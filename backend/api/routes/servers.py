"""
Server management API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from backend.core.ssh_manager import SafetyLevel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from backend.config.database import get_db
from backend.models.schemas import (
    ServerCreate, 
    ServerResponse, 
    ServerUpdate,
    ServerListResponse
)
from backend.services.server_service import ServerService
from backend.core.exceptions import ServerNotFoundError
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=ServerListResponse)
async def list_servers(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Get list of all configured servers"""
    server_service = ServerService(db)
    servers = await server_service.get_servers(skip=skip, limit=limit)
    total = await server_service.count_servers()
    
    return ServerListResponse(
        servers=servers,
        total=total,
        skip=skip,
        limit=limit
    )


@router.post("/", response_model=ServerResponse)
async def create_server(
    server: ServerCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new server configuration"""
    server_service = ServerService(db)
    
    try:
        created_server = await server_service.create_server(server)
        logger.info(f"Created server: {created_server.hostname}")
        return created_server
    except Exception as e:
        logger.error(f"Failed to create server: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{server_id}", response_model=ServerResponse)
async def get_server(
    server_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get server by ID"""
    server_service = ServerService(db)
    
    server = await server_service.get_server(server_id)
    if not server:
        raise ServerNotFoundError(server_id)
    
    return server


@router.put("/{server_id}", response_model=ServerResponse)
async def update_server(
    server_id: str,
    server_update: ServerUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update server configuration"""
    server_service = ServerService(db)
    
    try:
        updated_server = await server_service.update_server(server_id, server_update)
        if not updated_server:
            raise ServerNotFoundError(server_id)
        
        logger.info(f"Updated server: {server_id}")
        return updated_server
    except ServerNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to update server {server_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{server_id}")
async def delete_server(
    server_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete server configuration"""
    server_service = ServerService(db)
    
    success = await server_service.delete_server(server_id)
    if not success:
        raise ServerNotFoundError(server_id)
    
    logger.info(f"Deleted server: {server_id}")
    return {"message": f"Server {server_id} deleted successfully"}


@router.post("/{server_id}/test-connection")
async def test_connection(
    server_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Test SSH connection to server"""
    server_service = ServerService(db)
    
    try:
        result = await server_service.test_connection(server_id)
        return {
            "server_id": server_id,
            "connection_status": "success" if result else "failed",
            "details": result
        }
    except ServerNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Connection test failed for {server_id}: {e}")
        return {
            "server_id": server_id,
            "connection_status": "failed",
            "error": str(e)
        }
    

# Add this endpoint after your existing endpoints in servers.py
@router.post("/{server_id}/execute")
async def execute_command(
    server_id: str,
    command: str,
    safety_level: str = "dry_run",
    working_dir: str = None,
    timeout: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """Execute command on server with safety level"""
    server_service = ServerService(db)
    
    # Map string to enum
    safety_map = {
        "dry_run": SafetyLevel.DRY_RUN,
        "safe": SafetyLevel.SAFE,
        "cautious": SafetyLevel.CAUTIOUS, 
        "full": SafetyLevel.FULL
    }
    
    safety = safety_map.get(safety_level, SafetyLevel.DRY_RUN)
    
    try:
        result = await server_service.execute_command(
            server_id=server_id,
            command=command,
            working_dir=working_dir,
            timeout=timeout,
            safety_level=safety
        )
        return {
            "server_id": server_id,
            "executed_command": command,
            "safety_level": safety_level,
            "result": result
        }
    except ServerNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Command execution failed for {server_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))