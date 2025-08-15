"""
Test configuration and fixtures for the MCP Server Project.

This module provides proper test setup, including application initialization,
authentication, and test data management.
"""

import asyncio
import logging
from collections.abc import Generator
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette

from app.main import app, setup_mcp
from app.settings import settings

# Configure test logging
logging.basicConfig(level=logging.WARNING)
logging.getLogger("app").setLevel(logging.INFO)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_app() -> Starlette:
    """Create a test application with proper initialization."""
    # Use the same middleware stack as the real app
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    from app.logging_config import configure_json_logging
    from app.main import middleware
    from app.settings import settings

    # Create a test-specific lifespan that doesn't use MCP session manager
    @asynccontextmanager
    async def test_lifespan(starlette_app: Starlette):
        # Configure logging
        configure_json_logging(settings.LOG_LEVEL)

        # Initialize MCP components without MCP app lifespan
        starlette_app.state.mcp_components = await setup_mcp()
        logging.info("MCP components initialized for testing")
        yield

    # Create a fresh copy of the app for each test to avoid session manager conflicts
    test_app = Starlette(
        debug=True,
        routes=app.routes,
        lifespan=test_lifespan,
        middleware=middleware,
    )

    # Initialize test-specific rate limiter with higher limits for testing
    test_limiter = Limiter(key_func=get_remote_address)
    test_app.state.limiter = test_limiter

    return test_app


@pytest.fixture(scope="function")
def client(test_app: Starlette) -> Generator[TestClient, None, None]:
    """Create a test client with proper application setup."""
    # Create a fresh client for each test to avoid session conflicts
    with TestClient(test_app) as test_client:
        # Reset rate limiter state for each test to ensure isolation
        if hasattr(test_app.state, "limiter"):
            test_app.state.limiter.reset_all()
        yield test_client


@pytest.fixture
def auth_token(client: TestClient) -> str:
    """Get authentication token for testing."""
    response = client.post(
        "/api/auth/login",
        json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
    )

    if response.status_code == 200:
        return response.json().get("token", "")
    else:
        # If login fails, return empty token (tests will handle this)
        return ""


@pytest.fixture
def authenticated_client(client: TestClient, auth_token: str) -> TestClient:
    """Create a test client with authentication headers."""
    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return client


@pytest.fixture
def mock_mcp_server():
    """Mock MCP server to avoid startup issues in tests."""
    with patch("app.main.mcp_app") as mock_app:
        # Mock the MCP app to prevent actual server startup
        mock_app.lifespan = None
        mock_app.routes = []
        yield mock_app


@pytest.fixture
def mock_file_system():
    """Mock file system operations for testing."""
    with patch("app.tools.file_system_tools") as mock_fs:
        # Mock file system operations
        mock_fs.list_directory.return_value = {"files": ["test.txt"], "directories": ["test_dir"]}
        mock_fs.read_file.return_value = {"content": "test content", "size": 12}
        mock_fs.write_file.return_value = {"success": True, "bytes_written": 12}
        yield mock_fs


@pytest.fixture
def mock_shell_commands():
    """Mock shell command execution for testing."""
    with patch("app.tools.shell_tools") as mock_shell:
        # Mock shell command execution
        mock_shell.execute_shell_command.return_value = {
            "stdout": "test output",
            "stderr": "",
            "return_code": 0,
        }
        yield mock_shell


@pytest.fixture
def test_data():
    """Provide test data for various test scenarios."""
    return {
        "valid_user": {"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
        "invalid_user": {"username": "invalid", "password": "invalid"},
        "test_file": {"path": "/tmp/test.txt", "content": "test content"},
        "test_command": {"command": "echo 'test'", "expected_output": "test"},
    }


# Test markers for different test categories
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "auth: mark test as an authentication test")
    config.addinivalue_line("markers", "mcp: mark test as an MCP-specific test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
