"""
Server detection and system profiling service
"""

import asyncio
import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from backend.models.database import Server
from backend.models.schemas import OSType
from backend.core.ssh_manager import ssh_factory
from backend.core.exceptions import ServerNotFoundError, SSHConnectionError

logger = logging.getLogger(__name__)


class SystemProfile:
    """System profile data container"""
    def __init__(self):
        self.os_family: str = "unknown"
        self.os_distribution: str = "unknown"
        self.os_version: str = "unknown"
        self.kernel_version: str = "unknown"
        self.architecture: str = "unknown"
        self.package_manager: str = "unknown"
        self.init_system: str = "unknown"
        self.hostname: str = "unknown"
        self.last_scanned: datetime = datetime.utcnow()
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "os_family": self.os_family,
            "os_distribution": self.os_distribution,
            "os_version": self.os_version,
            "kernel_version": self.kernel_version,
            "architecture": self.architecture,
            "package_manager": self.package_manager,
            "init_system": self.init_system,
            "hostname": self.hostname,
            "last_scanned": self.last_scanned.isoformat()
        }


class HardwareProfile:
    """Hardware profile data container"""
    def __init__(self):
        self.cpu_count: int = 0
        self.cpu_model: str = "unknown"
        self.memory_total_mb: int = 0
        self.memory_available_mb: int = 0
        self.swap_total_mb: int = 0
        self.storage_devices: List[Dict] = []
        self.gpu_devices: List[Dict] = []
        self.network_interfaces: List[Dict] = []
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpu_count": self.cpu_count,
            "cpu_model": self.cpu_model,
            "memory_total_mb": self.memory_total_mb,
            "memory_available_mb": self.memory_available_mb,
            "swap_total_mb": self.swap_total_mb,
            "storage_devices": self.storage_devices,
            "gpu_devices": self.gpu_devices,
            "network_interfaces": self.network_interfaces
        }


class ServiceProfile:
    """Service and capability profile"""
    def __init__(self):
        self.has_docker: bool = False
        self.docker_version: Optional[str] = None
        self.has_systemd: bool = False
        self.systemd_version: Optional[str] = None
        self.has_sudo: bool = False
        self.firewall_type: Optional[str] = None
        self.listening_ports: List[Dict] = []
        self.running_services: List[str] = []
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_docker": self.has_docker,
            "docker_version": self.docker_version,
            "has_systemd": self.has_systemd,
            "systemd_version": self.systemd_version,
            "has_sudo": self.has_sudo,
            "firewall_type": self.firewall_type,
            "listening_ports": self.listening_ports,
            "running_services": self.running_services
        }


