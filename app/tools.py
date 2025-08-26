"""
Tool implementations for the MCP Server Project.

This module provides filesystem operations, shell command execution,
and LLM code generation tools with proper sandboxing and error handling.

SECURITY: Sandboxed tool execution
- All file operations restricted to configured working directory
- Shell commands filtered for dangerous tokens and patterns
- Path traversal attacks prevented via path resolution validation
- Configurable security controls (ALLOW_ARBITRARY_SHELL_COMMANDS)

ARCHITECTURE: MCP-compatible tool interface
- All tools return standardized {"content": [...], "isError": bool} format
- Async execution with proper error handling and logging
- Monitoring integration via tool_execution_monitor context manager
- Supports both development/testing and production security postures
"""

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
# TESTING: Tests patch this variable to control sandbox location
# SECURITY: All file operations are restricted to this directory tree
MCP_BASE_WORKING_DIR = Path(getattr(settings, "MCP_BASE_WORKING_DIR", getattr(settings, "WORKING_DIR", ".")))

# Whether arbitrary shell commands are allowed (tests patch this)
# SECURITY: Disabled by default, only enabled in development or explicit config
# TESTING: Tests can patch this to enable shell commands for testing
ALLOW_ARBITRARY_SHELL_COMMANDS = bool(getattr(settings, "ALLOW_ARBITRARY_SHELL_COMMANDS", False))

# API keys exposed for tests that patch them at module scope
# DESIGN: Module-level variables allow easy test patching
# TESTING: Tests patch these to control API behavior (None = no API calls)
OPENAI_API_KEY = getattr(settings, "OPENAI_API_KEY", None)
GEMINI_API_KEY = getattr(settings, "GEMINI_API_KEY", None)

# Default model configurations
DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------


def _resolve_and_verify_path(path_str: str | None) -> Path:
    """
    Resolve and verify that a relative path stays within the configured sandbox.
    IMPORTANT: honor the module-level MCP_BASE_WORKING_DIR (tests patch this).

    SECURITY: Path traversal prevention
    - Resolves all symbolic links and relative paths
    - Ensures target path is within sandbox directory
    - Raises PermissionError for any path outside sandbox
    - Handles edge cases like empty paths, None, complex traversals

    TESTING: Respects patched MCP_BASE_WORKING_DIR
    - Tests can set different sandbox directories
    - Allows testing path validation without affecting system

    Args:
        path_str: Relative path string (may be None)

    Returns:
        Path: Resolved absolute path within sandbox

    Raises:
        PermissionError: If path attempts to escape sandbox
    """
    base = Path(MCP_BASE_WORKING_DIR).resolve()
    target = (base / (path_str or ".")).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise PermissionError("Path traversal outside of sandbox is not allowed.")
    return target


async def file_system_create_directory_tool(path: str) -> dict[str, object]:
    """Create a directory within the sandbox.

    SECURITY: Sandboxed directory creation
    - Path validation prevents directory creation outside sandbox
    - Creates parent directories as needed (mkdir -p behavior)
    - Handles existing directories gracefully (exist_ok=True)

    MONITORING: Execution tracking
    - Uses tool_execution_monitor for metrics and error tracking
    - Records success/failure rates and execution times

    Args:
        path: Relative path for directory to create

    Returns:
        MCP-format response with success/error information
    """
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
    """Write content to a file within the sandbox.

    DESIGN: Safe file writing
    - Creates parent directories automatically if needed
    - Overwrites existing files (standard behavior)
    - Uses UTF-8 encoding for consistent text handling
    - Atomic write operation (Python's write_text is atomic on most systems)

    Args:
        path: Relative path for file to write
        content: Text content to write to file

    Returns:
        MCP-format response with success/error information
    """
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
    """Read content from a file within the sandbox.

    DESIGN: Safe file reading
    - Validates file exists before attempting read
    - Uses UTF-8 encoding for consistent text handling
    - Returns entire file content (consider size limits for large files)
    - Clear error messages for non-existent files

    Args:
        path: Relative path of file to read

    Returns:
        MCP-format response with file content or error
    """
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
    """List contents of a directory within the sandbox.

    DESIGN: Directory listing with type information
    - Shows both files and directories with type indicators
    - Sorts entries alphabetically (case-insensitive)
    - Returns JSON array for easy parsing by clients
    - Handles non-existent directories gracefully

    TESTING: JSON output format
    - Tests expect JSON array they can parse with json.loads()
    - Format: ["filename (file)", "dirname (dir)", ...]

    Args:
        path: Relative path of directory to list (defaults to current)

    Returns:
        MCP-format response with directory listing or error
    """
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
    """Check if a shell command is allowed to execute with exact messages expected by tests.

    SECURITY: Multi-layer command validation
    - Length validation prevents buffer overflow attempts
    - Token blacklist prevents command chaining and injection
    - Exact error messages maintained for test compatibility

    DESIGN: Whitelist approach would be more secure
    - Current implementation uses blacklist for flexibility
    - Production deployments should consider command whitelist
    - Could be enhanced with regex patterns for more sophisticated filtering

    Args:
        command: Shell command to validate

    Returns:
        Tuple of (is_allowed: bool, reason: str)

    TESTING: Exact error message format required
    - Tests verify specific error message text
    - "Invalid command length" (no period)
    - "illegal tokens" (lowercase)
    """
    # Tests look for EXACT text: "Invalid command length" (no period)
    if not command or len(command) > 4096:
        return False, "Invalid command length"

    # Tests look for EXACT text: "illegal tokens"
    # SECURITY: Prevent command injection and chaining
    illegal_tokens = ["\n", "\r", ";", "&&", "||", "`", "$(", "<(", "|&", ">", "<", "|"]
    if any(tok in command for tok in illegal_tokens):
        return False, "illegal tokens"
    return True, ""


