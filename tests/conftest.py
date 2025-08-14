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

# Import ALL models to ensure they're registered with Base.metadata
# This is crucial - all models must be imported before create_all()
from backend.models.database import (
    Server, User, CommandHistory, AuditLog, 
    OperationPlan, OperationExecution,
    ServerProfile, ServerHardware, ServerServices
)
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
    """Create a test database session with proper schema"""
    # Create test database engine with echo for debugging
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=NullPool,
        echo=False  # Set to True if you need to debug SQL
    )
    
    # Ensure all models are imported before creating tables
    from backend.models import database  # Import the module to register all models
    
    # Create all tables from the metadata
    async with engine.begin() as conn:
        # Drop all tables first to ensure clean state
        await conn.run_sync(Base.metadata.drop_all)
        # Create all tables with current schema
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session factory
    async_session = async_sessionmaker(
        engine, 
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    # Provide the session
    async with async_session() as session:
        try:
            yield session
            await session.rollback()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    # Clean up engine
    await engine.dispose()


@pytest.fixture
async def test_server(test_db: AsyncSession) -> Server:
    """Create a test server with all required fields"""
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
        private_key=None,
        connection_status="unknown",
        last_connected=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        # Explicitly set system profiling fields to None
        system_info=None,  # NOT 'null' string!
        last_scan_date=None
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
        updated_at=datetime.utcnow(),
        last_login=None
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
def mock_ssh_manager(mocker):
    """Mock SSH manager for testing"""
    mock = mocker.AsyncMock()
    mock.connect = mocker.AsyncMock(return_value=True)
    mock.disconnect = mocker.AsyncMock()
    mock.execute_command = mocker.AsyncMock()
    mock.get_connection = mocker.AsyncMock()
    mock.is_connected = mocker.Mock(return_value=True)
    
    # Default command result
    from unittest.mock import Mock
    mock.execute_command.return_value = Mock(
        success=True,
        stdout="",
        stderr="",
        exit_code=0
    )
    
    return mock


@pytest.fixture
def mock_encryption(mocker):
    """Mock encryption functions"""
    mocker.patch('backend.core.security.encrypt_password', return_value="encrypted_password")
    mocker.patch('backend.core.security.decrypt_password', return_value="decrypted_password")
    mocker.patch('backend.core.security.encrypt_data', return_value="encrypted_data")
    mocker.patch('backend.core.security.decrypt_data', return_value="decrypted_data")


@pytest.fixture
async def clean_db(test_db: AsyncSession):
    """Fixture to ensure database is clean before and after test"""
    # Clean up any existing data
    await test_db.execute("DELETE FROM command_history")
    await test_db.execute("DELETE FROM server_services")
    await test_db.execute("DELETE FROM server_hardware")
    await test_db.execute("DELETE FROM server_profiles")
    await test_db.execute("DELETE FROM servers")
    await test_db.execute("DELETE FROM users")
    await test_db.commit()
    
    yield test_db
    
    # Clean up after test
    await test_db.rollback()