"""
A small FastAPI app mounted at /docs to provide interactive API documentation.
Accepts both plain params ({"path": "..."}) and FastMCP-style ({"arguments": {...}}).
Calls tool handlers with kwargs when appropriate.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from inspect import Parameter, signature
from typing import Any, TypedDict, cast

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.tools import ALL_TOOLS

app = FastAPI(
    title="MCP Server API",
    version="0.1.2",
    description="Interactive docs for common MCP endpoints and tools.",
    docs_url="/",
    redoc_url=None,
)


class ToolInfo(BaseModel):
    name: str
    description: str


class RunToolRequest(BaseModel):
    name: str = Field(description="Registered tool name")
    params: dict[str, Any] = Field(default_factory=dict)


class RunToolResponse(BaseModel):
    content: list[dict[str, Any]]
    isError: bool | None = False


class ToolEntry(TypedDict):
    name: str
    description: str
    # Async callables returning the MCP-style dict result
    handler: Callable[..., Awaitable[dict[str, Any]]]


_TOOLS: list[ToolEntry] = cast("list[ToolEntry]", ALL_TOOLS)


@app.get("/tools", response_model=list[ToolInfo], summary="List available tools")
async def list_tools() -> list[ToolInfo]:
    return [ToolInfo(name=t["name"], description=t["description"]) for t in _TOOLS]


def _wants_single_param(handler: Any) -> bool:
    """Detect if the handler likely expects a single positional/keyword param (e.g., 'params')."""
    try:
        sig = signature(handler)
    except (ValueError, TypeError):
        return False
    params = [
        p for p in sig.parameters.values() if p.kind in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD)
    ]
    return len(params) == 1 and params[0].kind == Parameter.POSITIONAL_OR_KEYWORD


@app.post("/tools/run", response_model=RunToolResponse, summary="Execute a tool by name")
async def run_tool(req: RunToolRequest) -> RunToolResponse:
    # Build a name->handler map (keeps lines short + helps mypy)
    mapping: dict[str, Callable[..., Awaitable[dict[str, Any]]]] = {t["name"]: t["handler"] for t in _TOOLS}
    h = mapping.get(req.name)
    if h is None:
        raise HTTPException(status_code=404, detail=f"Tool not found: {req.name}")
    handler: Callable[..., Awaitable[dict[str, Any]]] = h

    # Support BOTH shapes:
    # 1) plain: {"params": {"path": "notes.txt"}}
    # 2) FastMCP style: {"params": {"arguments": {"path": "notes.txt"}}}
    payload: dict[str, Any] = req.params if isinstance(req.params, dict) else {}
    if "arguments" in payload and isinstance(payload["arguments"], dict):
        payload = payload["arguments"]

    try:
        if _wants_single_param(handler):
            result = await handler(payload)  # handler expects a single dict param
        else:
            result = await handler(**payload)  # handler expects kwargs like path=..., content=...
    except TypeError:
        # Fallback: try the other calling convention
        try:
            result = await handler(payload)
        except Exception as exc:  # pragma: no cover
            return RunToolResponse(
                content=[{"type": "text", "text": f"Internal Server Error: {exc}"}],
                isError=True,
            )
    except Exception as exc:  # pragma: no cover
        return RunToolResponse(
            content=[{"type": "text", "text": f"Internal Server Error: {exc}"}],
            isError=True,
        )

    if not isinstance(result, dict) or "content" not in result:
        raise HTTPException(status_code=500, detail="Tool returned an invalid result")

    return result  # type: ignore[return-value]
