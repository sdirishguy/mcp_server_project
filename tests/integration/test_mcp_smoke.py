"""
Simple MCP smoke test using the MCP client.
"""

import pytest


@pytest.mark.anyio
async def test_mcp_list_tools(client, mcp_session_headers):
    """Test that we can list tools using direct HTTP calls."""
    # Test ping first
    r = await client.get("/health")
    assert r.status_code == 200

    # Test listing tools
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    r = await client.post("/mcp/mcp.json/", headers=mcp_session_headers, json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "result" in data
    print(f"Tools response: {data}")


@pytest.mark.anyio
async def test_mcp_basic_functionality(client, mcp_session_headers):
    """Test basic MCP functionality."""
    # Test ping
    r = await client.get("/health")
    assert r.status_code == 200

    # Test RPC call
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    r = await client.post("/mcp/mcp.json/", headers=mcp_session_headers, json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "result" in data
    print(f"RPC response: {data}")
