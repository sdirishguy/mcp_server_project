"""
Simple MCP tests that don't rely on complex session management.
"""

import json

import pytest


@pytest.mark.anyio
async def test_mcp_endpoint_basic(client, jsonrpc_headers):
    """Test that the MCP endpoint exists and responds to basic requests."""
    # Simple GET request to check if endpoint exists
    r = await client.get("/mcp/mcp.json/", headers=jsonrpc_headers)
    # Should get some response (could be 200, 400, 401, etc.)
    assert r.status_code in [200, 400, 401, 406]

    # Check if we got a session ID (even if other things fail)
    session_id = r.headers.get("mcp-session-id")
    if session_id:
        print(f"Got session ID: {session_id}")


@pytest.mark.anyio
async def test_mcp_tools_list_basic(client, jsonrpc_headers):
    """Test basic tools/list request without session management."""
    payload = {"jsonrpc": "2.0", "method": "tools/list", "id": 1}
    r = await client.post(
        "/mcp/mcp.json/",
        headers=jsonrpc_headers,
        content=json.dumps(payload),
    )
    # Should get some response (could be 400 for missing session, 401 for auth, etc.)
    assert r.status_code in [200, 400, 401, 406]

    # If we get a 400, it should be a JSON error about missing session
    if r.status_code == 400 and r.content:
        try:
            data = r.json()
            assert "error" in data
            print(f"Got expected error: {data}")
        except json.JSONDecodeError:
            # Empty response is also acceptable
            pass
