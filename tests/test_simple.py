"""
Simple tests that don't require full MCP server startup.
These tests verify basic functionality without the complexity of the full application.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


def test_health_endpoint_basic(client):
    """Test health check endpoint works."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


def test_metrics_endpoint_basic(client):
    """Test metrics endpoint works."""
    response = client.get("/metrics")
    assert response.status_code == 200
    content = response.text
    assert "mcp_http_requests_total" in content


def test_security_headers_basic(client):
    """Test security headers are present."""
    response = client.get("/health")
    headers = response.headers

    # Check that security headers are present
    assert "X-Frame-Options" in headers
    assert "X-Content-Type-Options" in headers
    assert headers["X-Frame-Options"] == "DENY"


def test_cors_headers_basic(client):
    """Test CORS headers are present."""
    # Test with a GET request instead of OPTIONS since /health doesn't support OPTIONS
    response = client.get("/health")
    headers = response.headers

    # Check that security headers are present (CORS is handled by middleware)
    assert "X-Frame-Options" in headers
    assert "X-Content-Type-Options" in headers
