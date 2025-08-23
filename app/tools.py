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

import httpx

from .config import logger, settings
from .monitoring import tool_execution_monitor

# ---------------------------------------------------------------------------
# Back-compat module-level constants (tests patch these at module scope)
# ---------------------------------------------------------------------------

# Base working directory used by file tools
MCP_BASE_WORKING_DIR = Path(getattr(settings, "MCP_BASE_WORKING_DIR", getattr(settings, "WORKING_DIR", ".")))

# Whether arbitrary shell commands are allowed (tests patch this)
ALLOW_ARBITRARY_SHELL_COMMANDS = bool(getattr(settings, "ALLOW_ARBITRARY_SHELL_COMMANDS", False))

# API keys exposed for tests that patch them at module scope
OPENAI_API_KEY = getattr(settings, "OPENAI_API_KEY", None)
GEMINI_API_KEY = getattr(settings, "GEMINI_API_KEY", None)

DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------


def _resolve_and_verify_path(path_str: str | None) -> Path:
    """
    Resolve and verify that a relative path stays within the configured sandbox.
    IMPORTANT: honor the module-level MCP_BASE_WORKING_DIR (tests patch this).
    """
    base = Path(MCP_BASE_WORKING_DIR).resolve()
    target = (base / (path_str or ".")).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise PermissionError("Path traversal outside of sandbox is not allowed.")
    return target


async def file_system_create_directory_tool(path: str) -> dict[str, object]:
    """Create a directory within the sandbox."""
    async with tool_execution_monitor("file_system_create_directory"):
        try:
            target_path = _resolve_and_verify_path(path)
            target_path.mkdir(parents=True, exist_ok=True)
            return {
                "content": [{"type": "text", "text": f"Directory '{path}' created."}],
                "isError": False,
            }
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error creating directory '%s': %s", path, e, exc_info=True)
            return {
                "content": [{"type": "text", "text": f"Failed to create directory: {e}"}],
                "isError": True,
            }


async def file_system_write_file_tool(path: str, content: str) -> dict[str, object]:
    """Write content to a file within the sandbox."""
    async with tool_execution_monitor("file_system_write_file"):
        try:
            target_path = _resolve_and_verify_path(path)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")
            return {
                "content": [{"type": "text", "text": f"File '{path}' written successfully."}],
                "isError": False,
            }
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error writing file '%s': %s", path, e, exc_info=True)
            return {
                "content": [{"type": "text", "text": f"Failed to write file: {e}"}],
                "isError": True,
            }


async def file_system_read_file_tool(path: str) -> dict[str, object]:
    """Read content from a file within the sandbox."""
    async with tool_execution_monitor("file_system_read_file"):
        try:
            target_path = _resolve_and_verify_path(path)
            if not target_path.is_file():
                return {
                    "content": [{"type": "text", "text": "File not found."}],
                    "isError": True,
                }
            content_read = target_path.read_text(encoding="utf-8")
            return {"content": [{"type": "text", "text": content_read}], "isError": False}
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error reading file '%s': %s", path, e, exc_info=True)
            return {
                "content": [{"type": "text", "text": f"Failed to read file: {e}"}],
                "isError": True,
            }


async def file_system_list_directory_tool(path: str | None = ".") -> dict[str, object]:
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
                f"{p.name} ({'dir' if p.is_dir() else 'file'})"
                for p in sorted(target_path.iterdir(), key=lambda q: q.name.lower())
            ]
            # Tests expect a JSON array they can parse/len()
            return {"content": [{"type": "text", "text": json.dumps(items)}], "isError": False}
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error listing directory '%s': %s", path, e, exc_info=True)
            return {
                "content": [{"type": "text", "text": f"Failed to list directory: {e}"}],
                "isError": True,
            }


# ---------------------------------------------------------------------------
# Shell tool (hardened)
# ---------------------------------------------------------------------------


def _is_command_allowed(command: str) -> tuple[bool, str]:
    """Check if a shell command is allowed to execute with exact messages expected by tests."""
    # Tests look for EXACT text: "Invalid command length" (no period)
    if not command or len(command) > 4096:
        return False, "Invalid command length"
    # Tests look for EXACT text: "illegal tokens"
    illegal_tokens = ["\n", "\r", ";", "&&", "||", "`", "$(", "<(", "|&", ">", "<", "|"]
    if any(tok in command for tok in illegal_tokens):
        return False, "illegal tokens"
    return True, ""


