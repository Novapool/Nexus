"""
Integration tests for server management functionality
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.services.server_service import ServerService
from backend.services.server_detection_service import ServerDetectionService
from backend.models.database import Server, ServerProfile, ServerHardware, ServerServices
from backend.models.schemas import ServerCreate, ServerUpdate
from backend.core.exceptions import ServerNotFoundError, SSHConnectionError


class TestServerManagementIntegration:
    """Integration tests for complete server management flow"""
    
    @pytest.mark.asyncio
    async def test_create_server_with_auto_scan(self, test_db, mock_ssh_manager, mocker):
        """Test creating a server and performing automatic system scan"""
        # Mock SSH factory
        mocker.patch('backend.services.server_service.ssh_factory.connect_to_server', 
                    return_value=mock_ssh_manager)
        mocker.patch('backend.services.server_detection_service.ssh_factory.connect_to_server', 
                    return_value=mock_ssh_manager)
        
        # Mock encryption
        mocker.patch('backend.services.server_service.encrypt_password', 
                    return_value="encrypted_password")
        
        # Create services
        server_service = ServerService(test_db)
        detection_service = ServerDetectionService(test_db)
        
        # Create server data
        server_data = ServerCreate(
            hostname="new-test-server.local",
            username="testuser",
            port=22,
            password="test_password",
            description="Integration test server",
            os_type="linux"
        )
        
        # Create server
        created_server = await server_service.create_server(server_data)
        
        assert created_server is not None
        assert created_server.hostname == "new-test-server.local"
        assert created_server.username == "testuser"
        
        # Mock scan commands
        mock_ssh_manager.execute_command = AsyncMock(side_effect=[
            Mock(success=True, stdout="Ubuntu 22.04\nVERSION_ID=\"22.04\"", stderr=""),
            Mock(success=True, stdout="", stderr=""),
            Mock(success=True, stdout="Linux test 5.15.0 x86_64", stderr=""),
            Mock(success=True, stdout="test-server", stderr=""),
            Mock(success=True, stdout="5.15.0-generic", stderr=""),
            Mock(success=True, stdout="x86_64", stderr=""),
            Mock(success=True, stdout="/usr/bin/apt", stderr=""),
            Mock(success=True, stdout="1", stderr=""),
        ])
        
        # Perform initial scan
        scan_result = await detection_service.perform_initial_scan(created_server.id, "quick")
        
        assert scan_result["success"] is True
        assert scan_result["server_id"] == created_server.id
        assert "system_profile" in scan_result
        
        # Verify system profile was parsed correctly
        system_profile = scan_result["system_profile"]
        assert system_profile["os_family"] == "debian"
        assert system_profile["os_distribution"] == "ubuntu"
        assert system_profile["os_version"] == "22.04"
        assert system_profile["architecture"] == "x86_64"
    
    @pytest.mark.asyncio
    async def test_server_crud_operations(self, test_db):
        """Test complete CRUD operations for servers"""
        server_service = ServerService(test_db)
        
        # Mock encryption
        with patch('backend.services.server_service.encrypt_password', return_value="encrypted"):
            # Create
            server_data = ServerCreate(
                hostname="crud-test.local",
                username="cruduser",
                port=2222,
                password="crud_password",
                description="CRUD test server"
            )
            
            created = await server_service.create_server(server_data)
            assert created.hostname == "crud-test.local"
            assert created.port == 2222
            
            # Read
            fetched = await server_service.get_server(created.id)
            assert fetched is not None
            assert fetched.id == created.id
            assert fetched.hostname == "crud-test.local"
            
            # Update
            update_data = ServerUpdate(
                hostname="updated-crud.local",
                port=3333,
                description="Updated CRUD test"
            )
            
            updated = await server_service.update_server(created.id, update_data)
            assert updated.hostname == "updated-crud.local"
            assert updated.port == 3333
            assert updated.description == "Updated CRUD test"
            
            # List
            servers = await server_service.get_servers()
            assert len(servers) >= 1
            assert any(s.id == created.id for s in servers)
            
            # Delete
            deleted = await server_service.delete_server(created.id)
            assert deleted is True
            
            # Verify deletion
            fetched_after_delete = await server_service.get_server(created.id)
            assert fetched_after_delete is None
    
    @pytest.mark.asyncio
    async def test_server_connection_validation_flow(self, test_db, test_server, mock_ssh_manager, mocker):
        """Test complete server connection validation flow"""
        # Mock SSH factory
        mocker.patch('backend.services.server_detection_service.ssh_factory.connect_to_server', 
                    return_value=mock_ssh_manager)
        
        detection_service = ServerDetectionService(test_db)
        
        # Mock validation commands
        mock_ssh_manager.test_connection = AsyncMock(return_value={
            "success": True,
            "response_time_ms": 15.2
        })
        mock_ssh_manager.execute_command = AsyncMock(side_effect=[
            Mock(success=True, stdout="uid=1000(testuser)", stderr=""),  # id
            Mock(success=True, stdout="", stderr=""),  # sudo
            Mock(success=True, stdout="/dev/sda1 100G 30G 70G 30% /", stderr=""),  # df
        ])
        
        # Validate connection
        validation_result = await detection_service.validate_connection(test_server.id)
        
        assert validation_result["connection_valid"] is True
        assert validation_result["server_id"] == test_server.id
        assert validation_result["response_time_ms"] == 15.2
        assert "checks" in validation_result
        
        checks = validation_result["checks"]
        assert checks["user_check"]["success"] is True
        assert checks["sudo_access"]["available"] is True
        assert checks["disk_space"]["usage_percent"] == "30%"
    
    @pytest.mark.asyncio
    async def test_server_system_info_gathering(self, test_db, test_server, mock_ssh_manager, mocker):
        """Test gathering system information from server"""
        # Mock SSH factory and encryption
        mocker.patch('backend.services.server_service.ssh_factory.connect_to_server', 
                    return_value=mock_ssh_manager)
        mocker.patch('backend.services.server_service.decrypt_password', 
                    return_value="decrypted_password")
        
        server_service = ServerService(test_db)
        
        # Get system info
        system_info = await server_service.get_system_info(test_server.id)
        
        assert system_info["server_id"] == test_server.id
        assert system_info["hostname"] == test_server.hostname
        assert "collected_at" in system_info
        assert system_info["os_type"] == "ubuntu"
        assert system_info["package_manager"] == "apt"
    
    @pytest.mark.asyncio
    async def test_server_command_execution_flow(self, test_db, test_server, mock_ssh_manager, mocker):
        """Test command execution on server"""
        # Mock SSH factory and encryption
        mocker.patch('backend.services.server_service.ssh_factory.connect_to_server', 
                    return_value=mock_ssh_manager)
        mocker.patch('backend.services.server_service.decrypt_password', 
                    return_value="decrypted_password")
        
        # Mock command execution
        from backend.core.ssh_manager import CommandResult
        mock_result = CommandResult(
            command="ls -la",
            stdout="total 24\ndrwxr-xr-x 2 user user 4096 Jan 1 00:00 .",
            stderr="",
            exit_code=0,
            execution_time=0.5,
            working_directory="/home/user",
            success=True
        )
        mock_ssh_manager.execute_command = AsyncMock(return_value=mock_result)
        
        server_service = ServerService(test_db)
        
        # Execute command
        result = await server_service.execute_command(
            server_id=test_server.id,
            command="ls -la",
            timeout=30
        )
        
        assert result["success"] is True
        assert result["command"] == "ls -la"
        assert result["exit_code"] == 0
        assert "total 24" in result["stdout"]
        assert result["execution_time"] == 0.5
    
    @pytest.mark.asyncio
    async def test_full_server_scan_with_profile_storage(self, test_db, test_server, mock_ssh_manager, mocker, sample_scan_result):
        """Test full server scan with profile storage in database"""
        # Mock SSH factory
        mocker.patch('backend.services.server_detection_service.ssh_factory.connect_to_server', 
                    return_value=mock_ssh_manager)
        
        detection_service = ServerDetectionService(test_db)
        
        # Mock comprehensive scan commands
        mock_ssh_manager.execute_command = AsyncMock(side_effect=[
            # System profile commands
            Mock(success=True, stdout="Ubuntu 22.04\nVERSION_ID=\"22.04\"", stderr=""),
            Mock(success=True, stdout="", stderr=""),
            Mock(success=True, stdout="Linux test 5.15.0 x86_64", stderr=""),
            Mock(success=True, stdout="test-server", stderr=""),
            Mock(success=True, stdout="5.15.0-generic", stderr=""),
            Mock(success=True, stdout="x86_64", stderr=""),
            Mock(success=True, stdout="/usr/bin/apt", stderr=""),
            Mock(success=True, stdout="1", stderr=""),
            # Hardware profile commands
            Mock(success=True, stdout="4", stderr=""),
            Mock(success=True, stdout="Intel Core i7", stderr=""),
            Mock(success=True, stdout="Mem: 8192 4096 2048 512 2048 3584", stderr=""),
            Mock(success=True, stdout="/dev/sda1 100G 45G 55G 45% /", stderr=""),
            Mock(success=True, stdout="", stderr=""),
            Mock(success=False, stdout="", stderr="no nvidia"),
            Mock(success=False, stdout="", stderr="no gpu"),
            Mock(success=True, stdout="eth0: inet 192.168.1.100/24", stderr=""),
            # Service profile commands
            Mock(success=True, stdout="Docker version 24.0.7", stderr=""),
            Mock(success=True, stdout="systemd 249", stderr=""),
            Mock(success=True, stdout="sudo version 1.9", stderr=""),
            Mock(success=True, stdout="Status: active", stderr=""),
            Mock(success=False, stdout="", stderr="no iptables"),
            Mock(success=True, stdout="tcp LISTEN 0.0.0.0:22", stderr=""),
            Mock(success=True, stdout="ssh.service\nnginx.service", stderr=""),
        ])
        
        # Perform full scan
        scan_result = await detection_service.perform_initial_scan(test_server.id, "full")
        
        assert scan_result["success"] is True
        assert "system_profile" in scan_result
        assert "hardware_profile" in scan_result
        assert "service_profile" in scan_result
        
        # Verify profiles
        assert scan_result["system_profile"]["os_distribution"] == "ubuntu"
        assert scan_result["hardware_profile"]["cpu_count"] == 4
        assert scan_result["service_profile"]["has_docker"] is True
    
    @pytest.mark.asyncio
    async def test_server_connection_error_handling(self, test_db, test_server, mocker):
        """Test error handling for connection failures"""
        # Mock SSH factory to raise connection error
        mocker.patch('backend.services.server_service.ssh_factory.connect_to_server', 
                    side_effect=SSHConnectionError("Connection refused"))
        mocker.patch('backend.services.server_service.decrypt_password', 
                    return_value="decrypted_password")
        
        server_service = ServerService(test_db)
        
        # Test connection should fail gracefully
        result = await server_service.test_connection(test_server.id)
        
        assert result["success"] is False
        assert "Connection refused" in result["error"]
        assert result["server_info"]["connected"] is False
    
    @pytest.mark.asyncio
    async def test_bulk_server_operations(self, test_db, mocker):
        """Test bulk operations on multiple servers"""
        server_service = ServerService(test_db)
        
        # Mock encryption
        mocker.patch('backend.services.server_service.encrypt_password', 
                    return_value="encrypted")
        
        # Create multiple servers
        server_ids = []
        for i in range(3):
            server_data = ServerCreate(
                hostname=f"bulk-test-{i}.local",
                username="bulkuser",
                port=22 + i,
                password="bulk_password",
                description=f"Bulk test server {i}"
            )
            created = await server_service.create_server(server_data)
            server_ids.append(created.id)
        
        # Get all servers
        servers = await server_service.get_servers()
        assert len(servers) >= 3
        
        # Count servers
        count = await server_service.count_servers()
        assert count >= 3
        
        # Clean up - delete all bulk test servers
        for server_id in server_ids:
            deleted = await server_service.delete_server(server_id)
            assert deleted is True
        
        # Verify deletion
        for server_id in server_ids:
            server = await server_service.get_server(server_id)
            assert server is None
    
    @pytest.mark.asyncio
    async def test_server_context_for_ai(self, test_db, test_server, mock_ssh_manager, mocker):
        """Test getting server context for AI command generation"""
        # Mock SSH factory and encryption
        mocker.patch('backend.services.server_service.ssh_factory.connect_to_server', 
                    return_value=mock_ssh_manager)
        mocker.patch('backend.services.server_service.decrypt_password', 
                    return_value="decrypted_password")
        
        server_service = ServerService(test_db)
        
        # Get server context
        context = await server_service.get_server_context(test_server.id)
        
        assert context["server_id"] == test_server.id
        assert context["hostname"] == test_server.hostname
        assert context["os_type"] == test_server.os_type
        assert "system_info" in context
        assert "capabilities" in context
        assert "current_state" in context
        
        # Verify capabilities are properly extracted
        capabilities = context["capabilities"]
        assert capabilities["package_manager"] == "apt"
        assert capabilities["shell"] == "/bin/bash"
        assert capabilities["architecture"] == "x86_64"
        
        # Verify current state
        current_state = context["current_state"]
        assert current_state["user"] == "testuser"
        assert current_state["working_directory"] == "/home/testuser"


class TestServerProfilePersistence:
    """Test persistence of server profiles in database"""
    
    @pytest.mark.asyncio
    async def test_save_and_retrieve_server_profile(self, test_db, test_server):
        """Test saving and retrieving server profile"""
        # Create server profile
        profile = ServerProfile(
            id=str(uuid.uuid4()),
            server_id=test_server.id,
            os_family="debian",
            os_distribution="ubuntu",
            os_version="22.04",
            kernel_version="5.15.0-generic",
            architecture="x86_64",
            package_manager="apt",
            init_system="systemd",
            last_scanned=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        test_db.add(profile)
        await test_db.commit()
        
        # Retrieve profile
        query = select(ServerProfile).where(ServerProfile.server_id == test_server.id)
        result = await test_db.execute(query)
        retrieved_profile = result.scalar_one_or_none()
        
        assert retrieved_profile is not None
        assert retrieved_profile.os_distribution == "ubuntu"
        assert retrieved_profile.os_version == "22.04"
        assert retrieved_profile.package_manager == "apt"
    
    @pytest.mark.asyncio
    async def test_save_and_retrieve_hardware_profile(self, test_db, test_server):
        """Test saving and retrieving hardware profile"""
        # Create hardware profile
        hardware = ServerHardware(
            id=str(uuid.uuid4()),
            server_id=test_server.id,
            cpu_count=4,
            cpu_model="Intel Core i7",
            memory_total_mb=16384,
            memory_available_mb=8192,
            swap_total_mb=4096,
            storage_info=[
                {"filesystem": "/dev/sda1", "size": "500G", "used": "200G"}
            ],
            gpu_info=[],
            network_info=[
                {"name": "eth0", "addresses": ["192.168.1.100"]}
            ],
            last_updated=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        test_db.add(hardware)
        await test_db.commit()
        
        # Retrieve hardware profile
        query = select(ServerHardware).where(ServerHardware.server_id == test_server.id)
        result = await test_db.execute(query)
        retrieved_hardware = result.scalar_one_or_none()
        
        assert retrieved_hardware is not None
        assert retrieved_hardware.cpu_count == 4
        assert retrieved_hardware.memory_total_mb == 16384
        assert len(retrieved_hardware.storage_info) == 1
        assert len(retrieved_hardware.network_info) == 1
    
    @pytest.mark.asyncio
    async def test_save_and_retrieve_services_profile(self, test_db, test_server):
        """Test saving and retrieving services profile"""
        # Create services profile
        services = ServerServices(
            id=str(uuid.uuid4()),
            server_id=test_server.id,
            has_docker=True,
            docker_version="24.0.7",
            has_systemd=True,
            systemd_version="249",
            has_sudo=True,
            firewall_type="ufw",
            listening_ports=[
                {"port": "22", "protocol": "tcp"},
                {"port": "80", "protocol": "tcp"},
                {"port": "443", "protocol": "tcp"}
            ],
            running_services=["ssh", "nginx", "docker"],
            last_updated=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        test_db.add(services)
        await test_db.commit()
        
        # Retrieve services profile
        query = select(ServerServices).where(ServerServices.server_id == test_server.id)
        result = await test_db.execute(query)
        retrieved_services = result.scalar_one_or_none()
        
        assert retrieved_services is not None
        assert retrieved_services.has_docker is True
        assert retrieved_services.docker_version == "24.0.7"
        assert len(retrieved_services.listening_ports) == 3
        assert len(retrieved_services.running_services) == 3
        assert "nginx" in retrieved_services.running_services
