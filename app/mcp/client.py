"""
Minimal async JSON-RPC client for the MCP Server.

Usage:
    from app.mcp.client import MCPClient

    async with MCPClient(base_url="http://127.0.0.1:8000", token="...") as mc:
        ok = await mc.ping()
        tools = await mc.list_tools()
        result = await mc.call_tool("file_system_create_directory", {"path": "/tmp/x"})
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx

JSON = dict[str, Any]


class MCPError(RuntimeError):
    pass


class MCPClient:
    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        timeout: float = 10.0,
        retries: int = 2,
        backoff: float = 0.2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token or os.getenv("MCP_API_TOKEN") or os.getenv("API_TOKEN")
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> MCPClient:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self._client = httpx.AsyncClient(
            base_url=self.base_url, headers=headers, timeout=self.timeout
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _post(self, path: str, payload: JSON) -> httpx.Response:
        if not self._client:
            raise RuntimeError("Use 'async with MCPClient(...)' to start the client.")
        for attempt in range(self.retries + 1):
            try:
                return await self._client.post(path, content=json.dumps(payload))
            except (httpx.ConnectError, httpx.ReadTimeout):
                if attempt == self.retries:
                    raise
                await asyncio.sleep(self.backoff * (2**attempt))

    async def ping(self) -> bool:
        if not self._client:
            raise RuntimeError("Use 'async with MCPClient(...)' to start the client.")
        r = await self._client.get("/health")
        if r.status_code != 200:
            return False
        try:
            r.json()
        except Exception:
            return False
        return True

    async def rpc(
        self,
        method: str,
        params: JSON | None = None,
        id: int | str = 1,
        path: str = "/mcp/mcp.json/",
    ) -> JSON:
        payload: JSON = {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}
        resp = await self._post(path, payload)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            raise MCPError(json.dumps(data["error"]))
        return data

    async def list_tools(self) -> JSON:
        return await self.rpc("tools/list")

    async def call_tool(self, name: str, arguments: JSON | None = None) -> JSON:
        return await self.rpc("tools/call", {"name": name, "arguments": arguments or {}})

    # Optional sync helper
    def call_tool_sync(self, name: str, arguments: JSON | None = None) -> JSON:
        return asyncio.run(self.call_tool(name, arguments))
