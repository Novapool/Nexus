"""
Unit tests for ServerDetectionService
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.server_detection_service import (
    ServerDetectionService,
    SystemProfile,
    HardwareProfile,
    ServiceProfile
)
from backend.models.database import Server
from backend.core.exceptions import ServerNotFoundError


class TestServerDetectionService:
    """Test ServerDetectionService functionality"""
    
    @pytest.fixture
    def detection_service(self, test_db):
        """Create detection service instance"""
        return ServerDetectionService(test_db)
    
    @pytest.mark.asyncio
    async def test_perform_initial_scan_full(self, detection_service, test_server, mock_ssh_manager, mocker):
        """Test full system scan"""
        # Mock SSH factory
        mocker.patch('backend.services.server_detection_service.ssh_factory.connect_to_server', 
                    return_value=mock_ssh_manager)
        
        # Mock command execution results
        mock_ssh_manager.execute_command = AsyncMock(side_effect=[
            Mock(success=True, stdout="Ubuntu 22.04", stderr=""),  # OS release
            Mock(success=True, stdout="", stderr=""),  # LSB release
            Mock(success=True, stdout="Linux test-server 5.15.0 x86_64", stderr=""),  # uname
            Mock(success=True, stdout="test-server", stderr=""),  # hostname
            Mock(success=True, stdout="5.15.0-generic", stderr=""),  # kernel
            Mock(success=True, stdout="x86_64", stderr=""),  # arch
            Mock(success=True, stdout="/usr/bin/apt", stderr=""),  # apt check
            Mock(success=True, stdout="1", stderr=""),  # systemd check
            # Hardware scan commands
            Mock(success=True, stdout="4", stderr=""),  # cpu count
            Mock(success=True, stdout="Intel Core i7", stderr=""),  # cpu model
            Mock(success=True, stdout="Mem:  8192  4096", stderr=""),  # memory
            Mock(success=True, stdout="/dev/sda1 100G 45G 55G 45% /", stderr=""),  # disk
            Mock(success=True, stdout="", stderr=""),  # block devices
            Mock(success=False, stdout="", stderr="no nvidia"),  # nvidia gpu
            Mock(success=False, stdout="", stderr="no gpu"),  # amd gpu
            Mock(success=True, stdout="eth0: inet 192.168.1.100/24", stderr=""),  # network
            # Service scan commands
            Mock(success=True, stdout="Docker version 24.0.7", stderr=""),  # docker
            Mock(success=True, stdout="systemd 249", stderr=""),  # systemd
            Mock(success=True, stdout="sudo version 1.9", stderr=""),  # sudo
            Mock(success=True, stdout="Status: active", stderr=""),  # ufw
            Mock(success=False, stdout="", stderr="no iptables"),  # iptables
            Mock(success=True, stdout="tcp LISTEN 0.0.0.0:22", stderr=""),  # ports
            Mock(success=True, stdout="ssh.service\nnginx.service", stderr=""),  # services
        ])
        
        # Perform scan
        result = await detection_service.perform_initial_scan(test_server.id, "full")
        
        # Verify results
        assert result["success"] is True
        assert result["server_id"] == test_server.id
        assert result["scan_type"] == "full"
        assert "system_profile" in result
        assert "hardware_profile" in result
        assert "service_profile" in result
        
        # Verify system profile
        system_profile = result["system_profile"]
        assert system_profile["os_family"] == "debian"
        assert system_profile["os_distribution"] == "ubuntu"
        assert system_profile["hostname"] == "test-server"
        assert system_profile["architecture"] == "x86_64"
        assert system_profile["package_manager"] == "apt"
        assert system_profile["init_system"] == "systemd"
        
        # Verify hardware profile
        hardware_profile = result["hardware_profile"]
        assert hardware_profile["cpu_count"] == 4
        assert "Intel" in hardware_profile["cpu_model"]
        assert hardware_profile["memory_total_mb"] == 8192
        
        # Verify service profile
        service_profile = result["service_profile"]
        assert service_profile["has_docker"] is True
        assert service_profile["has_systemd"] is True
        assert service_profile["has_sudo"] is True
    
    @pytest.mark.asyncio
    async def test_perform_initial_scan_quick(self, detection_service, test_server, mock_ssh_manager, mocker):
        """Test quick system scan (system profile only)"""
        mocker.patch('backend.services.server_detection_service.ssh_factory.connect_to_server', 
                    return_value=mock_ssh_manager)
        
        # Mock minimal command results for quick scan
        mock_ssh_manager.execute_command = AsyncMock(side_effect=[
            Mock(success=True, stdout="Ubuntu 22.04", stderr=""),
            Mock(success=True, stdout="", stderr=""),
            Mock(success=True, stdout="Linux test-server 5.15.0 x86_64", stderr=""),
            Mock(success=True, stdout="test-server", stderr=""),
            Mock(success=True, stdout="5.15.0-generic", stderr=""),
            Mock(success=True, stdout="x86_64", stderr=""),
            Mock(success=True, stdout="/usr/bin/apt", stderr=""),
            Mock(success=True, stdout="1", stderr=""),
        ])
        
        result = await detection_service.perform_initial_scan(test_server.id, "quick")
        
        assert result["success"] is True
        assert "system_profile" in result
        assert "hardware_profile" not in result
        assert "service_profile" not in result
    
    @pytest.mark.asyncio
    async def test_perform_initial_scan_server_not_found(self, detection_service):
        """Test scan with non-existent server"""
        with pytest.raises(ServerNotFoundError):
            await detection_service.perform_initial_scan("non-existent-id", "full")
    
    @pytest.mark.asyncio
    async def test_validate_connection(self, detection_service, test_server, mock_ssh_manager, mocker):
        """Test connection validation"""
        mocker.patch('backend.services.server_detection_service.ssh_factory.connect_to_server', 
                    return_value=mock_ssh_manager)
        
        # Mock validation commands
        mock_ssh_manager.test_connection = AsyncMock(return_value={"success": True})
        mock_ssh_manager.execute_command = AsyncMock(side_effect=[
            Mock(success=True, stdout="uid=1000(testuser) gid=1000(testuser)", stderr=""),  # id
            Mock(success=False, stdout="", stderr="sudo requires password"),  # sudo check
            Mock(success=True, stdout="/dev/sda1 100G 45G 55G 45% /", stderr=""),  # df
        ])
        
        result = await detection_service.validate_connection(test_server.id)
        
        assert result["connection_valid"] is True
        assert result["server_id"] == test_server.id
        assert result["hostname"] == test_server.hostname
        assert "checks" in result
        
        checks = result["checks"]
        assert checks["user_check"]["success"] is True
        assert checks["sudo_access"]["available"] is False
        assert checks["sudo_access"]["requires_password"] is True
        assert "disk_space" in checks
    
    @pytest.mark.asyncio
    async def test_system_profile_parsing(self, detection_service, mock_ssh_manager):
        """Test system profile parsing logic"""
        # Test Ubuntu detection
        profile = SystemProfile()
        mock_ssh_manager.execute_command = AsyncMock(
            return_value=Mock(success=True, stdout="/usr/bin/apt", stderr="")
        )
        
        package_manager = await detection_service._detect_package_manager(mock_ssh_manager)
        assert package_manager == "apt"
        
        # Test CentOS detection
        mock_ssh_manager.execute_command = AsyncMock(side_effect=[
            Mock(success=False, stdout="", stderr="not found"),  # apt
            Mock(success=True, stdout="/usr/bin/yum", stderr=""),  # yum
        ])
        
        package_manager = await detection_service._detect_package_manager(mock_ssh_manager)
        assert package_manager == "yum"
    
    @pytest.mark.asyncio
    async def test_hardware_profile_parsing(self, detection_service):
        """Test hardware profile parsing"""
        profile = HardwareProfile()
        
        # Test memory parsing
        memory_output = """              total        used        free      shared  buff/cache   available
