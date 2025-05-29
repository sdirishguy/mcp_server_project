# app/tools.py
import asyncio
import json
import shlex
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Union, Optional

import mcp.types # Import the types module directly
from mcp import Tool, Resource # These are available at top-level

from .config import MCP_BASE_WORKING_DIR, ALLOW_ARBITRARY_SHELL_COMMANDS, logger

# _resolve_and_verify_path function remains the same
def _is_path_within_base(path_to_check: Path, base_path: Path) -> bool:
    try:
        return base_path == path_to_check or base_path in path_to_check.resolve().parents
    except Exception:
        return False

def _resolve_and_verify_path(user_path_str: str) -> Path:
    base = MCP_BASE_WORKING_DIR.resolve()
    normalized_user_path_str = user_path_str.lstrip('/')
    resolved_path = (base / normalized_user_path_str).resolve()
    if not _is_path_within_base(resolved_path, base):
        logger.warning(
            f"Path traversal attempt or access outside base directory denied: "
            f"User path '{user_path_str}' resolved to '{resolved_path}', "
            f"which is outside base '{base}'"
        )
        raise ValueError(f"Path is outside the allowed base directory: {user_path_str}")
    return resolved_path

# --- Revised Tool Handlers using qualified mcp.types ---

async def file_system_create_directory_tool(params: Dict[str, Any]) -> mcp.types.CallToolResult:
    tool_name = "file_system_create_directory"
    logger.info(f"Tool '{tool_name}' called with parameters: {params}")
    path_str = params.get("path")

    if not path_str or not isinstance(path_str, str):
        return mcp.types.CallToolResult(error=mcp.types.ErrorData(code=mcp.types.INVALID_PARAMETERS, message=f"Tool '{tool_name}': 'path' parameter is required and must be a string."))

    try:
        target_path = _resolve_and_verify_path(path_str)
        target_path.mkdir(parents=True, exist_ok=True)
        relative_path_str = str(target_path.relative_to(MCP_BASE_WORKING_DIR.resolve()))
        logger.info(f"Directory created or already exists at resolved path: {target_path} (relative: {relative_path_str})")
        return mcp.types.CallToolResult(results=[mcp.types.Content(type=mcp.types.ContentType.TEXT, data=f"Directory '{relative_path_str}' created or already exists.")])
    except ValueError as e:
        logger.error(f"Tool '{tool_name}': Invalid path '{path_str}'. Error: {e}")
        return mcp.types.CallToolResult(error=mcp.types.ErrorData(code=mcp.types.INVALID_REQUEST, message=str(e)))
    except Exception as e:
        logger.error(f"Tool '{tool_name}': Error creating directory '{path_str}'. Error: {e}", exc_info=True)
        return mcp.types.CallToolResult(error=mcp.types.ErrorData(code=mcp.types.INTERNAL_ERROR, message=f"Failed to create directory: {e}"))

async def file_system_write_file_tool(params: Dict[str, Any]) -> mcp.types.CallToolResult:
    tool_name = "file_system_write_file"
    logger.info(f"Tool '{tool_name}' called with parameters: {params}")
    path_str = params.get("path")
    content_str = params.get("content")

    if not path_str or not isinstance(path_str, str):
        return mcp.types.CallToolResult(error=mcp.types.ErrorData(code=mcp.types.INVALID_PARAMETERS, message=f"Tool '{tool_name}': 'path' parameter is required and must be a string."))
    if content_str is None or not isinstance(content_str, str):
        return mcp.types.CallToolResult(error=mcp.types.ErrorData(code=mcp.types.INVALID_PARAMETERS, message=f"Tool '{tool_name}': 'content' parameter is required and must be a string."))

    try:
        target_path = _resolve_and_verify_path(path_str)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content_str, encoding="utf-8")
        relative_path_str = str(target_path.relative_to(MCP_BASE_WORKING_DIR.resolve()))
        logger.info(f"File written to resolved path: {target_path} (relative: {relative_path_str})")
        return mcp.types.CallToolResult(results=[mcp.types.Content(type=mcp.types.ContentType.TEXT, data=f"File '{relative_path_str}' written successfully.")])
    except ValueError as e:
        logger.error(f"Tool '{tool_name}': Invalid path '{path_str}'. Error: {e}")
        return mcp.types.CallToolResult(error=mcp.types.ErrorData(code=mcp.types.INVALID_REQUEST, message=str(e)))
    except Exception as e:
        logger.error(f"Tool '{tool_name}': Error writing file '{path_str}'. Error: {e}", exc_info=True)
        return mcp.types.CallToolResult(error=mcp.types.ErrorData(code=mcp.types.INTERNAL_ERROR, message=f"Failed to write file: {e}"))

