"""
Tool implementations for the MCP Server Project.

This module provides filesystem operations, shell command execution,
and LLM code generation tools with proper sandboxing and error handling.
"""

# app/tools.py

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import httpx

from .config import (
    ALLOW_ARBITRARY_SHELL_COMMANDS,
    GEMINI_API_KEY,
    MCP_BASE_WORKING_DIR,
    OPENAI_API_KEY,
    logger,
)
from .monitoring import tool_execution_monitor

DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# ---------- Filesystem helpers ----------


def _resolve_and_verify_path(path_str: str | None) -> Path:
    """Resolve and verify path is within sandbox directory."""
    base = MCP_BASE_WORKING_DIR.resolve()
    target = (base / (path_str or ".")).resolve()
    if not str(target).startswith(str(base)):
        raise PermissionError("Path traversal outside of sandbox is not allowed.")
    return target


async def file_system_create_directory_tool(path: str) -> dict[str, Any]:
    """Create a directory within the sandbox."""
    async with tool_execution_monitor("file_system_create_directory"):
        try:
            target_path = _resolve_and_verify_path(path)
            target_path.mkdir(parents=True, exist_ok=True)
            return {"content": [{"type": "text", "text": f"Directory '{path}' created."}]}
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error creating directory '%s': %s", path, e, exc_info=True)
            return {
                "content": [{"type": "text", "text": f"Failed to create directory: {e}"}],
                "isError": True,
            }


async def file_system_write_file_tool(path: str, content: str) -> dict[str, Any]:
    """Write content to a file within the sandbox."""
    async with tool_execution_monitor("file_system_write_file"):
        try:
            target_path = _resolve_and_verify_path(path)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")
            return {"content": [{"type": "text", "text": f"File '{path}' written successfully."}]}
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error writing file '%s': %s", path, e, exc_info=True)
            return {
                "content": [{"type": "text", "text": f"Failed to write file: {e}"}],
                "isError": True,
            }


async def file_system_read_file_tool(path: str) -> dict[str, Any]:
    """Read content from a file within the sandbox."""
    async with tool_execution_monitor("file_system_read_file"):
        try:
            target_path = _resolve_and_verify_path(path)
            if not target_path.is_file():
                return {"content": [{"type": "text", "text": "File not found."}], "isError": True}
            content_read = target_path.read_text(encoding="utf-8")
            return {"content": [{"type": "text", "text": content_read}]}
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error reading file '%s': %s", path, e, exc_info=True)
            return {
                "content": [{"type": "text", "text": f"Failed to read file: {e}"}],
                "isError": True,
            }


async def file_system_list_directory_tool(path: str | None = ".") -> dict[str, Any]:
    """List contents of a directory within the sandbox."""
    async with tool_execution_monitor("file_system_list_directory"):
        try:
            target_path = _resolve_and_verify_path(path or ".")
            if not target_path.is_dir():
                return {
                    "content": [{"type": "text", "text": "Directory not found."}],
                    "isError": True,
                }
            items = [
                f"{item.name} ({'dir' if item.is_dir() else 'file'})"
                for item in target_path.iterdir()
            ]
            if not items:
                return {"content": [{"type": "text", "text": f"Directory '{path}' is empty."}]}
            return {"content": [{"type": "text", "text": json.dumps(items)}]}
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error listing directory '%s': %s", path, e, exc_info=True)
            return {
                "content": [{"type": "text", "text": f"Failed to list directory: {e}"}],
                "isError": True,
            }


# ---------- Shell tool (hardened) ----------


def _is_command_allowed(command: str) -> tuple[bool, str]:
    """Check if a shell command is allowed to execute."""
    if not command or len(command) > 4096:
        return False, "Invalid command length."
    illegal_tokens = ["\n", "\r", ";", "&&", "||", "`", "$(", "<(", "|&"]
    if any(tok in command for tok in illegal_tokens):
        return False, "Command chaining or illegal tokens are not allowed."
    return True, ""


