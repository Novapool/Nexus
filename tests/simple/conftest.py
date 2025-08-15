"""
Simple pytest configuration for basic testing
"""

import pytest
import asyncio
import os
from typing import Generator
from backend.core.ssh_manager import SSHManager, SSHConfig


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_server_config() -> SSHConfig:
    """Get test server configuration from environment"""
    return SSHConfig(
        hostname=os.getenv('TEST_SERVER_IP', '192.168.1.100'),
        username=os.getenv('TEST_SERVER_USERNAME', 'user'),
        password=os.getenv('TEST_SERVER_PASSWORD', 'password'),
        port=int(os.getenv('TEST_SERVER_PORT', '22')),
        timeout=int(os.getenv('TEST_TIMEOUT', '30'))
    )


@pytest.fixture
async def ssh_manager() -> SSHManager:
    """Create a fresh SSH manager for each test"""
    manager = SSHManager()
    yield manager
    # Clean up
    if manager._connection:
        await manager.disconnect()


@pytest.fixture
async def connected_ssh(ssh_manager: SSHManager, test_server_config: SSHConfig) -> SSHManager:
    """SSH manager that's already connected to test server"""
    success = await ssh_manager.connect(test_server_config)
    if not success:
        pytest.skip("Could not connect to test server")
    return ssh_manager