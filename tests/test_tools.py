"""
Unit tests for the tools module.

This module tests all tool functions with proper mocking and error handling.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.tools import (
    _is_command_allowed,
    _resolve_and_verify_path,
    execute_shell_command_tool,
    file_system_create_directory_tool,
    file_system_list_directory_tool,
    file_system_read_file_tool,
    file_system_write_file_tool,
    llm_generate_code_gemini_tool,
    llm_generate_code_openai_tool,
)


class TestFileSystemTools:
    """Test filesystem-related tools."""

    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Create a temporary directory for testing."""
        return tmp_path

    @pytest.mark.asyncio
    async def test_create_directory_success(self, temp_dir):
        """Test successful directory creation."""
        test_path = "test_dir"

        with patch("app.tools.MCP_BASE_WORKING_DIR", temp_dir):
            result = await file_system_create_directory_tool(test_path)

        assert result.get("isError") is not True
        assert "created" in result["content"][0]["text"]
        assert (temp_dir / test_path).exists()
        assert (temp_dir / test_path).is_dir()

    @pytest.mark.asyncio
    async def test_create_directory_path_traversal_attempt(self, temp_dir):
        """Test directory creation with path traversal attempt."""
        malicious_path = "../../../etc/passwd"

        with patch("app.tools.MCP_BASE_WORKING_DIR", temp_dir):
            result = await file_system_create_directory_tool(malicious_path)

        assert result["isError"] is True
        assert "Path traversal outside of sandbox is not allowed" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_write_file_success(self, temp_dir):
        """Test successful file writing."""
        test_path = "test_file.txt"
        test_content = "Hello, World!"

        with patch("app.tools.MCP_BASE_WORKING_DIR", temp_dir):
            result = await file_system_write_file_tool(test_path, test_content)

        assert result.get("isError") is not True
        assert "written successfully" in result["content"][0]["text"]
        assert (temp_dir / test_path).exists()
        assert (temp_dir / test_path).read_text() == test_content

    @pytest.mark.asyncio
    async def test_read_file_success(self, temp_dir):
        """Test successful file reading."""
        test_path = "test_file.txt"
        test_content = "Hello, World!"

        # Create the file first
        (temp_dir / test_path).write_text(test_content)

        with patch("app.tools.MCP_BASE_WORKING_DIR", temp_dir):
            result = await file_system_read_file_tool(test_path)

        assert result.get("isError") is not True
        assert result["content"][0]["text"] == test_content

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, temp_dir):
        """Test reading non-existent file."""
        test_path = "nonexistent_file.txt"

        with patch("app.tools.MCP_BASE_WORKING_DIR", temp_dir):
            result = await file_system_read_file_tool(test_path)

        assert result["isError"] is True
        assert "File not found" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_list_directory_success(self, temp_dir):
        """Test successful directory listing."""
        # Create some test files and directories
        (temp_dir / "file1.txt").touch()
        (temp_dir / "file2.txt").touch()
        (temp_dir / "dir1").mkdir()

        with patch("app.tools.MCP_BASE_WORKING_DIR", temp_dir):
            result = await file_system_list_directory_tool(".")

        assert result.get("isError") is not True
        content = json.loads(result["content"][0]["text"])
        assert len(content) == 3
        assert any("file1.txt" in item for item in content)
        assert any("file2.txt" in item for item in content)
        assert any("dir1" in item for item in content)

    @pytest.mark.asyncio
    async def test_list_directory_not_found(self, temp_dir):
        """Test listing non-existent directory."""
        test_path = "nonexistent_dir"

        with patch("app.tools.MCP_BASE_WORKING_DIR", temp_dir):
            result = await file_system_list_directory_tool(test_path)

        assert result["isError"] is True
        assert "Directory not found" in result["content"][0]["text"]


class TestShellCommandTools:
    """Test shell command execution tools."""

    @pytest.mark.asyncio
    async def test_shell_command_disabled(self):
        """Test shell command when disabled."""
        with patch("app.tools.ALLOW_ARBITRARY_SHELL_COMMANDS", False):
            result = await execute_shell_command_tool("ls")

        assert result["isError"] is True
        assert "disabled by configuration" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_shell_command_invalid_length(self):
        """Test shell command with invalid length."""
        long_command = "x" * 5000

        with patch("app.tools.ALLOW_ARBITRARY_SHELL_COMMANDS", True):
            result = await execute_shell_command_tool(long_command)

        assert result["isError"] is True
        assert "Invalid command length" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_shell_command_illegal_tokens(self):
        """Test shell command with illegal tokens."""
        illegal_commands = [
            "ls; rm -rf /",
            "ls && rm -rf /",
            "ls || rm -rf /",
            "ls `rm -rf /`",
            "ls $(rm -rf /)",
            "ls |& rm -rf /",
        ]

        with patch("app.tools.ALLOW_ARBITRARY_SHELL_COMMANDS", True):
            for command in illegal_commands:
                result = await execute_shell_command_tool(command)
                assert result["isError"] is True
                assert "illegal tokens" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_shell_command_success(self, tmp_path):
        """Test successful shell command execution."""
        with patch("app.tools.ALLOW_ARBITRARY_SHELL_COMMANDS", True):
            with patch("app.tools.MCP_BASE_WORKING_DIR", tmp_path):
                with patch("asyncio.create_subprocess_shell") as mock_subprocess:
                    # Mock successful subprocess
                    mock_proc = AsyncMock()
                    mock_proc.communicate.return_value = (b"test output", b"")
                    mock_proc.returncode = 0
                    mock_subprocess.return_value = mock_proc

                    result = await execute_shell_command_tool("echo test")

        assert result.get("isError") is not True
        content = json.loads(result["content"][0]["text"])
        assert content["stdout"] == "test output"
        assert content["return_code"] == 0


