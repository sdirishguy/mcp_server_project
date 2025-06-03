# app/main.py

import logging
from mcp.server.fastmcp import FastMCP

from .tools import (
    file_system_create_directory_tool,
    file_system_write_file_tool,
    file_system_read_file_tool,
    file_system_list_directory_tool,
    execute_shell_command_tool,
)

# You can configure logging level or format here if you wish.
logging.basicConfig(level=logging.INFO)

mcp = FastMCP("CodeGen & CyberOps MCP Server")

# Register tool handlers
@mcp.tool(name="file_system_create_directory", description="Creates a new directory. Path is relative to the server's configured base working directory.")
async def file_system_create_directory(params: dict) -> dict:
    return await file_system_create_directory_tool(params)

@mcp.tool(name="file_system_write_file", description="Writes or overwrites a file with given content. Path is relative to the server's configured base working directory.")
async def file_system_write_file(params: dict) -> dict:
    return await file_system_write_file_tool(params)

@mcp.tool(name="file_system_read_file", description="Reads the content of a file. Path is relative to the server's configured base working directory.")
async def file_system_read_file(params: dict) -> dict:
    return await file_system_read_file_tool(params)

@mcp.tool(name="file_system_list_directory", description="Lists files and subdirectories within a specified path. Path is relative to the server's configured base working directory.")
async def file_system_list_directory(params: dict) -> dict:
    return await file_system_list_directory_tool(params)

@mcp.tool(name="execute_shell_command", description="Executes a given shell command within the server's environment. WARNING: Use with caution.")
async def execute_shell_command(params: dict) -> dict:
    return await execute_shell_command_tool(params)

# Export the ASGI app for uvicorn or other ASGI servers
app = mcp.streamable_http_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