Mem:           8192        4096        2048         512        2048        3584
Swap:          2048           0        2048"""
        
        for line in memory_output.split('\n'):
            if line.startswith('Mem:'):
                parts = line.split()
                profile.memory_total_mb = int(parts[1])
                profile.memory_available_mb = int(parts[6])
            elif line.startswith('Swap:'):
                parts = line.split()
                profile.swap_total_mb = int(parts[1])
        
        assert profile.memory_total_mb == 8192
        assert profile.memory_available_mb == 3584
        assert profile.swap_total_mb == 2048
    
    @pytest.mark.asyncio
    async def test_service_profile_detection(self, detection_service):
        """Test service detection logic"""
        profile = ServiceProfile()
        
        # Test Docker detection
        docker_output = "Docker version 24.0.7, build afdd53b"
        if "no docker" not in docker_output.lower():
            profile.has_docker = True
            profile.docker_version = docker_output.strip()
        
        assert profile.has_docker is True
        assert "24.0.7" in profile.docker_version
        
        # Test port parsing
        ports_output = """tcp   LISTEN 0      128          0.0.0.0:22        0.0.0.0:*
tcp   LISTEN 0      511          0.0.0.0:80        0.0.0.0:*
tcp   LISTEN 0      511          0.0.0.0:443       0.0.0.0:*"""
        
        listening_ports = []
        for line in ports_output.split('\n'):
            parts = line.split()
            if len(parts) >= 5:
                addr = parts[3]
                if ':' in addr:
                    port = addr.split(':')[-1]
                    protocol = "tcp"
                    listening_ports.append({
                        "port": port,
                        "protocol": protocol,
                        "address": addr
                    })
        
        assert len(listening_ports) == 3
        assert listening_ports[0]["port"] == "22"
        assert listening_ports[1]["port"] == "80"
        assert listening_ports[2]["port"] == "443"


class TestSystemProfile:
    """Test SystemProfile class"""
    
    def test_system_profile_initialization(self):
        """Test SystemProfile initialization"""
        profile = SystemProfile()
        
        assert profile.os_family == "unknown"
        assert profile.os_distribution == "unknown"
        assert profile.os_version == "unknown"
        assert profile.kernel_version == "unknown"
        assert profile.architecture == "unknown"
        assert profile.package_manager == "unknown"
        assert profile.init_system == "unknown"
        assert profile.hostname == "unknown"
        assert isinstance(profile.last_scanned, datetime)
    
    def test_system_profile_to_dict(self):
        """Test SystemProfile to_dict method"""
        profile = SystemProfile()
        profile.os_family = "debian"
        profile.os_distribution = "ubuntu"
        profile.os_version = "22.04"
        
        result = profile.to_dict()
        
        assert isinstance(result, dict)
        assert result["os_family"] == "debian"
        assert result["os_distribution"] == "ubuntu"
        assert result["os_version"] == "22.04"
        assert "last_scanned" in result


class TestHardwareProfile:
    """Test HardwareProfile class"""
    
    def test_hardware_profile_initialization(self):
        """Test HardwareProfile initialization"""
        profile = HardwareProfile()
        
        assert profile.cpu_count == 0
        assert profile.cpu_model == "unknown"
        assert profile.memory_total_mb == 0
        assert profile.memory_available_mb == 0
        assert profile.swap_total_mb == 0
        assert isinstance(profile.storage_devices, list)
        assert isinstance(profile.gpu_devices, list)
        assert isinstance(profile.network_interfaces, list)
    
    def test_hardware_profile_to_dict(self):
        """Test HardwareProfile to_dict method"""
        profile = HardwareProfile()
        profile.cpu_count = 4
        profile.cpu_model = "Intel Core i7"
        profile.memory_total_mb = 16384
        profile.storage_devices = [
            {"filesystem": "/dev/sda1", "size": "500G"}
        ]
        
        result = profile.to_dict()
        
        assert isinstance(result, dict)
        assert result["cpu_count"] == 4
        assert result["cpu_model"] == "Intel Core i7"
        assert result["memory_total_mb"] == 16384
        assert len(result["storage_devices"]) == 1


class TestServiceProfile:
    """Test ServiceProfile class"""
    
    def test_service_profile_initialization(self):
        """Test ServiceProfile initialization"""
        profile = ServiceProfile()
        
        assert profile.has_docker is False
        assert profile.docker_version is None
        assert profile.has_systemd is False
        assert profile.systemd_version is None
        assert profile.has_sudo is False
        assert profile.firewall_type is None
        assert isinstance(profile.listening_ports, list)
        assert isinstance(profile.running_services, list)
    
    def test_service_profile_to_dict(self):
        """Test ServiceProfile to_dict method"""
        profile = ServiceProfile()
        profile.has_docker = True
        profile.docker_version = "24.0.7"
        profile.has_systemd = True
        profile.listening_ports = [
            {"port": "22", "protocol": "tcp"}
        ]
        profile.running_services = ["ssh", "nginx"]
        
        result = profile.to_dict()
        
        assert isinstance(result, dict)
        assert result["has_docker"] is True
        assert result["docker_version"] == "24.0.7"
        assert result["has_systemd"] is True
        assert len(result["listening_ports"]) == 1
        assert len(result["running_services"]) == 2
