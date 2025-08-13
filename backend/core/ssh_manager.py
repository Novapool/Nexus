"""
SSH connection management for server operations
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
import asyncssh
from asyncssh import SSHClientConnection, SSHClientProcess
from backend.models.schemas import OSType, SafetyLevel
from backend.utils.crypto import decrypt_password
from backend.core.exceptions import SSHConnectionError
import json
import time

logger = logging.getLogger(__name__)


@dataclass
class SSHConfig:
    """SSH connection configuration"""
    hostname: str
    username: str
    port: int = 22
    password: Optional[str] = None
    private_key: Optional[str] = None
    timeout: int = 30


@dataclass
class CommandResult:
    """Result of command execution"""
    command: str
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float
    working_directory: str
    success: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "command": self.command,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "execution_time": self.execution_time,
            "working_directory": self.working_directory,
            "success": self.success
        }


class SSHManager:
    """Manages SSH connections and command execution"""
    
    def __init__(self):
        self._connection: Optional[SSHClientConnection] = None
        self._connection_info: Optional[SSHConfig] = None
        self._last_used: float = 0
        self._connection_timeout = 300  # 5 minutes
        self.safety_level = SafetyLevel.CAUTIOUS
        
    async def connect(self, config: SSHConfig) -> bool:
        """Establish SSH connection to server"""
        try:
            logger.info(f"Connecting to {config.hostname}:{config.port} as {config.username}")
            
            # Close existing connection if different server
            if (self._connection and self._connection_info and 
                (self._connection_info.hostname != config.hostname or 
                 self._connection_info.username != config.username)):
                await self.disconnect()
            
            # Check if we already have a valid connection
            if self._connection:
                # Test the connection
                try:
                    await asyncio.wait_for(
                        self._connection.run("echo test", check=True),
                        timeout=5
                    )
                    self._last_used = time.time()
                    logger.debug(f"Reusing existing connection to {config.hostname}")
                    return True
                except Exception:
                    logger.debug("Existing connection is stale, reconnecting")
                    await self.disconnect()
            
            # Prepare connection arguments
            connect_kwargs = {
                'host': config.hostname,
                'port': config.port,
                'username': config.username,
                'known_hosts': None,  # For development - in production, manage known_hosts properly
                'connect_timeout': config.timeout,
            }
            
            # Use password authentication for now
            if config.password:
                connect_kwargs['password'] = config.password
            else:
                raise SSHConnectionError("No password provided for authentication")
            
            # Establish connection
            self._connection = await asyncio.wait_for(
                asyncssh.connect(**connect_kwargs),
                timeout=config.timeout
            )
            
            self._connection_info = config
            self._last_used = time.time()
            
            logger.info(f"Successfully connected to {config.hostname}")
            return True
            
        except asyncio.TimeoutError:
            logger.error(f"Connection timeout to {config.hostname}:{config.port}")
            raise SSHConnectionError(f"Connection timeout to {config.hostname}")
        except asyncssh.PermissionDenied:
            logger.error(f"Authentication failed for {config.username}@{config.hostname}")
            raise SSHConnectionError("Authentication failed - invalid credentials")
        except asyncssh.ConnectionLost as e:
            logger.error(f"Connection lost to {config.hostname}: {e}")
            raise SSHConnectionError(f"Connection lost: {str(e)}")
        except Exception as e:
            logger.error(f"SSH connection failed to {config.hostname}: {e}")
            raise SSHConnectionError(f"SSH connection failed: {str(e)}")
    
    async def disconnect(self):
        """Close SSH connection"""
        if self._connection:
            try:
                self._connection.close()
                await self._connection.wait_closed()
                logger.debug("SSH connection closed")
            except Exception as e:
                logger.warning(f"Error closing SSH connection: {e}")
        
        self._connection = None
        self._connection_info = None
        self._last_used = 0
    
    def is_connected(self) -> bool:
        """Check if SSH connection is active"""
        if not self._connection:
            return False
        
        # Check connection timeout
        if time.time() - self._last_used > self._connection_timeout:
            logger.debug("Connection timed out")
            return False
        
        # For AsyncSSH 2.14.2, we can't easily check if connection is closed
        # without making a call, so we assume it's connected if we have a connection
        # object and it hasn't timed out. The actual test will happen when we try to use it.
        return True
    
    async def execute_command(
        self, 
        command: str, 
        working_dir: str = None,
        timeout: int = 30,
        safety_level: SafetyLevel = None
    ) -> CommandResult:
        """Execute command on remote server"""
        
        if not self.is_connected():
            raise SSHConnectionError("Not connected to any server")
        
        # Use provided safety level or instance default
        current_safety = safety_level or self.safety_level
        
        # Handle paranoid mode (equivalent to dry run)
        if current_safety == SafetyLevel.PARANOID:
            logger.info(f"PARANOID MODE: Would execute: {command}")
            return CommandResult(
                command=command,
                stdout=f"PARANOID MODE: Command would be executed: {command}",
                stderr="",
                exit_code=0,
                execution_time=0.0,
                working_directory=working_dir or "/",
                success=True
            )
        
        start_time = time.time()
        
        try:
            logger.info(f"Executing command: {command}")
            
            # Prepare command with working directory if specified
            if working_dir:
                full_command = f"cd {working_dir} && {command}"
            else:
                full_command = command
            
            # Execute command
            result = await asyncio.wait_for(
                self._connection.run(full_command, check=False),
                timeout=timeout
            )
            
            execution_time = time.time() - start_time
            self._last_used = time.time()
            
            # Create result object
            command_result = CommandResult(
                command=command,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.exit_status,
                execution_time=execution_time,
                working_directory=working_dir or await self.get_working_directory(),
                success=result.exit_status == 0
            )
            
            if command_result.success:
                logger.info(f"Command executed successfully (exit code: {result.exit_status})")
            else:
                logger.warning(f"Command failed with exit code: {result.exit_status}")
                if result.stderr:
                    logger.warning(f"Error output: {result.stderr}")
            
            return command_result
            
        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.error(f"Command timeout after {execution_time:.2f}s: {command}")
            raise SSHConnectionError(f"Command execution timeout: {command}")
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Command execution failed after {execution_time:.2f}s: {e}")
            raise SSHConnectionError(f"Command execution failed: {str(e)}")
    
    async def get_working_directory(self) -> str:
        """Get current working directory"""
        try:
            result = await self._connection.run("pwd", check=True)
            return result.stdout.strip()
        except Exception:
            return "/"
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test SSH connection and gather basic info"""
        if not self.is_connected():
            raise SSHConnectionError("Not connected to any server")
        
        try:
            start_time = time.time()
            
            # Test basic connectivity
            result = await asyncio.wait_for(
                self._connection.run("echo 'Connection test successful'", check=True),
                timeout=10
            )
            
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            return {
                "success": True,
                "response_time_ms": round(response_time, 2),
                "test_output": result.stdout.strip(),
                "server_info": {
                    "hostname": self._connection_info.hostname if self._connection_info else "unknown",
                    "port": self._connection_info.port if self._connection_info else 22,
                    "username": self._connection_info.username if self._connection_info else "unknown",
                    "connected": True
                }
            }
            
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            raise SSHConnectionError(f"Connection test failed: {str(e)}")
    
    async def gather_system_info(self) -> Dict[str, Any]:
        """Gather comprehensive system information"""
        if not self.is_connected():
            raise SSHConnectionError("Not connected to any server")
        
        try:
            logger.info("Gathering system information")
            
            # Define system information commands
            info_commands = {
                "hostname": "hostname",
                "os_release": "cat /etc/os-release 2>/dev/null || echo 'OS info unavailable'",
                "kernel": "uname -r",
                "architecture": "uname -m",
                "cpu_info": "nproc",
                "memory_info": "free -m | grep '^Mem:' | awk '{print $2}'",
                "disk_usage": "df -h / | tail -1 | awk '{print $5}'",
                "uptime": "uptime -p 2>/dev/null || uptime",
                "shell": "echo $SHELL",
                "user": "whoami",
                "working_dir": "pwd"
            }
            
            system_info = {}
            
            # Execute commands and gather results
            for key, command in info_commands.items():
                try:
                    result = await self.execute_command(command, timeout=10)
                    if result.success:
                        system_info[key] = result.stdout.strip()
                    else:
                        system_info[key] = f"Error: {result.stderr}"
                        logger.warning(f"Failed to get {key}: {result.stderr}")
                except Exception as e:
                    system_info[key] = f"Error: {str(e)}"
                    logger.warning(f"Failed to get {key}: {e}")
            
            # Try to detect package manager
            package_manager = await self._detect_package_manager()
            system_info["package_manager"] = package_manager
            
            # Try to detect OS type
            os_type = self._detect_os_type(system_info.get("os_release", ""))
            system_info["os_type"] = os_type.value
            
            logger.info("System information gathered successfully")
            return system_info
            
        except Exception as e:
            logger.error(f"Failed to gather system info: {e}")
            raise SSHConnectionError(f"Failed to gather system info: {str(e)}")
    
    async def _detect_package_manager(self) -> str:
        """Detect the system's package manager"""
        package_managers = [
            ("apt", "which apt"),
            ("yum", "which yum"),
            ("dnf", "which dnf"),
            ("apk", "which apk"),
            ("pacman", "which pacman"),
            ("zypper", "which zypper")
        ]
        
        for pm_name, command in package_managers:
            try:
                result = await self.execute_command(command, timeout=5)
                if result.success:
                    return pm_name
            except Exception:
                continue
        
        return "unknown"
    
    def _detect_os_type(self, os_release: str) -> OSType:
        """Detect OS type from /etc/os-release"""
        os_release_lower = os_release.lower()
        
        if "ubuntu" in os_release_lower:
            return OSType.UBUNTU
        elif "debian" in os_release_lower:
            return OSType.DEBIAN
        elif "centos" in os_release_lower:
            return OSType.CENTOS
        elif "red hat" in os_release_lower or "rhel" in os_release_lower:
            return OSType.RHEL
        elif "alpine" in os_release_lower:
            return OSType.ALPINE
        else:
            return OSType.LINUX
    
    def set_safety_level(self, level: SafetyLevel):
        """Set command execution safety level"""
        self.safety_level = level
        logger.info(f"Safety level set to: {level.value}")
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()