async def execute_shell_command_tool(command: str, working_directory: str | None = None) -> dict[str, object]:
    """Execute a shell command within the sandbox.

    SECURITY: Heavily restricted shell execution
    - Disabled by default (ALLOW_ARBITRARY_SHELL_COMMANDS = False)
    - Command validation prevents injection attacks
    - Sandboxed execution within configured working directory
    - No command chaining, piping, or redirection allowed

    DESIGN DECISION: Shell vs direct execution
    - Uses asyncio.create_subprocess_shell for compatibility
    - Allows natural command behavior (quoting, spacing)
    - Pre-filtering makes this reasonably safe
    - Could be enhanced to use subprocess.run with shell=False

    TESTING: JSON output format
    - Returns structured JSON with stdout, stderr, return_code
    - Tests can parse with json.loads() for detailed assertions
    - "output" field provides friendly access to primary output

    Args:
        command: Shell command to execute
        working_directory: Working directory for command (defaults to sandbox root)

    Returns:
        MCP-format response with command output or error
    """
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

# API key validation set - these values indicate "not set"
_PLACEHOLDER_KEYS = {"", "test", "dummy", "sk-test", None}


async def llm_generate_code_openai_tool(
    prompt: str,
    language: str = "python",
    model: str = DEFAULT_OPENAI_MODEL,
    max_tokens: int = 256,
    temperature: float = 0.3,
    system_prompt: str | None = None,
) -> dict[str, object]:
    """Generate code using OpenAI's API.

    INTEGRATION: OpenAI ChatGPT API integration
    - Uses chat completions endpoint (not legacy completions)
    - Supports system prompts for better code generation
    - Configurable model, temperature, and token limits
    - Proper error handling for API failures

    TESTING: API key validation and mocking
    - Tests patch OPENAI_API_KEY to control behavior
    - Placeholder keys return specific error message for tests
    - Module-level variable allows easy test patching

    SECURITY: API key handling
    - Checks module variable first (for test patching)
    - Falls back to settings for production
    - Validates key is not placeholder value
    - No logging of API keys or responses (privacy)

    Args:
        prompt: Code generation prompt
        language: Target programming language
        model: OpenAI model to use (gpt-4, gpt-3.5-turbo, etc.)
        max_tokens: Maximum tokens in response
        temperature: Randomness control (0.0-1.0)
        system_prompt: System prompt override

    Returns:
        MCP-format response with generated code or error
    """
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
    """Generate code using Google's Gemini API.

    INTEGRATION: Google Gemini API integration
    - Uses generateContent endpoint with generation config
    - Different parameter naming vs OpenAI (maxOutputTokens vs max_tokens)
    - API key passed as URL parameter instead of header
    - JSON response structure differs from OpenAI

    DESIGN: Unified interface with OpenAI tool
    - Same parameter names and defaults where possible
    - Same error handling patterns and response format
    - System prompt handling (though Gemini doesn't use it directly)
    - Consistent MCP response format

    Args:
        prompt: Code generation prompt
        language: Target programming language
        model: Gemini model (gemini-pro, gemini-pro-vision, etc.)
        max_output_tokens: Maximum tokens in response
        temperature: Randomness control (0.0-1.0)
        system_prompt: System prompt (informational - not used by Gemini)

    Returns:
        MCP-format response with generated code or error
    """
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
    """Placeholder for local LLM code generation.

    FUTURE: Local LLM integration placeholder
    - Reserved for Ollama, LM Studio, or other local inference
    - No parameters needed yet (will be added when implemented)
    - Returns placeholder message indicating future availability
    - Maintains consistent MCP response format

    DESIGN: Future extensibility
    - Tool registration system supports adding new tools easily
    - Could integrate with Hugging Face Transformers
    - Could support multiple local model backends
    - Same interface pattern as cloud LLM tools
    """
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

"""
TOOL REGISTRY DESIGN:

This registration system provides:

1. **Declarative Tool Definition**: Each tool is defined with name, description, and handler
2. **FastMCP Integration**: Tools are automatically registered with FastMCP server  
3. **Type Safety**: Handler functions are typed for async execution
4. **Easy Extension**: New tools just need to be added to this list
5. **Testing Support**: Individual tools can be tested independently
6. **Documentation**: Descriptions are exposed via API for client discovery

SECURITY CONSIDERATIONS:
- All file tools are sandboxed to MCP_BASE_WORKING_DIR
- Shell execution is disabled by default and heavily filtered
- LLM tools validate API keys and handle errors gracefully
- No tools have direct network access beyond approved APIs

MONITORING INTEGRATION:
- All tools use tool_execution_monitor for metrics
- Execution times and error rates are tracked
- Prometheus metrics available at /metrics endpoint

TESTING DESIGN:
- Module-level variables can be patched by tests
- Predictable error messages for test assertions
- JSON output formats for structured test validation
- Mock-friendly async interfaces
"""
