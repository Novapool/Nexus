"""
Pytest configuration and shared fixtures
"""

import pytest
import asyncio
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
import tempfile
import os

from backend.config.database import Base
from backend.models.database import Server, User
from backend.config.settings import Settings


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Create test settings"""
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        secret_key="test-secret-key-for-testing-only",
        ssh_timeout=5,
        command_timeout=10,
        ai_model="test-model",
        ai_temperature=0.7,
        ai_max_tokens=1000,
        environment="test"
    )


@pytest.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session"""
    # Create test database engine
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=NullPool,
        echo=False
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async_session = async_sessionmaker(
        engine, 
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()
    
    # Clean up
    await engine.dispose()


@pytest.fixture
async def test_server(test_db: AsyncSession) -> Server:
    """Create a test server"""
    import uuid
    from datetime import datetime
    
    server = Server(
        id=str(uuid.uuid4()),
        hostname="test-server.local",
        username="testuser",
        port=22,
        description="Test server for unit tests",
        os_type="linux",
        password="encrypted_test_password",
        connection_status="unknown",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    test_db.add(server)
    await test_db.commit()
    await test_db.refresh(server)
    
    return server


@pytest.fixture
async def test_user(test_db: AsyncSession) -> User:
    """Create a test user"""
    import uuid
    from datetime import datetime
    
    user = User(
        id=str(uuid.uuid4()),
        username="testuser",
        email="test@example.com",
        hashed_password="hashed_test_password",
        is_active=True,
        is_admin=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    
    return user


@pytest.fixture
def mock_ssh_connection(mocker):
    """Mock SSH connection for testing"""
    mock_conn = mocker.AsyncMock()
    mock_conn.run = mocker.AsyncMock()
    mock_conn.close = mocker.Mock()
    mock_conn.wait_closed = mocker.AsyncMock()
    
    # Default successful command result
    mock_result = mocker.Mock()
    mock_result.stdout = "command output"
    mock_result.stderr = ""
    mock_result.exit_status = 0
    mock_conn.run.return_value = mock_result
    
    return mock_conn


@pytest.fixture
def mock_ssh_manager(mocker, mock_ssh_connection):
    """Mock SSH manager for testing"""
    from backend.core.ssh_manager import SSHManager
    
    mock_manager = mocker.Mock(spec=SSHManager)
    mock_manager.connect = mocker.AsyncMock(return_value=True)
    mock_manager.disconnect = mocker.AsyncMock()
    mock_manager.is_connected = mocker.Mock(return_value=True)
    mock_manager.execute_command = mocker.AsyncMock()
    mock_manager.test_connection = mocker.AsyncMock(
        return_value={
            "success": True,
            "response_time_ms": 10.5,
            "test_output": "Connection test successful",
            "server_info": {
                "hostname": "test-server.local",
                "port": 22,
                "username": "testuser",
                "connected": True
            }
        }
    )
    mock_manager.gather_system_info = mocker.AsyncMock(
        return_value={
            "hostname": "test-server",
            "os_release": "Ubuntu 22.04",
            "kernel": "5.15.0-generic",
            "architecture": "x86_64",
            "cpu_info": "4",
            "memory_info": "8192",
            "disk_usage": "45%",
            "uptime": "up 5 days",
            "shell": "/bin/bash",
            "user": "testuser",
            "working_dir": "/home/testuser",
            "package_manager": "apt",
            "os_type": "ubuntu"
        }
    )
    
    return mock_manager


@pytest.fixture
def sample_scan_result():
    """Sample scan result for testing"""
    return {
        "server_id": "test-server-id",
        "scan_type": "full",
        "scan_timestamp": "2025-01-13T12:00:00",
        "success": True,
        "error": None,
        "system_profile": {
            "os_family": "debian",
            "os_distribution": "ubuntu",
            "os_version": "22.04",
            "kernel_version": "5.15.0-generic",
            "architecture": "x86_64",
            "package_manager": "apt",
            "init_system": "systemd",
            "hostname": "test-server",
            "last_scanned": "2025-01-13T12:00:00"
        },
        "hardware_profile": {
            "cpu_count": 4,
            "cpu_model": "Intel Core i7",
            "memory_total_mb": 8192,
            "memory_available_mb": 4096,
            "swap_total_mb": 2048,
            "storage_devices": [
                {
                    "filesystem": "/dev/sda1",
                    "size": "100G",
                    "used": "45G",
                    "available": "55G",
                    "use_percent": "45%",
                    "mount_point": "/"
                }
            ],
            "gpu_devices": [],
            "network_interfaces": [
                {
                    "name": "eth0",
                    "addresses": [
                        {"type": "ipv4", "address": "192.168.1.100/24"}
                    ]
                }
            ]
        },
        "service_profile": {
            "has_docker": True,
            "docker_version": "Docker version 24.0.7",
            "has_systemd": True,
            "systemd_version": "systemd 249",
            "has_sudo": True,
            "firewall_type": "ufw",
            "listening_ports": [
                {"port": "22", "protocol": "tcp", "address": "0.0.0.0:22"},
                {"port": "80", "protocol": "tcp", "address": "0.0.0.0:80"}
            ],
            "running_services": ["ssh", "nginx", "docker"]
        }
    }
