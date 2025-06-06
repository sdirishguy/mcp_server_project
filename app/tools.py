import os
import json
import asyncio
import httpx
import logging
from pathlib import Path
from typing import Dict, Any

from .config import (
    MCP_BASE_WORKING_DIR,
    ALLOW_ARBITRARY_SHELL_COMMANDS,
    OPENAI_API_KEY,
    GEMINI_API_KEY,
    logger
)

# --- File system helpers ---

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
        logger.warning(f"Path traversal or out-of-base attempt: '{user_path_str}' -> '{resolved_path}'")
        raise ValueError(f"Path is outside the allowed base directory: {user_path_str}")
    return resolved_path

# --- Tool Handlers ---

async def file_system_create_directory_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    path_str = params.get("path")
    if not path_str or not isinstance(path_str, str):
        return {"content": [{"type": "text", "text": "Missing or invalid 'path' parameter."}], "isError": True}
    try:
        target_path = _resolve_and_verify_path(path_str)
        target_path.mkdir(parents=True, exist_ok=True)
        return {"content": [{"type": "text", "text": f"Directory '{path_str}' created successfully."}]}
    except Exception as e:
        logger.error(f"Error creating directory '{path_str}': {e}", exc_info=True)
        return {"content": [{"type": "text", "text": f"Failed to create directory: {str(e)}"}], "isError": True}

async def file_system_write_file_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    path_str = params.get("path")
    content = params.get("content")
    if not path_str or not isinstance(path_str, str) or content is None or not isinstance(content, str):
        return {"content": [{"type": "text", "text": "Missing or invalid 'path' or 'content' parameter."}], "isError": True}
    try:
        target_path = _resolve_and_verify_path(path_str)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
        return {"content": [{"type": "text", "text": f"File '{path_str}' written successfully."}]}
    except Exception as e:
        logger.error(f"Error writing file '{path_str}': {e}", exc_info=True)
        return {"content": [{"type": "text", "text": f"Failed to write file: {str(e)}"}], "isError": True}

async def file_system_read_file_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    path_str = params.get("path")
    if not path_str or not isinstance(path_str, str):
        return {"content": [{"type": "text", "text": "Missing or invalid 'path' parameter."}], "isError": True}
    try:
        target_path = _resolve_and_verify_path(path_str)
        if not target_path.is_file():
            return {"content": [{"type": "text", "text": "File not found."}], "isError": True}
        content_read = target_path.read_text(encoding="utf-8")
        return {"content": [{"type": "text", "text": content_read}]}
    except Exception as e:
        logger.error(f"Error reading file '{path_str}': {e}", exc_info=True)
        return {"content": [{"type": "text", "text": f"Failed to read file: {str(e)}"}], "isError": True}

async def file_system_list_directory_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    path_str = params.get("path", ".")
    if not isinstance(path_str, str):
        return {"content": [{"type": "text", "text": "Missing or invalid 'path' parameter."}], "isError": True}
    try:
        target_path = _resolve_and_verify_path(path_str)
        if not target_path.is_dir():
            return {"content": [{"type": "text", "text": "Directory not found."}], "isError": True}
        items = [f"{item.name} ({'dir' if item.is_dir() else 'file'})" for item in target_path.iterdir()]
        if not items:
            return {"content": [{"type": "text", "text": f"Directory '{path_str}' is empty."}]}
        return {"content": [{"type": "text", "text": json.dumps(items)}]}
    except Exception as e:
        logger.error(f"Error listing directory '{path_str}': {e}", exc_info=True)
        return {"content": [{"type": "text", "text": f"Failed to list directory: {str(e)}"}], "isError": True}

async def execute_shell_command_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    command_str = params.get("command")
    working_dir_str = params.get("working_directory")
    if not command_str or not isinstance(command_str, str):
        return {"content": [{"type": "text", "text": "Missing or invalid 'command' parameter."}], "isError": True}
    if not ALLOW_ARBITRARY_SHELL_COMMANDS:
        return {"content": [{"type": "text", "text": "Shell command execution is disabled."}], "isError": True}
    try:
        cwd_for_command = MCP_BASE_WORKING_DIR.resolve()
        if working_dir_str:
            resolved_custom_cwd = _resolve_and_verify_path(working_dir_str)
            if not resolved_custom_cwd.is_dir():
                return {"content": [{"type": "text", "text": "Working directory does not exist or is not a directory."}], "isError": True}
            cwd_for_command = resolved_custom_cwd
        proc = await asyncio.create_subprocess_shell(
            command_str,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd_for_command)
        )
        stdout, stderr = await proc.communicate()
        results_data = {
            "stdout": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
            "return_code": proc.returncode,
        }
        return {"content": [{"type": "text", "text": json.dumps(results_data, indent=2)}]}
    except Exception as e:
        logger.error(f"Error executing command '{command_str}': {e}", exc_info=True)
        return {"content": [{"type": "text", "text": f"Failed to execute command: {str(e)}"}], "isError": True}

# --- LLM Tools ---

async def llm_generate_code_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    params: {
        "provider": "openai" | "gemini",
        "prompt": str,
        "language": str (optional, e.g., "python"),
        "max_tokens": int (optional, default 256)
    }
    """
    provider = params.get("provider", "openai").lower()
    prompt = params.get("prompt")
    language = params.get("language", "python")
    max_tokens = params.get("max_tokens", 256)
    if not prompt or not isinstance(prompt, str):
        return {"content": [{"type": "text", "text": "Missing or invalid 'prompt' parameter."}], "isError": True}

    if provider == "openai":
        if not OPENAI_API_KEY:
            return {"content": [{"type": "text", "text": "OpenAI API key not set."}], "isError": True}
        api_url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        system_prompt = f"You are a professional code generator. Generate clean, idiomatic {language} code. Respond only with code."
        data = {
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(api_url, headers=headers, json=data)
                resp.raise_for_status()
                result = resp.json()
                code_text = result["choices"][0]["message"]["content"]
                return {"content": [{"type": "text", "text": code_text}]}
        except Exception as e:
            logger.error(f"OpenAI code generation error: {e}", exc_info=True)
            return {"content": [{"type": "text", "text": f"OpenAI error: {e}"}], "isError": True}

    elif provider == "gemini":
        if not GEMINI_API_KEY:
            return {"content": [{"type": "text", "text": "Gemini API key not set."}], "isError": True}
        # Gemini 1.5-pro REST API format
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={GEMINI_API_KEY}"
        data = {
            "contents": [
                {"role": "user", "parts": [{"text": f"Generate {language} code for: {prompt}"}]}
            ],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.3,
                "topP": 1.0,
            }
        }
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(api_url, json=data)
                resp.raise_for_status()
                result = resp.json()
                code_text = result["candidates"][0]["content"]["parts"][0]["text"]
                return {"content": [{"type": "text", "text": code_text}]}
        except Exception as e:
            logger.error(f"Gemini code generation error: {e}", exc_info=True)
            return {"content": [{"type": "text", "text": f"Gemini error: {e}"}], "isError": True}

    else:
        return {"content": [{"type": "text", "text": f"Unknown LLM provider '{provider}'."}], "isError": True}

        # --- Individual Provider MCP Tool Wrappers ---

async def llm_generate_code_openai_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    """Calls llm_generate_code_tool with provider 'openai'."""
    params = dict(params)  # copy so we don't mutate input
    params['provider'] = "openai"
    return await llm_generate_code_tool(params)

async def llm_generate_code_gemini_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    """Calls llm_generate_code_tool with provider 'gemini'."""
    params = dict(params)
    params['provider'] = "gemini"
    return await llm_generate_code_tool(params)


