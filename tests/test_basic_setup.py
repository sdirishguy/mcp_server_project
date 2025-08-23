"""
Basic setup test to verify the app starts correctly.
"""

import json

import pytest


@pytest.mark.anyio
async def test_app_starts(client):
    """Test that the app starts and responds to basic requests."""
    # Test health endpoint
    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"


@pytest.mark.anyio
async def test_auth_endpoint_works(client):
    """Test that the auth endpoint responds."""
    r = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "token" in data


@pytest.mark.anyio
async def test_mcp_endpoint_exists(client, jsonrpc_headers):
    """Test that the MCP endpoint exists and responds."""
    payload = {"jsonrpc": "2.0", "method": "tools/list", "id": 1}
    r = await client.post(
        "/mcp/mcp.json/",
        headers=jsonrpc_headers,
        content=json.dumps(payload),
    )
    # Should get 400 (missing session ID), 401 (auth required), or 200 (success)
    assert r.status_code in [200, 401, 400]

    # If it's 400, check if it's the expected "Missing session ID" error
    if r.status_code == 400:
        data = r.json()
        assert "error" in data
        # This confirms FastMCP is working and just needs session ID
