"""
Pytest configuration and shared fixtures
"""

import pytest
import asyncio
import tempfile
import os
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from backend.config.database import Base
from backend.models.database import Server, User
from backend.config.settings import Settings

# Import ALL models to ensure they're registered with Base.metadata
from backend.models import database


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
    """Create a test database session with proper schema"""
    # Create test database engine
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=NullPool,
        echo=False
    )
    
    # Create all tables directly from models - this is the simplest approach
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
    mock_manager.execute_command = mocker.AsyncMock()
    mock_manager.get_connection = mocker.AsyncMock(return_value=mock_ssh_connection)
    
    return mock_manager