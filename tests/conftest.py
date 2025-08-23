"""
Test configuration and fixtures for the MCP Server Project.

This module provides proper test setup, including application initialization,
authentication, and test data management with proper FastMCP lifespan integration.
"""

import asyncio
import json
import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from starlette.applications import Starlette


@pytest.fixture(scope="session")
def temp_dir() -> Path:
    """Create a temporary directory for test operations."""
    with tempfile.TemporaryDirectory() as temp_dir_str:
        yield Path(temp_dir_str)


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment(temp_dir: Path) -> None:
    """
    Set env before the app is imported/created.
    Tests import create_app() later to build a fresh app with these values.
    """
    os.environ["TESTING"] = "true"
    os.environ["MCP_BASE_WORKING_DIR"] = str(temp_dir)
    os.environ["AUDIT_LOG_FILE"] = str(temp_dir / "audit.log")
    os.environ["LOG_LEVEL"] = "WARNING"
    # Enable shell only if your tests need it; consider toggling per-test instead.
    os.environ["ALLOW_ARBITRARY_SHELL_COMMANDS"] = "true"


@pytest.fixture
def test_app() -> Starlette:
    """Create a fresh app instance for each test (better isolation)."""
    # Import create_app AFTER env is set to ensure fresh configuration
    from app.main import create_app

    return create_app()


@pytest.fixture
async def client(test_app: Starlette) -> AsyncIterator[httpx.AsyncClient]:
    """
    Use LifespanManager with ASGITransport for httpx 0.28.1.
    This ensures the FastMCP session manager is initialized before requests.
    """
    async with LifespanManager(test_app):
        transport = httpx.ASGITransport(app=test_app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            timeout=30.0,
            headers={"Accept": "application/json, text/event-stream"},
        ) as c:
            yield c


@pytest.fixture
async def auth_token(client: httpx.AsyncClient) -> str:
    """Obtain bearer token from your login endpoint."""
    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def jsonrpc_headers() -> dict[str, str]:
    """
    Headers that satisfy strict JSON-RPC content negotiation in your MCP endpoint.
    FastMCP requires both application/json and text/event-stream in Accept header.
    """
    return {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }


@pytest.fixture
async def mcp_session_headers(
    client: httpx.AsyncClient,
    jsonrpc_headers: dict[str, str],
) -> dict[str, str]:
    """
    Obtain FastMCP session header and wait for FastMCP to be fully initialized.
    """
    session_id = None

    # First, try to get session ID from GET request
    for attempt in range(20):
        try:
            resp = await client.get("/mcp/mcp.json/", headers=jsonrpc_headers)
            session_id = resp.headers.get("mcp-session-id")
            if session_id:
                break
        except Exception:
            pass
        await asyncio.sleep(0.05)

    # If GET didn't work, try POST to get session ID
    if not session_id:
        for attempt in range(20):
            try:
                payload = {"jsonrpc": "2.0", "method": "tools/list", "id": 0}
                resp = await client.post(
                    "/mcp/mcp.json/",
                    headers=jsonrpc_headers,
                    content=json.dumps(payload),
                )
                session_id = resp.headers.get("mcp-session-id")
                if session_id:
                    break
            except Exception:
                pass
            await asyncio.sleep(0.05)

    assert session_id, "Failed to obtain mcp-session-id after retries"

    # Now wait for FastMCP to be fully initialized by polling until we get a proper response
    ping_payload = {"jsonrpc": "2.0", "method": "tools/list", "id": 0}
    for attempt in range(50):  # Increased retries
        try:
            ping = await client.post(
                "/mcp/mcp.json/",
                headers={**jsonrpc_headers, "mcp-session-id": session_id},
                content=json.dumps(ping_payload),
            )
            # If we get a proper response (even if 401), FastMCP is ready
            if ping.status_code in (200, 401) and ping.content:
                try:
                    ping.json()  # Verify it's valid JSON
                    break
                except json.JSONDecodeError:
                    pass  # Not ready yet
        except Exception:
            pass  # Connection errors are expected during startup
        await asyncio.sleep(0.1)  # Longer sleep to give FastMCP time

    return {"mcp-session-id": session_id}


# Alternative client using LifespanManager
@pytest.fixture
async def client_alt(test_app: Starlette) -> AsyncIterator[httpx.AsyncClient]:
    # Using LifespanManager for httpx 0.28.1
    async with LifespanManager(test_app):
        transport = httpx.ASGITransport(app=test_app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
            timeout=30.0,
            headers={"Accept": "application/json, text/event-stream"},
        ) as c:
            yield c


# Helpers used by tests below
class TestResponse:
    """Helper for JSON-RPC tool responses."""

    def __init__(self, response: httpx.Response):
        self.response = response
        self.status_code = response.status_code
        if response.status_code == 204:
            self.data = {}
        else:
            try:
                self.data = response.json()
            except Exception:
                # Preserve raw text for better error messages if body isn't JSON.
                self.data = {
                    "_raw_text": response.text,
                    "_content_type": response.headers.get("content-type"),
                }

    def assert_success(self) -> dict[str, Any]:
        assert self.status_code == 200, f"Expected 200, got {self.status_code}: {self.data}"
        assert isinstance(self.data, dict) and "result" in self.data, (
            f"No result in response: {self.data}"
        )
        assert not self.data["result"].get("isError", False), f"Tool reported error: {self.data}"
        return self.data["result"]

    def assert_error(self, expected_status: int = 200) -> dict[str, Any]:
        assert self.status_code == expected_status, (
            f"Expected {expected_status}, got {self.status_code}"
        )
        if expected_status == 200:
            assert "result" in self.data, f"No result in response: {self.data}"
            assert self.data["result"].get("isError", False), f"Expected tool error: {self.data}"
        return self.data.get("result", self.data)


@pytest.fixture
def test_response_helper():
    return TestResponse


@pytest.fixture
def anyio_backend():
    """Keep async test execution predictable."""
    return "asyncio"


# Legacy fixtures for backward compatibility with existing tests
@pytest.fixture
def mock_mcp_server():
    """Mock MCP server to avoid startup issues in tests."""
    from unittest.mock import patch

    with patch("app.main.mcp_app") as mock_app:
        # Mock the MCP app to prevent actual server startup
        mock_app.lifespan = None
        mock_app.routes = []
        yield mock_app


@pytest.fixture
def mock_file_system():
    """Mock file system operations for testing."""
    from unittest.mock import patch

    with patch("app.tools.file_system_tools") as mock_fs:
        # Mock file system operations
        mock_fs.list_directory.return_value = {"files": ["test.txt"], "directories": ["test_dir"]}
        mock_fs.read_file.return_value = {"content": "test content", "size": 12}
        mock_fs.write_file.return_value = {"success": True, "bytes_written": 12}
        yield mock_fs


@pytest.fixture
def mock_shell_commands():
    """Mock shell command execution for testing."""
    from unittest.mock import patch

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
    from app.settings import settings

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
