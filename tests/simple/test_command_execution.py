"""
Test command execution capabilities
"""

import pytest
from backend.core.ssh_manager import SSHManager


class TestBasicCommands:
    """Test basic command execution"""
    
    @pytest.mark.asyncio
    async def test_simple_echo(self, connected_ssh: SSHManager):
        """Test simple echo command"""
        result = await connected_ssh.execute_command("echo 'Hello World'")
        
        assert result.success is True
        assert result.exit_code == 0
        assert "Hello World" in result.stdout
        assert result.execution_time > 0
    
    @pytest.mark.asyncio
    async def test_list_directory(self, connected_ssh: SSHManager):
        """Test listing directory contents"""
        result = await connected_ssh.execute_command("ls -la")
        
        assert result.success is True
        assert result.exit_code == 0
        assert len(result.stdout) > 0
        print(f"Directory listing:\n{result.stdout}")
    
    @pytest.mark.asyncio
    async def test_current_user(self, connected_ssh: SSHManager):
        """Test getting current user"""
        result = await connected_ssh.execute_command("whoami")
        
        assert result.success is True
        assert result.exit_code == 0
        username = result.stdout.strip()
        assert len(username) > 0
        print(f"Current user: {username}")
    
    @pytest.mark.asyncio
    async def test_date_command(self, connected_ssh: SSHManager):
        """Test getting system date"""
        result = await connected_ssh.execute_command("date")
        
        assert result.success is True
        assert result.exit_code == 0
        assert len(result.stdout.strip()) > 0
        print(f"System date: {result.stdout.strip()}")


class TestSystemCommands:
    """Test system-level commands"""
    
    @pytest.mark.asyncio
    async def test_uptime(self, connected_ssh: SSHManager):
        """Test system uptime"""
        result = await connected_ssh.execute_command("uptime")
        
        assert result.success is True
        assert result.exit_code == 0
        assert "load average" in result.stdout.lower() or "up" in result.stdout.lower()
        print(f"Uptime: {result.stdout.strip()}")
    
    @pytest.mark.asyncio
    async def test_process_list(self, connected_ssh: SSHManager):
        """Test listing processes"""
        result = await connected_ssh.execute_command("ps aux | head -10")
        
        assert result.success is True
        assert result.exit_code == 0
        assert "PID" in result.stdout or "USER" in result.stdout
        print("Top processes:")
        print(result.stdout)
    
    @pytest.mark.asyncio
    async def test_network_interfaces(self, connected_ssh: SSHManager):
        """Test getting network interface info"""
        # Try different commands depending on what's available
        commands = [
            "ip addr show",
            "ifconfig",
            "ip a"
        ]
        
        success = False
        for cmd in commands:
            result = await connected_ssh.execute_command(cmd)
            if result.success and len(result.stdout) > 0:
                print(f"Network info ({cmd}):\n{result.stdout[:500]}")
                success = True
                break
        
        # At least one command should work
        assert success, "Should be able to get network interface information"
    
    @pytest.mark.asyncio
    async def test_environment_variables(self, connected_ssh: SSHManager):
        """Test accessing environment variables"""
        result = await connected_ssh.execute_command("echo $HOME")
        
        assert result.success is True
        assert result.exit_code == 0
        home_path = result.stdout.strip()
        assert home_path.startswith("/")
        print(f"Home directory: {home_path}")


class TestErrorHandling:
    """Test command error handling"""
    
    @pytest.mark.asyncio
    async def test_nonexistent_command(self, connected_ssh: SSHManager):
        """Test running a command that doesn't exist"""
        result = await connected_ssh.execute_command("nonexistentcommand12345")
        
        assert result.success is False
        assert result.exit_code != 0
        assert len(result.stderr) > 0 or "not found" in result.stdout.lower()
    
    @pytest.mark.asyncio
    async def test_permission_denied(self, connected_ssh: SSHManager):
        """Test command that might have permission issues"""
        # Try to read a file that might not be readable
        result = await connected_ssh.execute_command("cat /etc/shadow")
        
        # This should either work (if user has sudo) or fail gracefully
        if not result.success:
            assert result.exit_code != 0
            assert "permission denied" in result.stderr.lower() or "permission denied" in result.stdout.lower()
        else:
            # If it worked, user has high privileges
            print("User has access to /etc/shadow")
    
    @pytest.mark.asyncio
    async def test_command_timeout_behavior(self, connected_ssh: SSHManager):
        """Test that quick commands complete within reasonable time"""
        result = await connected_ssh.execute_command("echo 'quick test'")
        
        assert result.success is True
        assert result.execution_time < 5.0  # Should complete in under 5 seconds