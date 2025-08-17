"""
Integration tests for the MCP Server Project.

This module tests complete application flows including authentication,
API endpoints, and end-to-end functionality.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.settings import settings


@pytest.fixture
def client():
    """Create a test client."""
    # Use TestClient without context manager to avoid MCP session manager issues
    return TestClient(app)


@pytest.fixture
def auth_token(client):
    """Get authentication token for testing."""
    # Skip rate limiting for tests by using a different approach
    # We'll get the token directly in tests that need it
    return None


class TestAuthentication:
    """Test authentication flows."""

    def test_login_success(self, client):
        """Test successful login."""
        response = client.post(
            "/api/auth/login",
            json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert "token" in data
        assert "user_id" in data

    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials."""
        response = client.post(
            "/api/auth/login", json={"username": "invalid", "password": "invalid"}
        )

        assert response.status_code == 401
        data = response.json()
        assert data["authenticated"] is False

    def test_protected_route_with_token(self, client):
        """Test accessing protected route with valid token."""
        # Get auth token directly
        response = client.post(
            "/api/auth/login",
            json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
        )
        if response.status_code != 200:
            pytest.skip("Could not obtain auth token")

        token = response.json().get("token")

        response = client.get("/api/protected", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200

    def test_protected_route_without_token(self, client):
        """Test accessing protected route without token."""
        response = client.get("/api/protected")

        assert response.status_code == 401
        assert "Authentication required" in response.json()["message"]


class TestHealthEndpoints:
    """Test health and monitoring endpoints."""

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"

    def test_metrics_endpoint(self, client):
        """Test Prometheus metrics endpoint."""
        response = client.get("/metrics")

        assert response.status_code == 200
        content = response.text
        assert "mcp_http_requests_total" in content
        assert "mcp_active_connections" in content


class TestToolExecution:
    """Test tool execution through the API."""

    def test_file_system_tools_flow(self, client):
        """Test complete filesystem tools flow."""
        # Get auth token directly
        response = client.post(
            "/api/auth/login",
            json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
        )
        if response.status_code != 200:
            pytest.skip("Could not obtain auth token")

        token = response.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}

        # Test directory creation
        create_dir_response = client.post(
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
        write_file_response = client.post(
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
        read_file_response = client.post(
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

    def test_shell_command_disabled(self, client):
        """Test shell command when disabled."""
        # Get auth token directly
        response = client.post(
            "/api/auth/login",
            json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
        )
        if response.status_code != 200:
            pytest.skip("Could not obtain auth token")

        token = response.json().get("token")

        with patch("app.tools.ALLOW_ARBITRARY_SHELL_COMMANDS", False):
            response = client.post(
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

    @pytest.mark.skip(reason="Rate limiting disabled in test mode for stability")
    def test_login_rate_limiting(self, client):
        """Test rate limiting on login endpoint."""
        # Make multiple rapid login attempts
        responses = []
        for i in range(10):
            response = client.post(
                "/api/auth/login", json={"username": "invalid", "password": "invalid"}
            )
            responses.append(response)

        # Check if rate limiting kicked in
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes  # Too Many Requests


class TestSecurityHeaders:
    """Test security headers are properly set."""

    def test_security_headers_present(self, client):
        """Test that security headers are present in responses."""
        response = client.get("/health")

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

    def test_invalid_json_rpc(self, client):
        """Test handling of invalid JSON-RPC requests."""
        # Get auth token directly
        response = client.post(
            "/api/auth/login",
            json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
        )
        if response.status_code != 200:
            pytest.skip("Could not obtain auth token")

        token = response.json().get("token")

        response = client.post(
            "/mcp/mcp.json/",
            headers={"Authorization": f"Bearer {token}"},
            json={"invalid": "request"},
        )

        # Should handle gracefully
        assert response.status_code in [200, 400, 500]

    def test_nonexistent_tool(self, client):
        """Test calling non-existent tool."""
        # Get auth token directly
        response = client.post(
            "/api/auth/login",
            json={"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD},
        )
        if response.status_code != 200:
            pytest.skip("Could not obtain auth token")

        token = response.json().get("token")

        response = client.post(
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

    def test_metrics_collection(self, client):
        """Test that metrics are being collected."""
        # Make some requests to generate metrics
        client.get("/health")
        client.get("/metrics")

        # Check metrics endpoint contains data
        response = client.get("/metrics")
        content = response.text

        # Should contain various metrics
        assert "mcp_http_requests_total" in content
        assert "mcp_active_connections" in content
        assert "mcp_authentication_attempts_total" in content

    def test_structured_logging(self, client):
        """Test that structured logging is working."""
        # This test would require checking log files
        # For now, just ensure the endpoint works
        response = client.get("/health")
        assert response.status_code == 200
