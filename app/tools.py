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
    logger,
)

DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_GEMINI_MODEL = "gemini-1.5-pro"
LLM_API_RETRY_SECONDS = 5

# --- Path helpers (unchanged) ---
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

# --- File/Dir/Shell Command Tools (keep these as before, unchanged) ---
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

# --- LLM TOOLS ---

async def llm_generate_code_openai_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    prompt = params.get("prompt")
    language = params.get("language", "python")
    model = params.get("model", DEFAULT_OPENAI_MODEL)
    max_tokens = params.get("max_tokens", 256)
    temperature = params.get("temperature", 0.3)
    system_prompt = params.get("system_prompt", f"You are a professional code generator. Generate clean, idiomatic {language} code. Respond only with code.")

    if not OPENAI_API_KEY:
        return {"content": [{"type": "text", "text": "OpenAI API key not set."}], "isError": True}
    if not prompt or not isinstance(prompt, str):
        return {"content": [{"type": "text", "text": "Missing or invalid 'prompt' parameter."}], "isError": True}

    api_url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(api_url, headers=headers, json=data)
                if resp.status_code == 429:
                    logger.warning("OpenAI quota exceeded (429 Too Many Requests). Retrying in %s seconds...", LLM_API_RETRY_SECONDS)
                    if attempt == 0:
                        await asyncio.sleep(LLM_API_RETRY_SECONDS)
                        continue
                    else:
                        return {"content": [{"type": "text", "text": "OpenAI: API quota exceeded (429 Too Many Requests). Try again later."}], "isError": True}
                resp.raise_for_status()
                result = resp.json()
                code_text = result["choices"][0]["message"]["content"]
                return {"content": [{"type": "text", "text": code_text}]}
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI API error: {e.response.status_code} - {e.response.text}")
            if e.response.status_code in (401, 403):
                return {"content": [{"type": "text", "text": "OpenAI: Invalid or missing API key."}], "isError": True}
            else:
                return {"content": [{"type": "text", "text": f"OpenAI error: {e.response.status_code} - {e.response.text}"}], "isError": True}
        except Exception as e:
            logger.error(f"OpenAI error: {e}", exc_info=True)
            return {"content": [{"type": "text", "text": f"OpenAI error: {e}"}], "isError": True}
    return {"content": [{"type": "text", "text": "OpenAI API call failed after retry."}], "isError": True}

async def llm_generate_code_gemini_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    prompt = params.get("prompt")
    language = params.get("language", "python")
    model = params.get("model", DEFAULT_GEMINI_MODEL)
    max_tokens = params.get("max_tokens", 256)
    temperature = params.get("temperature", 0.3)
    system_prompt = params.get("system_prompt", f"Generate clean, idiomatic {language} code. Respond only with code.")

    if not GEMINI_API_KEY:
        return {"content": [{"type": "text", "text": "Gemini API key not set."}], "isError": True}
    if not prompt or not isinstance(prompt, str):
        return {"content": [{"type": "text", "text": "Missing or invalid 'prompt' parameter."}], "isError": True}

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
    data = {
        "contents": [
            {"role": "user", "parts": [{"text": f"{system_prompt}\n{prompt}"}]}
        ],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
            "topP": 1.0,
        }
    }
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(api_url, json=data)
                if resp.status_code == 429:
                    logger.warning("Gemini quota exceeded (429 Too Many Requests). Retrying in %s seconds...", LLM_API_RETRY_SECONDS)
                    if attempt == 0:
                        await asyncio.sleep(LLM_API_RETRY_SECONDS)
                        continue
                    else:
                        return {"content": [{"type": "text", "text": "Gemini: API quota exceeded (429 Too Many Requests). Try again later."}], "isError": True}
                resp.raise_for_status()
                result = resp.json()
                code_text = result["candidates"][0]["content"]["parts"][0]["text"]
                return {"content": [{"type": "text", "text": code_text}]}
        except httpx.HTTPStatusError as e:
            logger.error(f"Gemini API error: {e.response.status_code} - {e.response.text}")
            if e.response.status_code in (401, 403):
                return {"content": [{"type": "text", "text": "Gemini: Invalid or missing API key."}], "isError": True}
            else:
                return {"content": [{"type": "text", "text": f"Gemini error: {e.response.status_code} - {e.response.text}"}], "isError": True}
        except Exception as e:
            logger.error(f"Gemini error: {e}", exc_info=True)
            return {"content": [{"type": "text", "text": f"Gemini error: {e}"}], "isError": True}
    return {"content": [{"type": "text", "text": "Gemini API call failed after retry."}], "isError": True}

async def llm_generate_code_local_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "content": [
            {"type": "text", "text": "Local LLM support coming soon! (Ollama, LM Studio, etc. will be integrated here.)"}
        ],
        "isError": False,
    }
