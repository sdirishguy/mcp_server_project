# app/tools.py

import asyncio
import json
import shlex
import os
from pathlib import Path
from typing import Dict, Any

from .config import MCP_BASE_WORKING_DIR, ALLOW_ARBITRARY_SHELL_COMMANDS, logger

# --- Utility functions for path safety ---
def _is_path_within_base(path_to_check: Path, base_path: Path) -> bool:
    try:
        return base_path in path_to_check.resolve().parents or base_path == path_to_check.resolve()
    except Exception:
        return False

def _resolve_and_verify_path(user_path: str) -> Path:
    base = MCP_BASE_WORKING_DIR
    norm_path = user_path.lstrip('/')
    resolved = (base / norm_path).resolve()
    if not _is_path_within_base(resolved, base):
        logger.warning(f"Access denied: '{user_path}' → '{resolved}' (outside base '{base}')")
        raise ValueError(f"Path '{user_path}' is outside the allowed base directory.")
    return resolved

# --- Tool: Create Directory ---
async def file_system_create_directory_tool(params: Dict[str, Any]) -> dict:
    path = params.get("path")
    if not path or not isinstance(path, str):
        return _error("Missing or invalid 'path' parameter.")
    try:
        target = _resolve_and_verify_path(path)
        target.mkdir(parents=True, exist_ok=True)
        return _text_result(f"Directory '{target.relative_to(MCP_BASE_WORKING_DIR)}' created successfully.")
    except Exception as e:
        logger.error(f"Error creating directory '{path}': {e}")
        return _error(str(e))

# --- Tool: Write File ---
async def file_system_write_file_tool(params: Dict[str, Any]) -> dict:
    path, content = params.get("path"), params.get("content")
    if not path or not isinstance(path, str):
        return _error("Missing or invalid 'path' parameter.")
    if not isinstance(content, str):
        return _error("Missing or invalid 'content' parameter.")
    try:
        target = _resolve_and_verify_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return _text_result(f"File '{target.relative_to(MCP_BASE_WORKING_DIR)}' written successfully.")
    except Exception as e:
        logger.error(f"Error writing file '{path}': {e}")
        return _error(str(e))

# --- Tool: Read File ---
async def file_system_read_file_tool(params: Dict[str, Any]) -> dict:
    path = params.get("path")
    if not path or not isinstance(path, str):
        return _error("Missing or invalid 'path' parameter.")
    try:
        target = _resolve_and_verify_path(path)
        if not target.is_file():
            return _error("File not found.")
        content = target.read_text(encoding="utf-8")
        return _text_result(content)
    except Exception as e:
        logger.error(f"Error reading file '{path}': {e}")
        return _error(str(e))

# --- Tool: List Directory ---
async def file_system_list_directory_tool(params: Dict[str, Any]) -> dict:
    path = params.get("path", ".")
    if not isinstance(path, str):
        return _error("Missing or invalid 'path' parameter.")
    try:
        target = _resolve_and_verify_path(path)
        if not target.is_dir():
            return _error("Directory not found.")
        items = [f"{item.name} ({'dir' if item.is_dir() else 'file'})" for item in target.iterdir()]
        return _text_result(json.dumps(items))
    except Exception as e:
        logger.error(f"Error listing directory '{path}': {e}")
        return _error(str(e))

# --- Tool: Execute Shell Command ---
async def execute_shell_command_tool(params: Dict[str, Any]) -> dict:
    command = params.get("command")
    working_dir = params.get("working_directory", ".")
    if not ALLOW_ARBITRARY_SHELL_COMMANDS:
        return _error("Shell execution is disabled by config.")
    if not command or not isinstance(command, str):
        return _error("Missing or invalid 'command' parameter.")
    try:
        cwd = _resolve_and_verify_path(working_dir)
        proc = await asyncio.create_subprocess_exec(
            *shlex.split(command),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd)
        )
        stdout, stderr = await proc.communicate()
        result = {
            "stdout": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
            "return_code": proc.returncode
        }
        return _text_result(json.dumps(result))
    except Exception as e:
        logger.error(f"Error executing command '{command}': {e}")
        return _error(str(e))

# --- Result helpers for MCP protocol ---
def _text_result(text: str) -> dict:
    return {
        "_meta": None,
        "content": [{
            "type": "text",
            "text": text,
            "annotations": None
        }],
        "isError": False
    }

def _error(message: str) -> dict:
    return {
        "_meta": None,
        "content": [{
            "type": "text",
            "text": message,
            "annotations": None
        }],
        "isError": True
    }