class SSHManagerFactory:
    """Factory for creating and managing SSH connections"""
    
    def __init__(self):
        self._managers: Dict[str, SSHManager] = {}
    
    async def get_manager(self, server_id: str) -> SSHManager:
        """Get or create SSH manager for server"""
        if server_id not in self._managers:
            self._managers[server_id] = SSHManager()
        
        return self._managers[server_id]
    
    async def connect_to_server(self, server_id: str, server_data: Dict[str, Any]) -> SSHManager:
        """Connect to server using provided configuration"""
        manager = await self.get_manager(server_id)
        
        # Decrypt password if provided
        password = None
        if server_data.get("password"):
            try:
                password = decrypt_password(server_data["password"])
            except Exception as e:
                logger.error(f"Failed to decrypt password for server {server_id}: {e}")
                raise SSHConnectionError("Failed to decrypt server password")
        
        # Create SSH config
        config = SSHConfig(
            hostname=server_data["hostname"],
            username=server_data["username"],
            port=server_data.get("port", 22),
            password=password,
            timeout=server_data.get("timeout", 30)
        )
        
        # Connect
        await manager.connect(config)
        return manager
    
    async def disconnect_all(self):
        """Disconnect all SSH connections"""
        for manager in self._managers.values():
            await manager.disconnect()
        
        self._managers.clear()
    
    async def cleanup_inactive(self):
        """Clean up inactive connections"""
        inactive_servers = []
        
        for server_id, manager in self._managers.items():
            if not manager.is_connected():
                inactive_servers.append(server_id)
        
        for server_id in inactive_servers:
            await self._managers[server_id].disconnect()
            del self._managers[server_id]
        
        if inactive_servers:
            logger.info(f"Cleaned up {len(inactive_servers)} inactive SSH connections")


# Global SSH manager factory instance
ssh_factory = SSHManagerFactory()