class TestLLMTools:
    """Test LLM code generation tools."""

    @pytest.mark.asyncio
    async def test_openai_tool_no_api_key(self):
        """Test OpenAI tool without API key."""
        with patch("app.tools.OPENAI_API_KEY", None):
            result = await llm_generate_code_openai_tool("print hello")

        assert result["isError"] is True
        assert "API key not set" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_openai_tool_success(self):
        """Test successful OpenAI code generation."""
        mock_response = {"choices": [{"message": {"content": "print('Hello, World!')"}}]}

        with patch("app.tools.OPENAI_API_KEY", "test-key"):
            with patch("httpx.AsyncClient.post") as mock_post:
                # Create a proper mock response object
                mock_response_obj = MagicMock()
                mock_response_obj.json.return_value = mock_response
                mock_response_obj.raise_for_status = MagicMock()
                mock_post.return_value = mock_response_obj

                result = await llm_generate_code_openai_tool("print hello")

        assert result.get("isError") is not True
        assert "print('Hello, World!')" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_openai_tool_http_error(self):
        """Test OpenAI tool with HTTP error."""
        with patch("app.tools.OPENAI_API_KEY", "test-key"):
            with patch("httpx.AsyncClient.post") as mock_post:
                mock_post.side_effect = httpx.HTTPStatusError(
                    "400 Bad Request",
                    request=MagicMock(),
                    response=MagicMock(status_code=400, text="Invalid request"),
                )

                result = await llm_generate_code_openai_tool("print hello")

        assert result["isError"] is True
        assert "OpenAI error: 400" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_gemini_tool_no_api_key(self):
        """Test Gemini tool without API key."""
        with patch("app.tools.GEMINI_API_KEY", None):
            result = await llm_generate_code_gemini_tool("print hello")

        assert result["isError"] is True
        assert "API key not set" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_gemini_tool_success(self):
        """Test successful Gemini code generation."""
        mock_response = {"candidates": [{"content": {"parts": [{"text": "print('Hello, World!')"}]}}]}

        with patch("app.tools.GEMINI_API_KEY", "test-key"):
            with patch("httpx.AsyncClient.post") as mock_post:
                # Create a proper mock response object
                mock_response_obj = MagicMock()
                mock_response_obj.json.return_value = mock_response
                mock_response_obj.raise_for_status = MagicMock()
                mock_post.return_value = mock_response_obj

                result = await llm_generate_code_gemini_tool("print hello")

        assert result.get("isError") is not True
        assert "print('Hello, World!')" in result["content"][0]["text"]


class TestUtilityFunctions:
    """Test utility functions."""

    def test_resolve_and_verify_path_valid(self, tmp_path):
        """Test valid path resolution."""
        test_path = "test_dir"

        with patch("app.tools.MCP_BASE_WORKING_DIR", tmp_path):
            result = _resolve_and_verify_path(test_path)

        assert result == tmp_path / test_path

    def test_resolve_and_verify_path_traversal(self, tmp_path):
        """Test path traversal prevention."""
        malicious_path = "../../../etc/passwd"

        with patch("app.tools.MCP_BASE_WORKING_DIR", tmp_path):
            with pytest.raises(PermissionError):
                _resolve_and_verify_path(malicious_path)

    def test_is_command_allowed_valid(self):
        """Test valid command validation."""
        valid_commands = ["ls", "echo hello", "cat file.txt"]

        for command in valid_commands:
            is_allowed, reason = _is_command_allowed(command)
            assert is_allowed is True
            assert reason == ""

    def test_is_command_allowed_invalid(self):
        """Test invalid command validation."""
        invalid_commands = [
            ("", "Invalid command length"),
            ("x" * 5000, "Invalid command length"),
            ("ls; rm -rf /", "illegal tokens"),
            ("ls && rm -rf /", "illegal tokens"),
        ]

        for command, expected_reason in invalid_commands:
            is_allowed, reason = _is_command_allowed(command)
            assert is_allowed is False
            assert expected_reason in reason
