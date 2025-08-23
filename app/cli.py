"""
Typer-based CLI for local development and tool operations.
Usage examples:
  python -m app.cli run --reload
  python -m app.cli tools list
  python -m app.cli tools call file_system_read_file --params '{"path":"README.md"}'
  # FastMCP-style also works:
  python -m app.cli tools call file_system_read_file --params '{"arguments":{"path":"README.md"}}'
"""

from __future__ import annotations

import asyncio
import inspect
import json
import subprocess
from collections.abc import Awaitable, Callable
from typing import Any, TypedDict, cast

import typer

app = typer.Typer(help="MCP Server CLI")
tools_app = typer.Typer(help="Work with registered tools")
app.add_typer(tools_app, name="tools")


@app.command()
def run(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = True,
    log_level: str = "info",
) -> None:
    """Run the ASGI server."""
    import uvicorn

    uvicorn.run("app.main:app", host=host, port=port, reload=reload, log_level=log_level)


@tools_app.command("list")
def list_tools() -> None:
    """List all registered tools."""
    from app.tools import ALL_TOOLS

    for t in ALL_TOOLS:
        typer.echo(f"{t['name']}: {t['description']}")


DICTY_SINGLE_PARAM_NAMES = {"params", "payload", "data", "arguments", "args"}


def _choose_call_style(handler: Any, payload: dict) -> str:
    """
    Decide whether to call `handler(**payload)` or `handler(payload)`.
    """
    try:
        sig = inspect.signature(handler)
    except (ValueError, TypeError):
        return "kwargs"

    params = list(sig.parameters.values())

    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params):
        return "kwargs"

    pos = [p for p in params if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)]
    if len(pos) == 1:
        return "single" if pos[0].name in DICTY_SINGLE_PARAM_NAMES else "kwargs"

    return "kwargs"


class ToolEntry(TypedDict):
    name: str
    description: str
    handler: Callable[..., Awaitable[dict[str, Any]]]


@tools_app.command("call")
def call_tool(
    name: str,
    params: str | None = typer.Option(
        None,
        help="JSON string of params or {'arguments': {...}}",
    ),
) -> None:
    """Execute a tool by its name with optional JSON params."""
    from app.tools import ALL_TOOLS

    tools_typed: list[ToolEntry] = cast("list[ToolEntry]", ALL_TOOLS)
    mapping: dict[str, Callable[..., Awaitable[dict[str, Any]]]] = {t["name"]: t["handler"] for t in tools_typed}
    h = mapping.get(name)
    if h is None:
        typer.echo(f"Tool not found: {name}", err=True)
        raise typer.Exit(1)
    handler: Callable[..., Awaitable[dict[str, Any]]] = h

    try:
        data = json.loads(params) if params else {}
    except json.JSONDecodeError as exc:
        typer.echo(f"Invalid JSON for --params: {exc}", err=True)
        raise typer.Exit(2)

    payload: dict[str, Any] = data if isinstance(data, dict) else {}
    if "arguments" in payload and isinstance(payload["arguments"], dict):
        payload = payload["arguments"]

    call_style = _choose_call_style(handler, payload)

    async def _run() -> None:
        try:
            if call_style == "kwargs":
                res = await handler(**payload)
            else:
                res = await handler(payload)
        except TypeError:
            try:
                if call_style == "kwargs":
                    res = await handler(payload)
                else:
                    res = await handler(**payload)
            except Exception as exc:
                typer.echo(f"Error calling tool: {exc}", err=True)
                raise typer.Exit(3)
        except Exception as exc:
            typer.echo(f"Error calling tool: {exc}", err=True)
            raise typer.Exit(3)

        try:
            typer.echo(json.dumps(res, indent=2))
        except Exception:
            typer.echo(str(res))

    asyncio.run(_run())


@app.command()
def test(path: str = "tests", extra: str = "") -> None:
    """Run test suite via pytest."""
    cmd = ["pytest", path]
    if extra:
        cmd.extend(extra.split())
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    app()
