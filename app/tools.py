# app/tools.py

import asyncio
import shlex
import json
from pathlib import Path

from mcp.types import CallToolResult, TextContent  # Use ImageContent, EmbeddedResource if you add other content types
from .config import MCP_BASE_WORKING_DIR, ALLOW_ARBITRARY_SHELL_COMMANDS, logger

def resolve_path(rel_path: str) -> Path:
    # Prevent path traversal
    base = MCP_BASE_WORKING_DIR.resolve()
    target = (base / rel_path.lstrip("/")).resolve()
    if base not in target.parents and base != target:
        raise ValueError(f"Access denied: Path '{target}' is outside of base '{base}'")
    return target

async def file_system_create_directory_tool(params: dict) -> CallToolResult:
    path_str = params.get("path")
    if not path_str or not isinstance(path_str, str):
        return CallToolResult(
            content=[TextContent(type="text", text="Parameter 'path' (str) is required.")],
            isError=True
        )
    try:
        target = resolve_path(path_str)
        target.mkdir(parents=True, exist_ok=True)
        logger.info(f"Directory created: {target}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"Directory '{path_str}' created successfully.")],
            isError=False
        )
    except Exception as e:
        logger.error(f"Error creating directory '{path_str}': {e}", exc_info=True)
        return CallToolResult(
            content=[TextContent(type="text", text=f"Failed to create directory: {e}")],
            isError=True
        )

async def file_system_write_file_tool(params: dict) -> CallToolResult:
    path_str = params.get("path")
    content_str = params.get("content")
    if not path_str or not isinstance(path_str, str):
        return CallToolResult(
            content=[TextContent(type="text", text="Parameter 'path' (str) is required.")],
            isError=True
        )
    if not isinstance(content_str, str):
        return CallToolResult(
            content=[TextContent(type="text", text="Parameter 'content' (str) is required.")],
            isError=True
        )
    try:
        target = resolve_path(path_str)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content_str, encoding="utf-8")
        logger.info(f"File written: {target}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"File '{path_str}' written successfully.")],
            isError=False
        )
    except Exception as e:
        logger.error(f"Error writing file '{path_str}': {e}", exc_info=True)
        return CallToolResult(
            content=[TextContent(type="text", text=f"Failed to write file: {e}")],
            isError=True
        )

async def file_system_read_file_tool(params: dict) -> CallToolResult:
    path_str = params.get("path")
    if not path_str or not isinstance(path_str, str):
        return CallToolResult(
            content=[TextContent(type="text", text="Parameter 'path' (str) is required.")],
            isError=True
        )
    try:
        target = resolve_path(path_str)
        if not target.is_file():
            return CallToolResult(
                content=[TextContent(type="text", text="File not found.")],
                isError=True
            )
        content = target.read_text(encoding="utf-8")
        logger.info(f"File read: {target}")
        return CallToolResult(
            content=[TextContent(type="text", text=content)],
            isError=False
        )
    except Exception as e:
        logger.error(f"Error reading file '{path_str}': {e}", exc_info=True)
        return CallToolResult(
            content=[TextContent(type="text", text=f"Failed to read file: {e}")],
            isError=True
        )

async def file_system_list_directory_tool(params: dict) -> CallToolResult:
    path_str = params.get("path", ".")
    if not isinstance(path_str, str):
        return CallToolResult(
            content=[TextContent(type="text", text="Parameter 'path' (str) is required.")],
            isError=True
        )
    try:
        target = resolve_path(path_str)
        if not target.is_dir():
            return CallToolResult(
                content=[TextContent(type="text", text="Directory not found.")],
                isError=True
            )
        items = []
        for item in target.iterdir():
            item_type = "dir" if item.is_dir() else "file"
            items.append(f"{item.name} ({item_type})")
        logger.info(f"Listed directory: {target}")
        if not items:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Directory '{path_str}' is empty.")],
                isError=False
            )
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(items))],
            isError=False
        )
    except Exception as e:
        logger.error(f"Error listing directory '{path_str}': {e}", exc_info=True)
        return CallToolResult(
            content=[TextContent(type="text", text=f"Failed to list directory: {e}")],
            isError=True
        )

async def execute_shell_command_tool(params: dict) -> CallToolResult:
    command_str = params.get("command")
    working_dir = params.get("working_directory", ".")
    if not command_str or not isinstance(command_str, str):
        return CallToolResult(
            content=[TextContent(type="text", text="Parameter 'command' (str) is required.")],
            isError=True
        )
    if not ALLOW_ARBITRARY_SHELL_COMMANDS:
        return CallToolResult(
            content=[TextContent(type="text", text="Shell command execution is disabled.")],
            isError=True
        )
    try:
        cwd = resolve_path(working_dir)
        command_parts = shlex.split(command_str)
        process = await asyncio.create_subprocess_exec(
            *command_parts,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        result = {
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "return_code": process.returncode,
        }
        logger.info(f"Executed shell command: {command_str} (cwd: {cwd})")
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(result, indent=2))],
            isError=process.returncode != 0
        )
    except Exception as e:
        logger.error(f"Error executing shell command '{command_str}': {e}", exc_info=True)
        return CallToolResult(
            content=[TextContent(type="text", text=f"Failed to execute command: {e}")],
            isError=True
        )
