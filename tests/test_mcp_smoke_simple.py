"""
Simple MCP smoke test to verify the lifespan fixes work.
"""

import pytest


@pytest.mark.anyio
async def test_mcp_list_tools(client, mcp_session_headers):
    """Test that tools/list endpoint works with proper FastMCP initialization."""
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    r = await client.post("/mcp/mcp.json/", headers=mcp_session_headers, json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "result" in body
    print(f"Tools response: {body}")


@pytest.mark.anyio
async def test_mcp_health_endpoint(client):
    """Test that health endpoint works independently of FastMCP."""
    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
