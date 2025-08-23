"""
FastMCP Integration Tests.

These tests validate the FastMCP lifespan integration fix and ensure
proper JSON-RPC tool execution through the ASGI application.
"""

import asyncio
import json
import os

import httpx
import pytest


class TestFastMCPIntegration:
    async def test_fastmcp_lifespan_initialization(
        self,
        client: httpx.AsyncClient,
        jsonrpc_headers,
        mcp_session_headers,
    ):
        """Test that FastMCP lifespan initializes correctly."""
        # If we reached here, we have a session id via mcp_session_headers.
        # Now call a PROTECTED tool WITHOUT auth; it should require 401.
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "file_system_read_file", "arguments": {"path": "x"}},
            "id": 1,
        }
        resp = await client.post(
            "/mcp/mcp.json/",
            headers={**jsonrpc_headers, **mcp_session_headers},
            content=json.dumps(payload),
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"

    async def test_file_system_tools_flow(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict[str, str],
        jsonrpc_headers: dict[str, str],
        mcp_session_headers: dict[str, str],
        test_response_helper,
    ):
        """Test complete file system tool workflow."""
        # 1) mkdir
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "file_system_create_directory",
                "arguments": {"path": "test_flow_dir"},
            },
            "id": 1,
        }
        r = await client.post(
            "/mcp/mcp.json/",
            headers={**jsonrpc_headers, **mcp_session_headers, **auth_headers},
            content=json.dumps(payload),
        )
        result = test_response_helper(r).assert_success()
        assert "test_flow_dir" in result["content"][0]["text"]

        # 2) write
        content = "Hello from FastMCP integration test!"
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "file_system_write_file",
                "arguments": {"path": "test_flow_dir/test.txt", "content": content},
            },
            "id": 2,
        }
        r = await client.post(
            "/mcp/mcp.json/",
            headers={**jsonrpc_headers, **mcp_session_headers, **auth_headers},
            content=json.dumps(payload),
        )
        test_response_helper(r).assert_success()

        # 3) read
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "file_system_read_file",
                "arguments": {"path": "test_flow_dir/test.txt"},
            },
            "id": 3,
        }
        r = await client.post(
            "/mcp/mcp.json/",
            headers={**jsonrpc_headers, **mcp_session_headers, **auth_headers},
            content=json.dumps(payload),
        )
        result = test_response_helper(r).assert_success()
        assert result["content"][0]["text"] == content

        # 4) list
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "file_system_list_directory",
                "arguments": {"path": "test_flow_dir"},
            },
            "id": 4,
        }
        r = await client.post(
            "/mcp/mcp.json/",
            headers={**jsonrpc_headers, **mcp_session_headers, **auth_headers},
            content=json.dumps(payload),
        )
        result = test_response_helper(r).assert_success()
        entries = json.loads(result["content"][0]["text"])
        assert any("test.txt" in item for item in entries)

    async def test_concurrent_tool_execution(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict[str, str],
        jsonrpc_headers: dict[str, str],
        mcp_session_headers: dict[str, str],
        test_response_helper,
    ):
        """Test concurrent tool execution to ensure thread safety."""

        async def write(i: int) -> httpx.Response:
            payload = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "file_system_write_file",
                    "arguments": {"path": f"concurrent_{i}.txt", "content": f"file {i}"},
                },
                "id": i,
            }
            return await client.post(
                "/mcp/mcp.json/",
                headers={**jsonrpc_headers, **mcp_session_headers, **auth_headers},
                content=json.dumps(payload),
            )

        responses = await asyncio.gather(*[write(i) for i in range(5)])
        for r in responses:
            test_response_helper(r).assert_success()


class TestMCPAuth:
    async def test_requires_auth(
        self, client: httpx.AsyncClient, jsonrpc_headers, mcp_session_headers
    ):
        """Test that MCP endpoints require authentication."""
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "file_system_read_file", "arguments": {"path": "x"}},
            "id": 1,
        }
        r = await client.post(
            "/mcp/mcp.json/",
            headers={**jsonrpc_headers, **mcp_session_headers},
            content=json.dumps(payload),
        )
        assert r.status_code == 401

    async def test_invalid_token(
        self, client: httpx.AsyncClient, jsonrpc_headers, mcp_session_headers
    ):
        """Test that invalid tokens are rejected."""
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "file_system_read_file", "arguments": {"path": "x"}},
            "id": 1,
        }
        r = await client.post(
            "/mcp/mcp.json/",
            headers={**jsonrpc_headers, **mcp_session_headers, "Authorization": "Bearer nope"},
            content=json.dumps(payload),
        )
        assert r.status_code == 401


