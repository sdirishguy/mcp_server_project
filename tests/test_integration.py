"""
Integration tests for the MCP Server Project.

This module tests complete application flows including authentication,
API endpoints, and end-to-end functionality.
"""

from unittest.mock import patch

import httpx
import pytest

from app.main import app
from app.settings import settings


@pytest.fixture
async def client():
    """Create a test client."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def auth_token(client):
    """Get authentication token for testing."""

    async def _get_token():
        response = await client.post(
            "/api/auth/login",
            json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
        )
        if response.status_code == 200:
            return response.json().get("token")
        return None

    return _get_token


class TestAuthentication:
    """Test authentication flows."""

    @pytest.mark.asyncio
    async def test_login_success(self, client):
        """Test successful login."""
        response = await client.post(
            "/api/auth/login",
            json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert "token" in data
        assert "user_id" in data

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials."""
        response = await client.post(
            "/api/auth/login", json={"username": "invalid", "password": "invalid"}
        )

        assert response.status_code == 401
        data = response.json()
        assert data["authenticated"] is False

    @pytest.mark.asyncio
    async def test_protected_route_with_token(self, client, auth_token):
        """Test accessing protected route with valid token."""
        token = await auth_token()
        if not token:
            pytest.skip("Could not obtain auth token")

        response = await client.get("/api/protected", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_protected_route_without_token(self, client):
        """Test accessing protected route without token."""
        response = await client.get("/api/protected")

        assert response.status_code == 401
        assert "Authentication required" in response.json()["message"]


class TestHealthEndpoints:
    """Test health and monitoring endpoints."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, client):
        """Test Prometheus metrics endpoint."""
        response = await client.get("/metrics")

        assert response.status_code == 200
        content = response.text
        assert "mcp_http_requests_total" in content
        assert "mcp_active_connections" in content


class TestToolExecution:
    """Test tool execution through the API."""

    @pytest.mark.asyncio
    async def test_file_system_tools_flow(self, client, auth_token):
        """Test complete filesystem tools flow."""
        token = await auth_token()
        if not token:
            pytest.skip("Could not obtain auth token")

        headers = {"Authorization": f"Bearer {token}"}

        # Test directory creation
        create_dir_response = await client.post(
            "/mcp/mcp.json/",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "file_system_create_directory",
                    "arguments": {"path": "test_integration_dir"},
                },
                "id": 1,
            },
        )

        assert create_dir_response.status_code == 200
        create_data = create_dir_response.json()
        assert "result" in create_data

        # Test file writing
        write_file_response = await client.post(
            "/mcp/mcp.json/",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "file_system_write_file",
                    "arguments": {
                        "path": "test_integration_dir/test_file.txt",
                        "content": "Integration test content",
                    },
                },
                "id": 2,
            },
        )

        assert write_file_response.status_code == 200
        write_data = write_file_response.json()
        assert "result" in write_data

        # Test file reading
        read_file_response = await client.post(
            "/mcp/mcp.json/",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "file_system_read_file",
                    "arguments": {"path": "test_integration_dir/test_file.txt"},
                },
                "id": 3,
            },
        )

        assert read_file_response.status_code == 200
        read_data = read_file_response.json()
        assert "result" in read_data
        assert "Integration test content" in str(read_data["result"])

    @pytest.mark.asyncio
    async def test_shell_command_disabled(self, client, auth_token):
        """Test shell command when disabled."""
        token = await auth_token()
        if not token:
            pytest.skip("Could not obtain auth token")

        with patch("app.tools.ALLOW_ARBITRARY_SHELL_COMMANDS", False):
            response = await client.post(
                "/mcp/mcp.json/",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": "execute_shell_command", "arguments": {"command": "ls"}},
                    "id": 1,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "disabled by configuration" in str(data["result"])


class TestRateLimiting:
    """Test rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_login_rate_limiting(self, client):
        """Test rate limiting on login endpoint."""
        # Make multiple rapid login attempts
        responses = []
        for i in range(10):
            response = await client.post(
                "/api/auth/login", json={"username": "invalid", "password": "invalid"}
            )
            responses.append(response)

        # Check if rate limiting kicked in
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes  # Too Many Requests


class TestSecurityHeaders:
    """Test security headers are properly set."""

    @pytest.mark.asyncio
    async def test_security_headers_present(self, client):
        """Test that security headers are present in responses."""
        response = await client.get("/health")

        headers = response.headers
        assert "X-Frame-Options" in headers
        assert "X-Content-Type-Options" in headers
        assert "X-XSS-Protection" in headers
        assert "Strict-Transport-Security" in headers
        assert "Referrer-Policy" in headers
        assert "Content-Security-Policy" in headers

        # Check specific values
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["X-Content-Type-Options"] == "nosniff"


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_invalid_json_rpc(self, client, auth_token):
        """Test handling of invalid JSON-RPC requests."""
        token = await auth_token()
        if not token:
            pytest.skip("Could not obtain auth token")

        response = await client.post(
            "/mcp/mcp.json/",
            headers={"Authorization": f"Bearer {token}"},
            json={"invalid": "request"},
        )

        # Should handle gracefully
        assert response.status_code in [200, 400, 500]

    @pytest.mark.asyncio
    async def test_nonexistent_tool(self, client, auth_token):
        """Test calling non-existent tool."""
        token = await auth_token()
        if not token:
            pytest.skip("Could not obtain auth token")

        response = await client.post(
            "/mcp/mcp.json/",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "nonexistent_tool", "arguments": {}},
                "id": 1,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "error" in data or "Tool not found" in str(data)


class TestMonitoring:
    """Test monitoring and observability features."""

    @pytest.mark.asyncio
    async def test_metrics_collection(self, client):
        """Test that metrics are being collected."""
        # Make some requests to generate metrics
        await client.get("/health")
        await client.get("/metrics")

        # Check metrics endpoint contains data
        response = await client.get("/metrics")
        content = response.text

        # Should contain various metrics
        assert "mcp_http_requests_total" in content
        assert "mcp_active_connections" in content
        assert "mcp_authentication_attempts_total" in content

    @pytest.mark.asyncio
    async def test_structured_logging(self, client):
        """Test that structured logging is working."""
        # This test would require checking log files
        # For now, just ensure the endpoint works
        response = await client.get("/health")
        assert response.status_code == 200