async def execute_shell_command_tool(
    command: str, working_directory: str | None = None
) -> dict[str, Any]:
    """Execute a shell command within the sandbox."""
    async with tool_execution_monitor("execute_shell_command"):
        try:
            if not ALLOW_ARBITRARY_SHELL_COMMANDS:
                return {
                    "content": [
                        {"type": "text", "text": "Shell commands are disabled by configuration."}
                    ],
                    "isError": True,
                }
            ok, reason = _is_command_allowed(command)
            if not ok:
                return {
                    "content": [{"type": "text", "text": f"Rejected: {reason}"}],
                    "isError": True,
                }

            cwd_for_command = _resolve_and_verify_path(working_directory or ".")
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd_for_command),
            )
            stdout, stderr = await proc.communicate()
            results_data = {
                "stdout": stdout.decode(errors="replace"),
                "stderr": stderr.decode(errors="replace"),
                "return_code": proc.returncode,
            }
            return {"content": [{"type": "text", "text": json.dumps(results_data, indent=2)}]}
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error executing command '%s': %s", command, e, exc_info=True)
            return {
                "content": [{"type": "text", "text": f"Failed to execute command: {e}"}],
                "isError": True,
            }


# ---------- LLM tools ----------


async def llm_generate_code_openai_tool(
    prompt: str,
    language: str = "python",
    model: str = DEFAULT_OPENAI_MODEL,
    max_tokens: int = 256,
    temperature: float = 0.3,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    """Generate code using OpenAI's API."""
    if not OPENAI_API_KEY:
        return {"content": [{"type": "text", "text": "OpenAI API key not set."}], "isError": True}
    if not system_prompt:
        system_prompt = (
            f"You are a professional code generator. Generate clean, "
            f"idiomatic {language} code. Respond only with code."
        )

    api_url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(api_url, headers=headers, json=data)
            resp.raise_for_status()
            j = resp.json()
            text = j["choices"][0]["message"]["content"]
            return {"content": [{"type": "text", "text": text}]}
        except httpx.HTTPStatusError as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (f"OpenAI error: {e.response.status_code} - {e.response.text}"),
                    }
                ],
                "isError": True,
            }
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("OpenAI error: %s", e, exc_info=True)
            return {"content": [{"type": "text", "text": f"OpenAI error: {e}"}], "isError": True}


async def llm_generate_code_gemini_tool(
    prompt: str,
    language: str = "python",
    model: str = DEFAULT_GEMINI_MODEL,
    max_output_tokens: int = 256,
    temperature: float = 0.3,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    """Generate code using Google's Gemini API."""
    if not GEMINI_API_KEY:
        return {"content": [{"type": "text", "text": "Gemini API key not set."}], "isError": True}
    if not system_prompt:
        system_prompt = (
            f"You are a professional code generator. Generate clean, "
            f"idiomatic {language} code. Respond only with code."
        )

    api_url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_output_tokens},
    }
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(api_url, json=payload)
            resp.raise_for_status()
            j = resp.json()
            text = j["candidates"][0]["content"]["parts"][0]["text"]
            return {"content": [{"type": "text", "text": text}]}
        except httpx.HTTPStatusError as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (f"Gemini error: {e.response.status_code} - {e.response.text}"),
                    }
                ],
                "isError": True,
            }
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Gemini error: %s", e, exc_info=True)
            return {"content": [{"type": "text", "text": f"Gemini error: {e}"}], "isError": True}


async def llm_generate_code_local_tool() -> dict[str, Any]:
    """Placeholder for local LLM code generation."""
    return {
        "content": [
            {
                "type": "text",
                "text": (
                    "Local LLM support coming soon! "
                    "(Ollama, LM Studio, etc. will be integrated here.)"
                ),
            }
        ],
        "isError": False,
    }


# --- TOOL REGISTRATION TABLE ---
ALL_TOOLS = [
    {
        "name": "file_system_create_directory",
        "description": "Creates a directory.",
        "handler": file_system_create_directory_tool,
    },
    {
        "name": "file_system_write_file",
        "description": "Writes text to a file.",
        "handler": file_system_write_file_tool,
    },
    {
        "name": "file_system_read_file",
        "description": "Reads a text file.",
        "handler": file_system_read_file_tool,
    },
    {
        "name": "file_system_list_directory",
        "description": "Lists the contents of a directory.",
        "handler": file_system_list_directory_tool,
    },
    {
        "name": "execute_shell_command",
        "description": "Executes a shell command in the sandbox.",
        "handler": execute_shell_command_tool,
    },
    {
        "name": "llm_generate_code_openai",
        "description": "Generates code using OpenAI.",
        "handler": llm_generate_code_openai_tool,
    },
    {
        "name": "llm_generate_code_gemini",
        "description": "Generates code using Gemini.",
        "handler": llm_generate_code_gemini_tool,
    },
    {
        "name": "llm_generate_code_local",
        "description": "Generates code using a local model.",
        "handler": llm_generate_code_local_tool,
    },
]