async def file_system_read_file_tool(params: Dict[str, Any]) -> mcp.types.CallToolResult:
    tool_name = "file_system_read_file"
    logger.info(f"Tool '{tool_name}' called with parameters: {params}")
    path_str = params.get("path")

    if not path_str or not isinstance(path_str, str):
        return mcp.types.CallToolResult(error=mcp.types.ErrorData(code=mcp.types.INVALID_PARAMETERS, message=f"Tool '{tool_name}': 'path' parameter is required and must be a string."))

    try:
        target_path = _resolve_and_verify_path(path_str)
        if not target_path.is_file():
            logger.warning(f"Tool '{tool_name}': File not found at resolved path {target_path} for reading.")
            return mcp.types.CallToolResult(error=mcp.types.ErrorData(code=mcp.types.RESOURCE_NOT_FOUND, message="File not found."))
        
        content_read = target_path.read_text(encoding="utf-8")
        logger.info(f"File read from resolved path: {target_path}")
        return mcp.types.CallToolResult(results=[mcp.types.Content(type=mcp.types.ContentType.TEXT, data=content_read)])
    except ValueError as e:
        logger.error(f"Tool '{tool_name}': Invalid path '{path_str}'. Error: {e}")
        return mcp.types.CallToolResult(error=mcp.types.ErrorData(code=mcp.types.INVALID_REQUEST, message=str(e)))
    except Exception as e:
        logger.error(f"Tool '{tool_name}': Error reading file '{path_str}'. Error: {e}", exc_info=True)
        return mcp.types.CallToolResult(error=mcp.types.ErrorData(code=mcp.types.INTERNAL_ERROR, message=f"Failed to read file: {e}"))

async def file_system_list_directory_tool(params: Dict[str, Any]) -> mcp.types.CallToolResult:
    tool_name = "file_system_list_directory"
    logger.info(f"Tool '{tool_name}' called with parameters: {params}")
    path_str = params.get("path", ".") 

    if not isinstance(path_str, str):
        return mcp.types.CallToolResult(error=mcp.types.ErrorData(code=mcp.types.INVALID_PARAMETERS, message=f"Tool '{tool_name}': 'path' parameter must be a string."))

    try:
        target_path = _resolve_and_verify_path(path_str)
        if not target_path.is_dir():
            logger.warning(f"Tool '{tool_name}': Directory not found at resolved path {target_path} for listing.")
            return mcp.types.CallToolResult(error=mcp.types.ErrorData(code=mcp.types.RESOURCE_NOT_FOUND, message="Directory not found."))

        items = []
        for item in target_path.iterdir():
            item_type = "dir" if item.is_dir() else "file"
            items.append(f"{item.name} ({item_type})")
        
        relative_path_str = str(target_path.relative_to(MCP_BASE_WORKING_DIR.resolve()))
        logger.info(f"Directory '{relative_path_str}' listed with {len(items)} items.")
        
        if not items:
            return mcp.types.CallToolResult(results=[mcp.types.Content(type=mcp.types.ContentType.TEXT, data=f"Directory '{relative_path_str}' is empty.")])
        
        return mcp.types.CallToolResult(results=[mcp.types.Content(type=mcp.types.ContentType.JSON, data=json.dumps(items))])
    except ValueError as e:
        logger.error(f"Tool '{tool_name}': Invalid path '{path_str}'. Error: {e}")
        return mcp.types.CallToolResult(error=mcp.types.ErrorData(code=mcp.types.INVALID_REQUEST, message=str(e)))
    except Exception as e:
        logger.error(f"Tool '{tool_name}': Error listing directory '{path_str}'. Error: {e}", exc_info=True)
        return mcp.types.CallToolResult(error=mcp.types.ErrorData(code=mcp.types.INTERNAL_ERROR, message=f"Failed to list directory: {e}"))

