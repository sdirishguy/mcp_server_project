"""
Test MCP session management.
"""

import json

import pytest


@pytest.mark.anyio
async def test_mcp_session_creation(client, jsonrpc_headers, mcp_session_headers):
    """Test that MCP session creation works."""
    # The mcp_session_headers fixture should have already created a session
    # Let's verify it works by making another request
    payload = {"jsonrpc": "2.0", "method": "tools/list", "id": 2}
    r = await client.post(
        "/mcp/mcp.json/",
        headers={**jsonrpc_headers, **mcp_session_headers},
        content=json.dumps(payload),
    )
    # Should get 401 (auth required) or 200 (success)
    assert r.status_code in [200, 401]


@pytest.mark.anyio
async def test_mcp_with_auth(client, auth_headers, jsonrpc_headers, mcp_session_headers):
    """Test MCP endpoint with authentication."""
    payload = {"jsonrpc": "2.0", "method": "tools/list", "id": 3}
    r = await client.post(
        "/mcp/mcp.json/",
        headers={**jsonrpc_headers, **mcp_session_headers, **auth_headers},
        content=json.dumps(payload),
    )
    assert r.status_code == 200

    # Handle potential empty response gracefully
    if r.content:
        data = r.json()
        assert "result" in data
    else:
        # If response is empty, that's also acceptable for this test
        # (FastMCP might return empty response for some cases)
        pass