class TestLLMTools:
    async def test_llm_local_placeholder(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict[str, str],
        jsonrpc_headers: dict[str, str],
        mcp_session_headers: dict[str, str],
        test_response_helper,
    ):
        """Test local LLM placeholder tool."""
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "llm_generate_code_local", "arguments": {}},
            "id": 1,
        }
        r = await client.post(
            "/mcp/mcp.json/",
            headers={**jsonrpc_headers, **mcp_session_headers, **auth_headers},
            content=json.dumps(payload),
        )
        result = test_response_helper(r).assert_success()
        assert "coming soon" in result["content"][0]["text"].lower()

    @pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
    async def test_openai_code_generation(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict[str, str],
        jsonrpc_headers: dict[str, str],
        mcp_session_headers: dict[str, str],
        test_response_helper,
    ):
        """Test OpenAI code generation tool."""
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "llm_generate_code_openai",
                "arguments": {
                    "prompt": "Write a hello world",
                    "language": "python",
                    "max_tokens": 100,
                },
            },
            "id": 1,
        }
        r = await client.post(
            "/mcp/mcp.json/",
            headers={**jsonrpc_headers, **mcp_session_headers, **auth_headers},
            content=json.dumps(payload),
        )
        result = test_response_helper(r).assert_success()
        assert result["content"][0]["text"]


class TestPerf:
    async def test_rapid_sequential_requests(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict[str, str],
        jsonrpc_headers: dict[str, str],
        mcp_session_headers: dict[str, str],
        test_response_helper,
    ):
        """Test rapid sequential requests to ensure stability."""
        for i in range(10):
            payload = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "file_system_create_directory",
                    "arguments": {"path": f"perf_{i}"},
                },
                "id": i,
            }
            r = await client.post(
                "/mcp/mcp.json/",
                headers={**jsonrpc_headers, **mcp_session_headers, **auth_headers},
                content=json.dumps(payload),
            )
            test_response_helper(r).assert_success()


class TestShellTools:
    async def test_shell_command_execution(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict[str, str],
        jsonrpc_headers: dict[str, str],
        mcp_session_headers: dict[str, str],
        test_response_helper,
    ):
        """Test shell command execution tool."""
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "execute_shell_command", "arguments": {"command": "echo 'test'"}},
            "id": 1,
        }
        r = await client.post(
            "/mcp/mcp.json/",
            headers={**jsonrpc_headers, **mcp_session_headers, **auth_headers},
            content=json.dumps(payload),
        )
        result = test_response_helper(r).assert_success()
        assert "test" in result["content"][0]["text"]


class TestErrorHandling:
    async def test_invalid_tool_name(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict[str, str],
        jsonrpc_headers: dict[str, str],
        mcp_session_headers: dict[str, str],
        test_response_helper,
    ):
        """Test error handling for invalid tool names."""
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "invalid_tool", "arguments": {}},
            "id": 1,
        }
        r = await client.post(
            "/mcp/mcp.json/",
            headers={**jsonrpc_headers, **mcp_session_headers, **auth_headers},
            content=json.dumps(payload),
        )
        # Many JSON-RPC servers return HTTP 200 with a JSON-RPC error envelope.
        # If your server uses HTTP 200, this will pass; otherwise adjust expected_status.
        result = test_response_helper(r).assert_error(expected_status=200)
        assert "error" in result

    async def test_invalid_json_rpc(
        self,
        client: httpx.AsyncClient,
        auth_headers: dict[str, str],
        jsonrpc_headers: dict[str, str],
        mcp_session_headers: dict[str, str],
    ):
        """Test error handling for invalid JSON-RPC requests."""
        r = await client.post(
            "/mcp/mcp.json/",
            headers={**jsonrpc_headers, **mcp_session_headers, **auth_headers},
            content=json.dumps({"invalid": "request"}),
        )
        assert r.status_code in [400, 422]  # Bad request or validation error
