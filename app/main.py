# app/main.py

from mcp.server.fastmcp import FastMCP
from .tools import (
    file_system_create_directory_tool,
    file_system_write_file_tool,
    file_system_read_file_tool,
    file_system_list_directory_tool,
    execute_shell_command_tool,
    llm_generate_code_openai_tool,
    llm_generate_code_gemini_tool,
)

mcp = FastMCP("CodeGen & CyberOps MCP Server")

@mcp.tool(name="file_system_create_directory", description="Creates a directory.")
async def create_dir(params: dict) -> dict:
    return await file_system_create_directory_tool(params)

@mcp.tool(name="file_system_write_file", description="Writes a file.")
async def write_file(params: dict) -> dict:
    return await file_system_write_file_tool(params)

@mcp.tool(name="file_system_read_file", description="Reads a file.")
async def read_file(params: dict) -> dict:
    return await file_system_read_file_tool(params)

@mcp.tool(name="file_system_list_directory", description="Lists directory contents.")
async def list_dir(params: dict) -> dict:
    return await file_system_list_directory_tool(params)

@mcp.tool(name="execute_shell_command", description="Executes a shell command.")
async def exec_cmd(params: dict) -> dict:
    return await execute_shell_command_tool(params)

@mcp.tool(name="llm_generate_code_openai", description="Generate code with OpenAI GPT.")
async def llm_code_openai(params: dict) -> dict:
    return await llm_generate_code_openai_tool(params)

@mcp.tool(name="llm_generate_code_gemini", description="Generate code with Gemini.")
async def llm_code_gemini(params: dict) -> dict:
    return await llm_generate_code_gemini_tool(params)

app = mcp.streamable_http_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
