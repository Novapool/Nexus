"""
Server management API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from datetime import datetime
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


@router.get("/{server_id}/detailed-profile")
async def get_detailed_server_profile(
    server_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get comprehensive detailed server profile with all available information"""
    server_service = ServerService(db)
    
    try:
        # Get basic server info
        server = await server_service.get_server(server_id)
        if not server:
            raise ServerNotFoundError(server_id)
        
        # Get all profile data
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
        
        # Build comprehensive response
        detailed_profile = {
            "server": {
                "id": server.id,
                "hostname": server.hostname,
                "username": server.username,
                "port": server.port,
                "os_type": server.os_type,
                "description": server.description,
                "connection_status": server.connection_status,
                "last_connected": server.last_connected.isoformat() if server.last_connected else None,
                "created_at": server.created_at.isoformat(),
                "updated_at": server.updated_at.isoformat(),
                "last_scan_date": server.last_scan_date.isoformat() if server.last_scan_date else None
            },
            "system_profile": {
                "os_family": profile.os_family if profile else None,
                "os_distribution": profile.os_distribution if profile else None,
                "os_version": profile.os_version if profile else None,
                "kernel_version": profile.kernel_version if profile else None,
                "architecture": profile.architecture if profile else None,
                "package_manager": profile.package_manager if profile else None,
                "init_system": profile.init_system if profile else None,
                "last_scanned": profile.last_scanned.isoformat() if profile and profile.last_scanned else None,
                "scan_data": profile.scan_data if profile else None
            } if profile else None,
            "hardware": {
                "cpu": {
                    "count": hardware.cpu_count if hardware else None,
                    "model": hardware.cpu_model if hardware else None,
                    "detailed_info": hardware.cpu_info if hardware else None
                },
                "memory": {
                    "total_mb": hardware.memory_total_mb if hardware else None,
                    "available_mb": hardware.memory_available_mb if hardware else None,
                    "swap_total_mb": hardware.swap_total_mb if hardware else None,
                    "detailed_info": hardware.memory_info if hardware else None
                },
                "storage": hardware.storage_info if hardware else None,
                "gpu": hardware.gpu_info if hardware else None,
                "network": hardware.network_info if hardware else None,
                "last_updated": hardware.last_updated.isoformat() if hardware and hardware.last_updated else None
            } if hardware else None,
            "services": {
                "docker": {
                    "available": services.has_docker if services else False,
                    "version": services.docker_version if services else None
                },
                "systemd": {
                    "available": services.has_systemd if services else False,
                    "version": services.systemd_version if services else None
                },
                "sudo": {
                    "available": services.has_sudo if services else False
                },
                "firewall": {
                    "type": services.firewall_type if services else None
                },
                "listening_ports": services.listening_ports if services else [],
                "running_services": services.running_services if services else [],
                "last_updated": services.last_updated.isoformat() if services and services.last_updated else None
            } if services else None
        }
        
        return detailed_profile
        
    except ServerNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to get detailed server profile for {server_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{server_id}/performance")
async def get_server_performance(
    server_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get real-time server performance metrics"""
    server_service = ServerService(db)
    
    try:
        # Get server from database
        server = await server_service.get_server(server_id)
        if not server:
            raise ServerNotFoundError(server_id)
        
        # Get SSH manager
        from backend.core.ssh_manager import ssh_factory
        from backend.utils.crypto import decrypt_password
        
        server_data = {
            "hostname": server.hostname,
            "username": server.username,
            "port": server.port,
            "password": server.password,
            "timeout": 30
        }
        
        manager = await ssh_factory.connect_to_server(server_id, server_data)
        
        # Performance monitoring commands
        commands = {
            "uptime": "uptime",
            "load_avg": "cat /proc/loadavg",
            "cpu_usage": "top -bn1 | grep 'Cpu(s)' | head -1",
            "memory_usage": "free -m",
            "disk_usage": "df -h",
            "disk_io": "iostat -d 1 1 2>/dev/null | tail -n +4 || echo 'iostat not available'",
            "network_stats": "cat /proc/net/dev | tail -n +3",
            "processes": "ps aux --sort=-%cpu | head -10",
            "temperature": "sensors 2>/dev/null | grep -E '(Core|temp)' || echo 'sensors not available'"
        }
        
        results = {}
        for key, command in commands.items():
            try:
                result = await manager.execute_command(command, timeout=10)
                if result.success:
                    results[key] = result.stdout.strip()
                else:
                    results[key] = None
            except Exception as e:
                logger.warning(f"Performance command '{key}' failed: {e}")
                results[key] = None
        
        # Parse and structure the performance data
        performance_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": results.get("uptime"),
            "load_average": results.get("load_avg"),
            "cpu": _parse_cpu_usage(results.get("cpu_usage")),
            "memory": _parse_memory_usage(results.get("memory_usage")),
            "disk": _parse_disk_usage(results.get("disk_usage")),
            "disk_io": results.get("disk_io"),
            "network": _parse_network_stats(results.get("network_stats")),
            "top_processes": _parse_top_processes(results.get("processes")),
            "temperature": results.get("temperature")
        }
        
        return performance_data
        
    except ServerNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to get server performance for {server_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _parse_cpu_usage(cpu_output):
    """Parse CPU usage from top command output"""
    if not cpu_output:
        return None
    
    try:
        # Example: "Cpu(s):  5.3%us,  1.0%sy,  0.0%ni, 93.4%id,  0.3%wa,  0.0%hi,  0.0%si,  0.0%st"
        parts = cpu_output.split(',')
        cpu_data = {}
        for part in parts:
            part = part.strip()
            if '%us' in part:
                cpu_data['user'] = float(part.split('%')[0].split()[-1])
            elif '%sy' in part:
                cpu_data['system'] = float(part.split('%')[0].split()[-1])
            elif '%id' in part:
                cpu_data['idle'] = float(part.split('%')[0].split()[-1])
            elif '%wa' in part:
                cpu_data['wait'] = float(part.split('%')[0].split()[-1])
        
        if cpu_data:
            cpu_data['usage'] = round(100 - cpu_data.get('idle', 0), 1)
        
        return cpu_data
    except:
        return {"raw": cpu_output}


def _parse_memory_usage(memory_output):
    """Parse memory usage from free command output"""
    if not memory_output:
        return None
    
    try:
        lines = memory_output.split('\n')
        for line in lines:
            if line.startswith('Mem:'):
                parts = line.split()
                if len(parts) >= 7:
                    total = int(parts[1])
                    used = int(parts[2])
                    free = int(parts[3])
                    available = int(parts[6]) if len(parts) > 6 else free
                    
                    return {
                        "total_mb": total,
                        "used_mb": used,
                        "free_mb": free,
                        "available_mb": available,
                        "usage_percent": round((used / total) * 100, 1) if total > 0 else 0
                    }
    except:
        return {"raw": memory_output}
    
    return None


def _parse_disk_usage(disk_output):
    """Parse disk usage from df command output"""
    if not disk_output:
        return None
    
    try:
        lines = disk_output.split('\n')[1:]  # Skip header
        disk_data = []
        
        for line in lines:
            parts = line.split()
            if len(parts) >= 6 and not line.startswith('tmpfs'):
                disk_data.append({
                    "filesystem": parts[0],
                    "size": parts[1],
                    "used": parts[2],
                    "available": parts[3],
                    "usage_percent": parts[4],
                    "mount_point": parts[5]
                })
        
        return disk_data
    except:
        return {"raw": disk_output}


def _parse_network_stats(network_output):
    """Parse network statistics from /proc/net/dev"""
    if not network_output:
        return None
    
    try:
        lines = network_output.split('\n')
        network_data = []
        
        for line in lines:
            if ':' in line:
                parts = line.split(':')
                if len(parts) >= 2:
                    interface = parts[0].strip()
                    stats = parts[1].split()
                    if len(stats) >= 16:
                        network_data.append({
                            "interface": interface,
                            "rx_bytes": int(stats[0]),
                            "rx_packets": int(stats[1]),
                            "tx_bytes": int(stats[8]),
                            "tx_packets": int(stats[9])
                        })
        
        return network_data
    except:
        return {"raw": network_output}


def _parse_top_processes(processes_output):
    """Parse top processes from ps command output"""
    if not processes_output:
        return None
    
    try:
        lines = processes_output.split('\n')[1:]  # Skip header
        processes = []
        
        for line in lines[:10]:  # Top 10 processes
            parts = line.split(None, 10)  # Split on whitespace, max 11 parts
            if len(parts) >= 11:
                processes.append({
                    "user": parts[0],
                    "pid": parts[1],
                    "cpu_percent": parts[2],
                    "memory_percent": parts[3],
                    "command": parts[10]
                })
        
        return processes
    except:
        return {"raw": processes_output}


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
