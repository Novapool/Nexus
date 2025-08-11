"""
Server management business logic service with SSH integration
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from backend.models.database import Server
from backend.models.schemas import (
    ServerCreate, 
    ServerUpdate, 
    ServerResponse,
    OSType,
    SystemInfo
)
from backend.core.exceptions import ServerNotFoundError, SSHConnectionError
from backend.core.ssh_manager import ssh_factory, SafetyLevel
from backend.utils.crypto import encrypt_password, decrypt_password
from backend.config.settings import get_settings
import uuid
import datetime

logger = logging.getLogger(__name__)


class ServerService:
    """Service class for server management operations with SSH integration"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
    
    async def get_servers(self, skip: int = 0, limit: int = 100) -> List[ServerResponse]:
        """Get list of servers with pagination"""
        query = select(Server).offset(skip).limit(limit).order_by(Server.created_at.desc())
        result = await self.db.execute(query)
        servers = result.scalars().all()
        
        return [ServerResponse.model_validate(server) for server in servers]
    
    async def count_servers(self) -> int:
        """Get total count of servers"""
        query = select(func.count(Server.id))
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def get_server(self, server_id: str) -> Optional[ServerResponse]:
        """Get server by ID"""
        query = select(Server).where(Server.id == server_id)
        result = await self.db.execute(query)
        server = result.scalar_one_or_none()
        
        if server:
            return ServerResponse.model_validate(server)
        return None
    
    async def create_server(self, server_data: ServerCreate) -> ServerResponse:
        """Create a new server configuration"""
        # Generate unique ID
        server_id = str(uuid.uuid4())
        
        # Encrypt sensitive data
        encrypted_password = None
        encrypted_key = None
        
        if server_data.password:
            encrypted_password = encrypt_password(server_data.password)
        
        if server_data.private_key:
            encrypted_key = encrypt_password(server_data.private_key)
        
        # Create server instance
        server = Server(
            id=server_id,
            hostname=server_data.hostname,
            username=server_data.username,
            port=server_data.port,
            description=server_data.description,
            os_type=server_data.os_type or OSType.LINUX,
            password=encrypted_password,
            private_key=encrypted_key,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow()
        )
        
        self.db.add(server)
        await self.db.commit()
        await self.db.refresh(server)
        
        logger.info(f"Created server: {server.hostname} ({server_id})")
        return ServerResponse.model_validate(server)
    
    async def update_server(self, server_id: str, server_data: ServerUpdate) -> Optional[ServerResponse]:
        """Update server configuration"""
        query = select(Server).where(Server.id == server_id)
        result = await self.db.execute(query)
        server = result.scalar_one_or_none()
        
        if not server:
            return None
        
        # Update fields that are provided
        update_data = server_data.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            if field == "password" and value:
                server.password = encrypt_password(value)
            elif field == "private_key" and value:
                server.private_key = encrypt_password(value)
            elif hasattr(server, field):
                setattr(server, field, value)
        
        server.updated_at = datetime.datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(server)
        
        logger.info(f"Updated server: {server.hostname} ({server_id})")
        return ServerResponse.model_validate(server)
    
    async def delete_server(self, server_id: str) -> bool:
        """Delete server configuration"""
        query = select(Server).where(Server.id == server_id)
        result = await self.db.execute(query)
        server = result.scalar_one_or_none()
        
        if not server:
            return False
        
        # Disconnect any active SSH connections
        try:
            manager = await ssh_factory.get_manager(server_id)
            await manager.disconnect()
        except Exception as e:
            logger.warning(f"Error disconnecting SSH for deleted server {server_id}: {e}")
        
        await self.db.delete(server)
        await self.db.commit()
        
        logger.info(f"Deleted server: {server.hostname} ({server_id})")
        return True
    
    async def test_connection(self, server_id: str) -> Dict[str, Any]:
        """Test SSH connection to server"""
        server = await self.get_server(server_id)
        if not server:
            raise ServerNotFoundError(server_id)
        
        try:
            # Get SSH manager and connect
            manager = await self._get_ssh_manager(server_id)
            
            # Test connection
            result = await manager.test_connection()
            
            # Update connection status in database
            await self._update_connection_status(server_id, "connected")
            
            logger.info(f"Connection test successful for {server.hostname}")
            return result
            
        except SSHConnectionError as e:
            # Update connection status as failed
            await self._update_connection_status(server_id, "failed")
            logger.error(f"Connection test failed for {server_id}: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "server_info": {
                    "hostname": server.hostname,
                    "port": server.port,
                    "connected": False
                }
            }
        except Exception as e:
            await self._update_connection_status(server_id, "failed")
            logger.error(f"Unexpected error during connection test for {server_id}: {e}")
            raise SSHConnectionError(f"Connection test failed: {str(e)}")
    
    async def get_server_context(self, server_id: str) -> Dict[str, Any]:
        """Get server context for AI command generation"""
        server = await self.get_server(server_id)
        if not server:
            raise ServerNotFoundError(server_id)
        
        try:
            # Get SSH manager and connect
            manager = await self._get_ssh_manager(server_id)
            
            # Gather system information
            system_info = await manager.gather_system_info()
            
            # Build comprehensive context
            context = {
                "server_id": server_id,
                "hostname": server.hostname,
                "os_type": server.os_type,
                "username": server.username,
                "port": server.port,
                "description": server.description,
                "system_info": system_info,
                "capabilities": {
                    "package_manager": system_info.get("package_manager", "unknown"),
                    "shell": system_info.get("shell", "/bin/bash"),
                    "architecture": system_info.get("architecture", "unknown"),
                    "os_version": system_info.get("os_release", "unknown")
                },
                "current_state": {
                    "working_directory": system_info.get("working_dir", "/"),
                    "user": system_info.get("user", server.username),
                    "uptime": system_info.get("uptime", "unknown")
                }
            }
            
            # Update connection status
            await self._update_connection_status(server_id, "connected")
            
            logger.info(f"Successfully gathered context for {server.hostname}")
            return context
            
        except SSHConnectionError as e:
            logger.error(f"Failed to gather context for {server_id}: {e}")
            await self._update_connection_status(server_id, "failed")
            
            # Return basic context without system info
            return {
                "server_id": server_id,
                "hostname": server.hostname,
                "os_type": server.os_type,
                "username": server.username,
                "port": server.port,
                "description": server.description,
                "error": f"Could not connect to gather system info: {str(e)}",
                "system_info": {},
                "capabilities": {
                    "package_manager": self._guess_package_manager(OSType(server.os_type)),
                    "shell": "/bin/bash",
                    "architecture": "unknown",
                    "os_version": "unknown"
                }
            }
    
    async def execute_command(
        self, 
        server_id: str, 
        command: str, 
        working_dir: Optional[str] = None,
        timeout: int = 30,
        safety_level: Optional[SafetyLevel] = None
    ) -> Dict[str, Any]:
        """Execute command on server via SSH"""
        server = await self.get_server(server_id)
        if not server:
            raise ServerNotFoundError(server_id)
        
        try:
            # Get SSH manager
            manager = await self._get_ssh_manager(server_id)
            
            # Set safety level if provided
            if safety_level:
                manager.set_safety_level(safety_level)
            
            # Execute command
            result = await manager.execute_command(
                command=command,
                working_dir=working_dir,
                timeout=timeout
            )
            
            # Update connection status
            await self._update_connection_status(server_id, "connected")
            
            logger.info(f"Command executed on {server.hostname}: {command}")
            return result.to_dict()
            
        except SSHConnectionError as e:
            logger.error(f"Command execution failed on {server_id}: {e}")
            await self._update_connection_status(server_id, "failed")
            raise
        except Exception as e:
            logger.error(f"Unexpected error executing command on {server_id}: {e}")
            raise SSHConnectionError(f"Command execution failed: {str(e)}")
    
    async def get_system_info(self, server_id: str) -> Dict[str, Any]:
        """Get detailed system information from server"""
        server = await self.get_server(server_id)
        if not server:
            raise ServerNotFoundError(server_id)
        
        try:
            manager = await self._get_ssh_manager(server_id)
            system_info = await manager.gather_system_info()
            
            await self._update_connection_status(server_id, "connected")
            
            return {
                "server_id": server_id,
                "hostname": server.hostname,
                "collected_at": datetime.datetime.utcnow().isoformat(),
                **system_info
            }
            
        except Exception as e:
            logger.error(f"Failed to get system info for {server_id}: {e}")
            await self._update_connection_status(server_id, "failed")
            raise SSHConnectionError(f"Failed to get system info: {str(e)}")
    
    async def _get_ssh_manager(self, server_id: str):
        """Get SSH manager and ensure connection"""
        # Get server data
        query = select(Server).where(Server.id == server_id)
        result = await self.db.execute(query)
        server = result.scalar_one_or_none()
        
        if not server:
            raise ServerNotFoundError(server_id)
        
        # Prepare server data for SSH connection
        server_data = {
            "hostname": server.hostname,
            "username": server.username,
            "port": server.port,
            "password": server.password,  # Will be decrypted by ssh_factory
            "timeout": self.settings.ssh_timeout
        }
        
        # Get connected manager
        manager = await ssh_factory.connect_to_server(server_id, server_data)
        return manager
    
    def _guess_package_manager(self, os_type: OSType) -> str:
        """Guess package manager based on OS type"""
        package_managers = {
            OSType.UBUNTU: "apt",
            OSType.DEBIAN: "apt", 
            OSType.CENTOS: "yum",
            OSType.RHEL: "yum",
            OSType.ALPINE: "apk",
            OSType.MACOS: "brew",
        }
        return package_managers.get(os_type, "unknown")
    
    async def _update_connection_status(self, server_id: str, status: str):
        """Update server connection status and timestamp"""
        query = select(Server).where(Server.id == server_id)
        result = await self.db.execute(query)
        server = result.scalar_one_or_none()
        
        if server:
            server.connection_status = status
            server.last_connected = datetime.datetime.utcnow()
            await self.db.commit()
    
    async def disconnect_server(self, server_id: str) -> bool:
        """Manually disconnect SSH connection for a server"""
        try:
            manager = await ssh_factory.get_manager(server_id)
            await manager.disconnect()
            await self._update_connection_status(server_id, "disconnected")
            logger.info(f"Disconnected from server: {server_id}")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting from server {server_id}: {e}")
            return False
    
    async def cleanup_connections(self):
        """Clean up inactive SSH connections"""
        try:
            await ssh_factory.cleanup_inactive()
            logger.info("SSH connection cleanup completed")
        except Exception as e:
            logger.error(f"Error during SSH cleanup: {e}")