class ServerDetectionService:
    """Service for detecting and profiling server systems"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def perform_initial_scan(self, server_id: str, scan_type: str = "full") -> Dict[str, Any]:
        """
        Perform comprehensive initial server scan
        
        Args:
            server_id: Server ID to scan
            scan_type: Type of scan - 'quick', 'full', 'hardware', 'software'
        
        Returns:
            Complete scan results dictionary
        """
        logger.info(f"Starting {scan_type} scan for server {server_id}")
        
        # Get server from database
        server = await self._get_server(server_id)
        if not server:
            raise ServerNotFoundError(server_id)
        
        # Get SSH manager
        manager = await self._get_ssh_manager(server_id, server)
        
        scan_results = {
            "server_id": server_id,
            "scan_type": scan_type,
            "scan_timestamp": datetime.utcnow().isoformat(),
            "success": False,
            "error": None
        }
        
        try:
            # Perform scans based on type
            if scan_type in ["quick", "full"]:
                system_profile = await self._scan_system_profile(manager)
                scan_results["system_profile"] = system_profile.to_dict()
            
            if scan_type in ["hardware", "full"]:
                hardware_profile = await self._scan_hardware(manager)
                scan_results["hardware_profile"] = hardware_profile.to_dict()
            
            if scan_type in ["software", "full"]:
                service_profile = await self._scan_services(manager)
                scan_results["service_profile"] = service_profile.to_dict()
            
            scan_results["success"] = True
            
            # Update server record with scan results
            await self._update_server_scan_data(server_id, scan_results)
            
            logger.info(f"Completed {scan_type} scan for server {server_id}")
            
        except Exception as e:
            logger.error(f"Scan failed for server {server_id}: {e}")
            scan_results["error"] = str(e)
        
        return scan_results
    
    async def _scan_system_profile(self, manager) -> SystemProfile:
        """Scan basic system information"""
        profile = SystemProfile()
        
        # OS Detection commands
        commands = {
            "os_release": "cat /etc/os-release 2>/dev/null || echo 'not available'",
            "lsb_release": "lsb_release -a 2>/dev/null || echo 'not available'",
            "uname": "uname -a",
            "hostname": "hostname",
            "kernel": "uname -r",
            "arch": "uname -m"
        }
        
        results = await self._execute_commands(manager, commands)
        
        # Parse OS information
        os_release = results.get("os_release", "")
        if "ubuntu" in os_release.lower():
            profile.os_family = "debian"
            profile.os_distribution = "ubuntu"
        elif "debian" in os_release.lower():
            profile.os_family = "debian"
            profile.os_distribution = "debian"
        elif "centos" in os_release.lower():
            profile.os_family = "rhel"
            profile.os_distribution = "centos"
        elif "red hat" in os_release.lower() or "rhel" in os_release.lower():
            profile.os_family = "rhel"
            profile.os_distribution = "rhel"
        elif "alpine" in os_release.lower():
            profile.os_family = "alpine"
            profile.os_distribution = "alpine"
        else:
            profile.os_family = "linux"
            profile.os_distribution = "unknown"
        
        # Extract version
        for line in os_release.split('\n'):
            if 'VERSION_ID=' in line:
                profile.os_version = line.split('=')[1].strip('"')
                break
        
        profile.kernel_version = results.get("kernel", "unknown").strip()
        profile.architecture = results.get("arch", "unknown").strip()
        profile.hostname = results.get("hostname", "unknown").strip()
        
        # Detect package manager
        profile.package_manager = await self._detect_package_manager(manager)
        
        # Detect init system
        profile.init_system = await self._detect_init_system(manager)
        
        return profile
    
    async def _scan_hardware(self, manager) -> HardwareProfile:
        """Scan hardware information"""
        profile = HardwareProfile()
        
        commands = {
            "cpu_count": "nproc",
            "cpu_model": "cat /proc/cpuinfo | grep 'model name' | head -1 | cut -d: -f2",
            "memory": "free -m",
            "disk": "df -h",
            "block_devices": "lsblk -J 2>/dev/null || lsblk",
            "gpu_nvidia": "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo 'no nvidia'",
            "gpu_amd": "lspci | grep -i 'vga\\|3d\\|display' || echo 'no gpu'",
            "network": "ip -j addr show 2>/dev/null || ip addr show"
        }
        
        results = await self._execute_commands(manager, commands)
        
        # Parse CPU info
        try:
            profile.cpu_count = int(results.get("cpu_count", "0").strip())
        except:
            profile.cpu_count = 0
        
        profile.cpu_model = results.get("cpu_model", "unknown").strip()
        
        # Parse memory info
        memory_output = results.get("memory", "")
        for line in memory_output.split('\n'):
            if line.startswith('Mem:'):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        profile.memory_total_mb = int(parts[1])
                        if len(parts) >= 7:
                            profile.memory_available_mb = int(parts[6])
                    except:
                        pass
            elif line.startswith('Swap:'):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        profile.swap_total_mb = int(parts[1])
                    except:
                        pass
        
        # Parse disk info
        disk_output = results.get("disk", "")
        storage_devices = []
        for line in disk_output.split('\n')[1:]:  # Skip header
            parts = line.split()
            if len(parts) >= 6 and not line.startswith('tmpfs'):
                storage_devices.append({
                    "filesystem": parts[0],
                    "size": parts[1],
                    "used": parts[2],
                    "available": parts[3],
                    "use_percent": parts[4],
                    "mount_point": parts[5]
                })
        profile.storage_devices = storage_devices
        
        # Parse GPU info
        gpu_devices = []
        nvidia_output = results.get("gpu_nvidia", "")
        if "no nvidia" not in nvidia_output.lower():
            for line in nvidia_output.strip().split('\n'):
                if line:
                    parts = line.split(',')
                    if len(parts) >= 2:
                        gpu_devices.append({
                            "type": "nvidia",
                            "name": parts[0].strip(),
                            "memory": parts[1].strip()
                        })
        
        amd_output = results.get("gpu_amd", "")
        if "no gpu" not in amd_output.lower():
            for line in amd_output.split('\n'):
                if 'vga' in line.lower() or '3d' in line.lower():
                    gpu_devices.append({
                        "type": "detected",
                        "info": line.strip()
                    })
        
        profile.gpu_devices = gpu_devices
        
        # Parse network interfaces (simplified)
        network_output = results.get("network", "")
        interfaces = []
        current_interface = None
        
        for line in network_output.split('\n'):
            if line and not line.startswith(' '):
                # New interface
                parts = line.split(':')
                if len(parts) >= 2:
                    current_interface = {
                        "name": parts[1].strip().split()[0] if len(parts[1].strip().split()) > 0 else "unknown",
                        "addresses": []
                    }
                    interfaces.append(current_interface)
            elif current_interface and 'inet ' in line:
                # IPv4 address
                parts = line.strip().split()
                for i, part in enumerate(parts):
                    if part == 'inet' and i + 1 < len(parts):
                        current_interface["addresses"].append({
                            "type": "ipv4",
                            "address": parts[i + 1]
                        })
        
        profile.network_interfaces = interfaces
        
        return profile
    
    async def _scan_services(self, manager) -> ServiceProfile:
        """Scan services and capabilities"""
        profile = ServiceProfile()
        
        commands = {
            "docker": "docker --version 2>/dev/null || echo 'no docker'",
            "systemd": "systemctl --version 2>/dev/null | head -1 || echo 'no systemd'",
            "sudo": "sudo -V 2>/dev/null | head -1 || echo 'no sudo'",
            "firewall_ufw": "ufw status 2>/dev/null | head -1 || echo 'no ufw'",
            "firewall_iptables": "iptables -V 2>/dev/null || echo 'no iptables'",
            "ports": "ss -tuln 2>/dev/null | grep LISTEN || netstat -tuln 2>/dev/null | grep LISTEN || echo 'no ports'"
        }
        
        results = await self._execute_commands(manager, commands)
        
        # Check Docker
        docker_output = results.get("docker", "")
        if "no docker" not in docker_output.lower():
            profile.has_docker = True
            if "version" in docker_output.lower():
                profile.docker_version = docker_output.strip()
        
        # Check systemd
        systemd_output = results.get("systemd", "")
        if "no systemd" not in systemd_output.lower():
            profile.has_systemd = True
            profile.systemd_version = systemd_output.strip()
        
        # Check sudo
        sudo_output = results.get("sudo", "")
        if "no sudo" not in sudo_output.lower():
            profile.has_sudo = True
        
        # Check firewall
        ufw_output = results.get("firewall_ufw", "")
        iptables_output = results.get("firewall_iptables", "")
        
        if "no ufw" not in ufw_output.lower() and "inactive" not in ufw_output.lower():
            profile.firewall_type = "ufw"
        elif "no iptables" not in iptables_output.lower():
            profile.firewall_type = "iptables"
        
        # Parse listening ports
        ports_output = results.get("ports", "")
        listening_ports = []
        
        if "no ports" not in ports_output.lower():
            for line in ports_output.split('\n'):
                parts = line.split()
                if len(parts) >= 5:
                    # Extract port from address (e.g., "0.0.0.0:22" -> "22")
                    addr = parts[3] if 'ss' in line else parts[3]
                    if ':' in addr:
                        port = addr.split(':')[-1]
                        protocol = parts[0] if 'ss' not in line else parts[0].lower().replace('listen', '').strip()
                        listening_ports.append({
                            "port": port,
                            "protocol": protocol or "tcp",
                            "address": addr
                        })
        
        profile.listening_ports = listening_ports
        
        # Get running services if systemd is available
        if profile.has_systemd:
            try:
                result = await manager.execute_command(
                    "systemctl list-units --type=service --state=running --no-pager --no-legend | head -20",
                    timeout=10
                )
                if result.success:
                    services = []
                    for line in result.stdout.split('\n'):
                        if line.strip():
                            service_name = line.split()[0]
                            if service_name.endswith('.service'):
                                services.append(service_name[:-8])  # Remove .service suffix
                    profile.running_services = services[:20]  # Limit to 20 services
            except:
                pass
        
        return profile
    
    async def _detect_package_manager(self, manager) -> str:
        """Detect the system's package manager"""
        package_managers = [
            ("apt", "which apt"),
            ("yum", "which yum"),
            ("dnf", "which dnf"),
            ("apk", "which apk"),
            ("pacman", "which pacman"),
            ("zypper", "which zypper"),
            ("brew", "which brew")
        ]
        
        for pm_name, command in package_managers:
            try:
                result = await manager.execute_command(command, timeout=5)
                if result.success and result.stdout.strip():
                    return pm_name
            except:
                continue
        
        return "unknown"
    
    async def _detect_init_system(self, manager) -> str:
        """Detect the system's init system"""
        try:
            # Check for systemd
            result = await manager.execute_command("pidof systemd", timeout=5)
            if result.success and result.stdout.strip():
                return "systemd"
            
            # Check for upstart
            result = await manager.execute_command("initctl version 2>/dev/null", timeout=5)
            if result.success and "upstart" in result.stdout.lower():
                return "upstart"
            
            # Check for sysvinit
            result = await manager.execute_command("ls /etc/init.d/ 2>/dev/null", timeout=5)
            if result.success and result.stdout.strip():
                return "sysvinit"
            
            # Check for openrc
            result = await manager.execute_command("rc-status 2>/dev/null", timeout=5)
            if result.success:
                return "openrc"
                
        except:
            pass
        
        return "unknown"
    
    async def _execute_commands(self, manager, commands: Dict[str, str]) -> Dict[str, str]:
        """Execute multiple commands and return results"""
        results = {}
        
        for key, command in commands.items():
            try:
                result = await manager.execute_command(command, timeout=10)
                if result.success:
                    results[key] = result.stdout
                else:
                    results[key] = result.stderr or "command failed"
            except Exception as e:
                logger.warning(f"Command '{key}' failed: {e}")
                results[key] = f"error: {str(e)}"
        
        return results
    
    async def _get_server(self, server_id: str) -> Optional[Server]:
        """Get server from database"""
        query = select(Server).where(Server.id == server_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def _get_ssh_manager(self, server_id: str, server: Server):
        """Get SSH manager for server"""
        from backend.utils.crypto import decrypt_password
        
        # Prepare server data
        server_data = {
            "hostname": server.hostname,
            "username": server.username,
            "port": server.port,
            "password": server.password,
            "timeout": 30
        }
        
        # Connect and return manager
        return await ssh_factory.connect_to_server(server_id, server_data)
    
    async def _update_server_scan_data(self, server_id: str, scan_results: Dict[str, Any]):
        """Update server record with scan data"""
        try:
            # Store scan results in a JSON column (we'll add this in migration)
            query = (
                update(Server)
                .where(Server.id == server_id)
                .values(
                    updated_at=datetime.utcnow(),
                    # We'll add system_info column in migration
                    # system_info=json.dumps(scan_results)
                )
            )
            await self.db.execute(query)
            await self.db.commit()
        except Exception as e:
            logger.error(f"Failed to update server scan data: {e}")
    
    async def validate_connection(self, server_id: str) -> Dict[str, Any]:
        """Validate server connection before operations"""
        logger.info(f"Validating connection for server {server_id}")
        
        server = await self._get_server(server_id)
        if not server:
            raise ServerNotFoundError(server_id)
        
        validation_result = {
            "server_id": server_id,
            "hostname": server.hostname,
            "connection_valid": False,
            "response_time_ms": None,
            "error": None,
            "checks": {}
        }
        
        try:
            manager = await self._get_ssh_manager(server_id, server)
            
            # Test basic connectivity
            import time
            start_time = time.time()
            test_result = await manager.test_connection()
            response_time = (time.time() - start_time) * 1000
            
            validation_result["connection_valid"] = test_result.get("success", False)
            validation_result["response_time_ms"] = round(response_time, 2)
            
            # Perform additional checks
            checks = {}
            
            # Check user permissions
            result = await manager.execute_command("id", timeout=5)
            checks["user_check"] = {
                "success": result.success,
                "user_info": result.stdout.strip() if result.success else None
            }
            
            # Check sudo access
            result = await manager.execute_command("sudo -n true 2>/dev/null", timeout=5)
            checks["sudo_access"] = {
                "available": result.success,
                "requires_password": not result.success
            }
            
            # Check disk space
            result = await manager.execute_command("df -h / | tail -1", timeout=5)
            if result.success:
                parts = result.stdout.strip().split()
                if len(parts) >= 5:
                    checks["disk_space"] = {
                        "available": True,
                        "usage_percent": parts[4],
                        "available_space": parts[3]
                    }
            
            validation_result["checks"] = checks
            
        except Exception as e:
            logger.error(f"Connection validation failed for {server_id}: {e}")
            validation_result["error"] = str(e)
        
        return validation_result
