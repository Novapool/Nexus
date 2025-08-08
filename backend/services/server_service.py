"""
Server management business logic service
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
from backend.utils.crypto import encrypt_password, decrypt_password
import uuid
import datetime

logger = logging.getLogger(__name__)


class ServerService:
    """Service class for server management operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
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
            # TODO: Implement actual SSH connection test
            # This is a placeholder that simulates connection testing
            await asyncio.sleep(0.1)  # Simulate network delay
            
            # For now, return a mock successful connection
            connection_result = {
                "success": True,
                "response_time_ms": 50,
                "server_info": {
                    "hostname": server.hostname,
                    "port": server.port,
                    "reachable": True
                },
                "tested_at": datetime.datetime.utcnow().isoformat()
            }
            
            # Update last_connected timestamp
            await self._update_connection_status(server_id, "connected")
            
            return connection_result
            
        except Exception as e:
            logger.error(f"Connection test failed for {server_id}: {e}")
            await self._update_connection_status(server_id, "failed")
            raise SSHConnectionError(f"Connection test failed: {str(e)}")
    
    async def get_server_context(self, server_id: str) -> Dict[str, Any]:
        """Get server context for AI command generation"""
        server = await self.get_server(server_id)
        if not server:
            raise ServerNotFoundError(server_id)
        
        # TODO: Implement actual system information gathering
        # This would require SSH connection to gather real system info
        context = {
            "hostname": server.hostname,
            "os_type": server.os_type,
            "username": server.username,
            "port": server.port,
            "description": server.description,
            # Mock system info - replace with real data later
            "system_info": {
                "architecture": "x86_64",
                "kernel": "Linux 5.4.0",
                "shell": "/bin/bash",
                "package_manager": self._guess_package_manager(server.os_type),
                "available_commands": ["ls", "cd", "mkdir", "rm", "cp", "mv", "nano", "vim"]
            }
        }
        
        return context
    
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