async def execute_shell_command_tool(params: Dict[str, Any]) -> mcp.types.CallToolResult:
    tool_name = "execute_shell_command"
    logger.info(f"Tool '{tool_name}' called with parameters: {params}")
    command_str = params.get("command")
    working_dir_str = params.get("working_directory")

    if not command_str or not isinstance(command_str, str):
        return mcp.types.CallToolResult(error=mcp.types.ErrorData(code=mcp.types.INVALID_PARAMETERS, message=f"Tool '{tool_name}': 'command' parameter is required and must be a string."))

    if not ALLOW_ARBITRARY_SHELL_COMMANDS:
        logger.warning(f"Tool '{tool_name}': Attempt to execute shell command when disallowed by server configuration.")
        return mcp.types.CallToolResult(error=mcp.types.ErrorData(code=mcp.types.FORBIDDEN, message="Shell command execution is disabled by server configuration."))

    try:
        cwd_for_command = MCP_BASE_WORKING_DIR.resolve()
        if working_dir_str:
            if not isinstance(working_dir_str, str):
                 return mcp.types.CallToolResult(error=mcp.types.ErrorData(code=mcp.types.INVALID_PARAMETERS, message=f"Tool '{tool_name}': 'working_directory' must be a string if provided."))
            resolved_custom_cwd = _resolve_and_verify_path(working_dir_str)
            if not resolved_custom_cwd.is_dir():
                return mcp.types.CallToolResult(error=mcp.types.ErrorData(code=mcp.types.INVALID_REQUEST, message=f"Specified working directory '{working_dir_str}' does not exist or is not a directory within the allowed base path."))
            cwd_for_command = resolved_custom_cwd
        
        logger.info(f"Executing command: '{command_str}' in working directory: '{cwd_for_command}'")
        command_parts = shlex.split(command_str)
        process = await asyncio.create_subprocess_exec(
            *command_parts,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd_for_command)
        )
        stdout_bytes, stderr_bytes = await process.communicate()
        stdout_str = stdout_bytes.decode('utf-8', errors='replace').strip()
        stderr_str = stderr_bytes.decode('utf-8', errors='replace').strip()
        return_code = process.returncode
        logger.info(f"Command '{command_str}' finished with return code: {return_code}")
        if stdout_str: logger.debug(f"Stdout: {stdout_str}")
        if stderr_str: logger.debug(f"Stderr: {stderr_str}")
            
        results_data = {"stdout": stdout_str, "stderr": stderr_str, "return_code": return_code}
        return mcp.types.CallToolResult(results=[mcp.types.Content(type=mcp.types.ContentType.JSON, data=json.dumps(results_data))])
    except ValueError as e: # From _resolve_and_verify_path for working_directory
        logger.error(f"Tool '{tool_name}': Invalid working directory '{working_dir_str}'. Error: {e}")
        return mcp.types.CallToolResult(error=mcp.types.ErrorData(code=mcp.types.INVALID_REQUEST, message=str(e)))
    except FileNotFoundError:
        cmd_executable = shlex.split(command_str)[0] if command_str else "Unknown"
        logger.error(f"Tool '{tool_name}': Command executable '{cmd_executable}' not found in container's PATH.")
        return mcp.types.CallToolResult(error=mcp.types.ErrorData(code=mcp.types.INVALID_REQUEST, message=f"Command executable '{cmd_executable}' not found."))
    except Exception as e:
        logger.error(f"Tool '{tool_name}': Error executing command '{command_str}'. Error: {e}", exc_info=True)
        return mcp.types.CallToolResult(error=mcp.types.ErrorData(code=mcp.types.INTERNAL_ERROR, message=f"Failed to execute command: {e}"))

MCP_TOOLS_REGISTRY = [
    Tool(
        name="file_system_create_directory",
        description="Creates a new directory. Path is relative to the server's configured base working directory.",
        inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "The path for the new directory (e.g., 'my_folder/sub_folder')."}}, "required": ["path"]},
        handler=file_system_create_directory_tool,
    ),
    Tool(
        name="file_system_write_file",
        description="Writes or overwrites a file with given content. Path is relative to the server's configured base working directory.",
        inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "The path of the file to write (e.g., 'my_folder/my_file.txt')."}, "content": {"type": "string", "description": "The content to write into the file."}}, "required": ["path", "content"]},
        handler=file_system_write_file_tool,
    ),
    Tool(
        name="file_system_read_file",
        description="Reads the content of a file. Path is relative to the server's configured base working directory.",
        inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "The path of the file to read (e.g., 'my_folder/my_file.txt')."}}, "required": ["path"]},
        handler=file_system_read_file_tool,
    ),
    Tool(
        name="file_system_list_directory",
        description="Lists files and subdirectories within a specified path. Path is relative to the server's configured base working directory. Defaults to listing the base directory if no path is provided.",
        inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "The path of the directory to list (e.g., 'my_folder' or '.'). Defaults to the base directory."}}},
        handler=file_system_list_directory_tool,
    ),
    Tool(
        name="execute_shell_command",
        description="Executes a given shell command within the container's operating system environment. WARNING: This tool is powerful. Use with extreme caution.",
        inputSchema={"type": "object", "properties": {"command": {"type": "string", "description": "The shell command to execute (e.g., 'ls -la')."}, "working_directory": {"type": "string", "description": "Optional. Path relative to the server's base directory to use as the current working directory for the command. Defaults to the server's base directory."}}, "required": ["command"]},
        handler=execute_shell_command_tool,
    ),
]
MCP_RESOURCES_REGISTRY: List[Resource] = []