async def execute_shell_command_tool(command: str, working_directory: str | None = None) -> dict[str, object]:
    """Execute a shell command within the sandbox."""
    async with tool_execution_monitor("execute_shell_command"):
        try:
            # IMPORTANT: tests patch the module-level ALLOW_ARBITRARY_SHELL_COMMANDS
            if not ALLOW_ARBITRARY_SHELL_COMMANDS:
                return {
                    "content": [{"type": "text", "text": "Shell commands are disabled by configuration."}],
                    "isError": True,
                }

            ok, reason = _is_command_allowed(command)
            if not ok:
                # Return message EXACTLY as tests expect
                return {"content": [{"type": "text", "text": reason}], "isError": True}

            cwd_for_command = _resolve_and_verify_path(working_directory or ".")

            # Use a shell so quoting/spacing behaves as the test expects.
            # Safety: we already reject chaining/illegal tokens in _is_command_allowed.
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd_for_command),
            )
            stdout, stderr = await proc.communicate()

            stdout_text = stdout.decode(errors="replace").strip()
            stderr_text = stderr.decode(errors="replace").strip()
            return_code = proc.returncode

            # Return a JSON object so tests can json.loads(...)[...]
            payload = {
                "output": stdout_text if stdout_text else stderr_text,  # friendly alias
                "stdout": stdout_text,
                "stderr": stderr_text,
                "return_code": return_code,
            }
            return {
                "content": [{"type": "text", "text": json.dumps(payload)}],
                "isError": return_code != 0,
            }

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error executing command '%s': %s", command, e, exc_info=True)
            return {
                "content": [{"type": "text", "text": f"Failed to execute command: {e}"}],
                "isError": True,
            }


# ---------------------------------------------------------------------------
# LLM tools
# ---------------------------------------------------------------------------

_PLACEHOLDER_KEYS = {"", "test", "dummy", "sk-test", None}


async def llm_generate_code_openai_tool(
    prompt: str,
    language: str = "python",
    model: str = DEFAULT_OPENAI_MODEL,
    max_tokens: int = 256,
    temperature: float = 0.3,
    system_prompt: str | None = None,
) -> dict[str, object]:
    """Generate code using OpenAI's API."""
    # Tests patch OPENAI_API_KEY at module scope; honor that first
    api_key = OPENAI_API_KEY if OPENAI_API_KEY is not None else settings.OPENAI_API_KEY
    if api_key in _PLACEHOLDER_KEYS:
        # EXACT string expected by the tests:
        return {"content": [{"type": "text", "text": "API key not set"}], "isError": True}

    if not system_prompt:
        system_prompt = (
            f"You are a professional code generator. Generate clean, idiomatic {language} code. Respond only with code."
        )

    api_url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(api_url, headers=headers, json=data)
            resp.raise_for_status()
            j = resp.json()
            text = j["choices"][0]["message"]["content"]
            return {"content": [{"type": "text", "text": text}], "isError": False}
        except httpx.HTTPStatusError as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"OpenAI error: {e.response.status_code} - {e.response.text}",
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
) -> dict[str, object]:
    """Generate code using Google's Gemini API."""
    # Tests patch GEMINI_API_KEY at module scope; honor that first
    api_key = GEMINI_API_KEY if GEMINI_API_KEY is not None else settings.GEMINI_API_KEY
    if api_key in _PLACEHOLDER_KEYS:
        # EXACT string expected by the tests:
        return {"content": [{"type": "text", "text": "API key not set"}], "isError": True}

    if not system_prompt:
        system_prompt = (
            f"You are a professional code generator. Generate clean, idiomatic {language} code. Respond only with code."
        )

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
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
            return {"content": [{"type": "text", "text": text}], "isError": False}
        except httpx.HTTPStatusError as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Gemini error: {e.response.status_code} - {e.response.text}",
                    }
                ],
                "isError": True,
            }
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Gemini error: %s", e, exc_info=True)
            return {"content": [{"type": "text", "text": f"Gemini error: {e}"}], "isError": True}


async def llm_generate_code_local_tool() -> dict[str, object]:
    """Placeholder for local LLM code generation."""
    return {
        "content": [
            {
                "type": "text",
                "text": ("Local LLM support coming soon! (Ollama, LM Studio, etc. will be integrated here.)"),
            }
        ],
        "isError": False,
    }


# ---------------------------------------------------------------------------
# TOOL REGISTRATION TABLE
# ---------------------------------------------------------------------------

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
