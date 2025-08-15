"""
Basic SSH connection and server info tests
"""

import pytest
from backend.core.ssh_manager import SSHManager, SSHConfig


class TestBasicConnection:
    """Test basic SSH connectivity"""
    
    @pytest.mark.asyncio
    async def test_ssh_connection(self, ssh_manager: SSHManager, test_server_config: SSHConfig):
        """Test that we can connect to the server"""
        success = await ssh_manager.connect(test_server_config)
        assert success, "Should be able to connect to test server"
        
        # Test that connection is working
        assert ssh_manager.is_connected(), "SSH manager should report connected"
    
    @pytest.mark.asyncio
    async def test_connection_test(self, connected_ssh: SSHManager):
        """Test the built-in connection test"""
        result = await connected_ssh.test_connection()
        
        assert result["success"] is True
        assert "response_time_ms" in result
        assert result["response_time_ms"] > 0
        assert "test_output" in result


class TestServerInfo:
    """Test gathering basic server information"""
    
    @pytest.mark.asyncio
    async def test_get_hostname(self, connected_ssh: SSHManager):
        """Test getting server hostname"""
        result = await connected_ssh.execute_command("hostname")
        
        assert result.success is True
        assert result.exit_code == 0
        assert len(result.stdout.strip()) > 0
        print(f"Hostname: {result.stdout.strip()}")
    
    @pytest.mark.asyncio
    async def test_get_os_info(self, connected_ssh: SSHManager):
        """Test getting OS information"""
        # Try different commands to get OS info
        commands = [
            "cat /etc/os-release",
            "uname -a",
            "whoami"
        ]
        
        for cmd in commands:
            result = await connected_ssh.execute_command(cmd)
            assert result.success is True
            assert result.exit_code == 0
            print(f"{cmd}: {result.stdout.strip()[:100]}")
    
    @pytest.mark.asyncio
    async def test_get_working_directory(self, connected_ssh: SSHManager):
        """Test getting current working directory"""
        result = await connected_ssh.execute_command("pwd")
        
        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout.strip().startswith("/")
        print(f"Working directory: {result.stdout.strip()}")


class TestSystemResources:
    """Test gathering system resource information"""
    
    @pytest.mark.asyncio
    async def test_cpu_info(self, connected_ssh: SSHManager):
        """Test getting CPU information"""
        # CPU count
        result = await connected_ssh.execute_command("nproc")
        assert result.success is True
        cpu_count = int(result.stdout.strip())
        assert cpu_count > 0
        print(f"CPU cores: {cpu_count}")
        
        # CPU model (try different approaches)
        commands = [
            "cat /proc/cpuinfo | grep 'model name' | head -1",
            "lscpu | grep 'Model name'"
        ]
        
        for cmd in commands:
            result = await connected_ssh.execute_command(cmd)
            if result.success and result.stdout.strip():
                print(f"CPU info: {result.stdout.strip()}")
                break
    
    @pytest.mark.asyncio
    async def test_memory_info(self, connected_ssh: SSHManager):
        """Test getting memory information"""
        result = await connected_ssh.execute_command("free -h")
        
        assert result.success is True
        assert "Mem:" in result.stdout
        print(f"Memory info:\n{result.stdout}")
    
    @pytest.mark.asyncio
    async def test_disk_info(self, connected_ssh: SSHManager):
        """Test getting disk information"""
        result = await connected_ssh.execute_command("df -h")
        
        assert result.success is True
        assert "Filesystem" in result.stdout
        print(f"Disk info:\n{result.stdout}")
    
    @pytest.mark.asyncio
    async def test_gpu_detection(self, connected_ssh: SSHManager):
        """Test GPU detection (may not be present)"""
        # Try nvidia first
        result = await connected_ssh.execute_command("nvidia-smi --query-gpu=name --format=csv,noheader,nounits")
        if result.success and result.stdout.strip():
            print(f"NVIDIA GPU: {result.stdout.strip()}")
        else:
            # Try lspci for any GPU
            result = await connected_ssh.execute_command("lspci | grep -i 'vga\\|3d\\|display'")
            if result.success and result.stdout.strip():
                print(f"GPU detected: {result.stdout.strip()}")
            else:
                print("No GPU detected or lspci not available")