# app/main.py

from mcp.server.fastmcp import FastMCP
from .tools import (
    file_system_create_directory_tool,
    file_system_write_file_tool,
    file_system_read_file_tool,
    file_system_list_directory_tool,
    execute_shell_command_tool,
)
import logging

mcp = FastMCP("CodeGen & CyberOps MCP Server")

# -- Register tools using the expected MCP naming and schema --

@mcp.tool(
    name="file_system_create_directory",
    description="Creates a new directory. Path is relative to the server's configured base working directory.",
    input_schema={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Directory path."}},
        "required": ["path"],
    },
)
async def create_directory(params: dict) -> dict:
    return await file_system_create_directory_tool(params)

@mcp.tool(
    name="file_system_write_file",
    description="Writes or overwrites a file. Path is relative to the server's configured base working directory.",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path."},
            "content": {"type": "string", "description": "File content."},
        },
        "required": ["path", "content"],
    },
)
async def write_file(params: dict) -> dict:
    return await file_system_write_file_tool(params)

@mcp.tool(
    name="file_system_read_file",
    description="Reads the content of a file. Path is relative to the server's configured base working directory.",
    input_schema={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "File path."}},
        "required": ["path"],
    },
)
async def read_file(params: dict) -> dict:
    return await file_system_read_file_tool(params)

@mcp.tool(
    name="file_system_list_directory",
    description="Lists files and subdirectories within a specified path.",
    input_schema={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Directory path."}},
        "required": ["path"],
    },
)
async def list_directory(params: dict) -> dict:
    return await file_system_list_directory_tool(params)

@mcp.tool(
    name="execute_shell_command",
    description="Executes a given shell command within the server's environment. WARNING: Use with caution.",
    input_schema={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute."},
            "working_directory": {
                "type": "string",
                "description": "Optional working directory. Defaults to base.",
            },
        },
        "required": ["command"],
    },
)
async def execute_command(params: dict) -> dict:
    return await execute_shell_command_tool(params)

# -- MCP ASGI app for Uvicorn --
app = mcp.streamable_http_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
