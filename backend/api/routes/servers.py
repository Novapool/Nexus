"""
Server management API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from backend.config.database import get_db
from backend.models.schemas import (
    ServerCreate, 
    ServerResponse, 
    ServerUpdate,
    ServerListResponse,
    SafetyLevel
)
from backend.services.server_service import ServerService
from backend.services.server_detection_service import ServerDetectionService
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
    safety_level: str = "cautious",
    working_dir: str = None,
    timeout: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """Execute command on server with safety level"""
    server_service = ServerService(db)
    
    # Map string to enum - using correct SafetyLevel values
    safety_map = {
        "paranoid": SafetyLevel.PARANOID,
        "safe": SafetyLevel.SAFE,
        "cautious": SafetyLevel.CAUTIOUS,
        "normal": SafetyLevel.NORMAL,
        "permissive": SafetyLevel.PERMISSIVE
    }
    
    safety = safety_map.get(safety_level, SafetyLevel.CAUTIOUS)
    
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


@router.post("/{server_id}/scan")
async def scan_server(
    server_id: str,
    scan_type: str = "full",
    db: AsyncSession = Depends(get_db)
):
    """Perform system scan on server
    
    Scan types:
    - quick: Basic OS and system info
    - hardware: Hardware profiling only
    - software: Services and capabilities only
    - full: Complete system scan (default)
    """
    detection_service = ServerDetectionService(db)
    
    # Validate scan type
    valid_scan_types = ["quick", "hardware", "software", "full"]
    if scan_type not in valid_scan_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scan type. Must be one of: {', '.join(valid_scan_types)}"
        )
    
    try:
        scan_results = await detection_service.perform_initial_scan(server_id, scan_type)
        return scan_results
    except ServerNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Server scan failed for {server_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{server_id}/profile")
async def get_server_profile(
    server_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get comprehensive server profile including system, hardware, and services info"""
    server_service = ServerService(db)
    
    try:
        # Get basic server info
        server = await server_service.get_server(server_id)
        if not server:
            raise ServerNotFoundError(server_id)
        
        # Get system profile from database if available
        from sqlalchemy import select
        from backend.models.database import ServerProfile, ServerHardware, ServerServices
        
        # Get profile data
        profile_query = select(ServerProfile).where(ServerProfile.server_id == server_id)
        profile_result = await db.execute(profile_query)
        profile = profile_result.scalar_one_or_none()
        
        # Get hardware data
        hardware_query = select(ServerHardware).where(ServerHardware.server_id == server_id)
        hardware_result = await db.execute(hardware_query)
        hardware = hardware_result.scalar_one_or_none()
        
        # Get services data
        services_query = select(ServerServices).where(ServerServices.server_id == server_id)
        services_result = await db.execute(services_query)
        services = services_result.scalar_one_or_none()
        
        return {
            "server": server.model_dump() if hasattr(server, 'model_dump') else server.dict(),
            "profile": {
                "os_family": profile.os_family if profile else None,
                "os_distribution": profile.os_distribution if profile else None,
                "os_version": profile.os_version if profile else None,
                "kernel_version": profile.kernel_version if profile else None,
                "architecture": profile.architecture if profile else None,
                "package_manager": profile.package_manager if profile else None,
                "init_system": profile.init_system if profile else None,
                "last_scanned": profile.last_scanned.isoformat() if profile and profile.last_scanned else None
            } if profile else None,
            "hardware": {
                "cpu_count": hardware.cpu_count if hardware else None,
                "cpu_model": hardware.cpu_model if hardware else None,
                "memory_total_mb": hardware.memory_total_mb if hardware else None,
                "memory_available_mb": hardware.memory_available_mb if hardware else None,
                "swap_total_mb": hardware.swap_total_mb if hardware else None,
                "storage_info": hardware.storage_info if hardware else None,
                "gpu_info": hardware.gpu_info if hardware else None,
                "network_info": hardware.network_info if hardware else None
            } if hardware else None,
            "services": {
                "has_docker": services.has_docker if services else False,
                "docker_version": services.docker_version if services else None,
                "has_systemd": services.has_systemd if services else False,
                "systemd_version": services.systemd_version if services else None,
                "has_sudo": services.has_sudo if services else False,
                "firewall_type": services.firewall_type if services else None,
                "listening_ports": services.listening_ports if services else [],
                "running_services": services.running_services if services else []
            } if services else None
        }
        
    except ServerNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to get server profile for {server_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{server_id}/validate")
async def validate_server_connection(
    server_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Validate server connection and perform pre-flight checks"""
    detection_service = ServerDetectionService(db)
    
    try:
        validation_result = await detection_service.validate_connection(server_id)
        return validation_result
    except ServerNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Connection validation failed for {server_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{server_id}/system-info")
async def get_system_info(
    server_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get current system information from server"""
    server_service = ServerService(db)
    
    try:
        system_info = await server_service.get_system_info(server_id)
        return system_info
    except ServerNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to get system info for {server_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk/scan")
async def bulk_scan_servers(
    server_ids: List[str],
    scan_type: str = "quick",
    db: AsyncSession = Depends(get_db)
):
    """Scan multiple servers in parallel
    
    Useful for refreshing system information across multiple servers
    """
    detection_service = ServerDetectionService(db)
    
    # Validate scan type
    valid_scan_types = ["quick", "hardware", "software", "full"]
    if scan_type not in valid_scan_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scan type. Must be one of: {', '.join(valid_scan_types)}"
        )
    
    results = []
    for server_id in server_ids:
        try:
            scan_result = await detection_service.perform_initial_scan(server_id, scan_type)
            results.append({
                "server_id": server_id,
                "success": scan_result.get("success", False),
                "scan_type": scan_type,
                "timestamp": scan_result.get("scan_timestamp")
            })
        except Exception as e:
            logger.error(f"Scan failed for server {server_id}: {e}")
            results.append({
                "server_id": server_id,
                "success": False,
                "error": str(e)
            })
    
    return {
        "total_servers": len(server_ids),
        "successful_scans": sum(1 for r in results if r.get("success")),
        "failed_scans": sum(1 for r in results if not r.get("success")),
        "results": results
    }
