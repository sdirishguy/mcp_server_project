"""Legacy MCP client test module.

This module provides comprehensive testing for the Model Context Protocol (MCP) client
functionality, including dynamic type resolution, tool calling, and server communication.
"""

import asyncio
import datetime
import json
import logging
from typing import TYPE_CHECKING, Any

import httpx
import mcp.types
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - CLIENT - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f"client_run_{datetime.date.today()}.log", mode="a"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


# --- Placeholder Classes (defined globally) ---
class PlaceholderContent:
    """Placeholder for mcp.types.Content when not available."""

    def __init__(self, content_type, data):
        """Initialize placeholder content.

        Args:
            content_type: The type of content
            data: The content data
        """
        self.type = content_type
        self.data = data


class PlaceholderContentType:
    """Placeholder for mcp.types.ContentType when not available."""

    TEXT = "text"
    JSON = "json"
    IMAGE = "image"


class PlaceholderErrorData:
    """Placeholder for mcp.types.ErrorData when not available."""

    def __init__(self, code, message, data=None):
        """Initialize placeholder error data.

        Args:
            code: Error code
            message: Error message
            data: Optional additional error data
        """
        self.code = code
        self.message = message
        self.data = data


class PlaceholderCallToolResult:
    """Placeholder for mcp.types.CallToolResult when not available."""

    def __init__(self, results=None, error=None):
        """Initialize placeholder call tool result.

        Args:
            results: Tool call results
            error: Tool call error if any
        """
        self.results = results
        self.error = error


# --- Dynamic Type Resolution with Placeholders ---
if TYPE_CHECKING:
    _Content = mcp.types.Content
    _ContentType = mcp.types.ContentType
    _ErrorData = mcp.types.ErrorData
    _CallToolResult = mcp.types.CallToolResult
else:
    _Content = getattr(mcp.types, "Content", None)
    if _Content is None:
        logger.warning(
            "Client: Could not resolve mcp.types.Content via getattr, using placeholder."
        )
        _Content = PlaceholderContent

    CONTENT_TYPE = getattr(mcp.types, "ContentType", None)
    if CONTENT_TYPE is None:
        logger.warning(
            "Client: Could not resolve mcp.types.ContentType via getattr, using placeholder."
        )
        CONTENT_TYPE = PlaceholderContentType
    _ContentType = CONTENT_TYPE

    _ErrorData = getattr(mcp.types, "ErrorData", None)
    if _ErrorData is None:
        logger.error("CRITICAL: Client could not resolve mcp.types.ErrorData! Using placeholder.")
        _ErrorData = PlaceholderErrorData

    _CallToolResult = getattr(mcp.types, "CallToolResult", None)
    if _CallToolResult is None:
        logger.error(
            "CRITICAL: Client could not resolve mcp.types.CallToolResult! Using placeholder."
        )
        _CallToolResult = PlaceholderCallToolResult


# --- Server Configuration ---
SERVER_BASE_URL = "http://localhost:8000"
MCP_FULL_ENDPOINT_URL = f"{SERVER_BASE_URL}/mcp"


# --- Mock Response and Print Helper ---
class MockToolCallResponse:
    """Mock response wrapper for tool call results."""

    def __init__(
        self,
        results: list[_Content] | None = None,
        error: _ErrorData | None = None,
        raw_response: dict | None = None,
    ):
        self.results = results
        self.error = error
        self._raw_response = raw_response

    @classmethod
    def from_sdk_response(cls, sdk_response_obj):
        """Create MockToolCallResponse from SDK response object.

        Args:
            sdk_response_obj: The response object from the SDK

        Returns:
            MockToolCallResponse: Parsed response wrapper
        """
        if not all([_Content, _ErrorData, _ContentType, _CallToolResult]):
            logger.error(
                "Client: Core types for response parsing not resolved or are "
                "placeholders. Parsing may be basic/unreliable."
            )

        if hasattr(sdk_response_obj, "results") and hasattr(sdk_response_obj, "error"):
            parsed_results = []
            if sdk_response_obj.results:
                for item in sdk_response_obj.results:
                    if isinstance(item, _Content):
                        parsed_results.append(item)
                    elif isinstance(item, dict) and "type" in item and "data" in item:
                        parsed_results.append(_Content(type=item["type"], data=item["data"]))
                    else:
                        parsed_results.append(
                            _Content(type="unknown_sdk_result_item", data=str(item))
                        )
            parsed_error = sdk_response_obj.error
            if (
                sdk_response_obj.error
                and not isinstance(sdk_response_obj.error, _ErrorData)
                and isinstance(sdk_response_obj.error, dict)
            ):
                parsed_error = _ErrorData(
                    code=sdk_response_obj.error.get("code", "UNKNOWN_ERROR_CODE"),
                    message=sdk_response_obj.error.get("message", "Unknown error"),
                    data=sdk_response_obj.error.get("data"),
                )
            return cls(results=parsed_results if parsed_results else None, error=parsed_error)
        elif isinstance(sdk_response_obj, dict):
            results_list = sdk_response_obj.get("results")
            parsed_results = []
            if results_list:
                for item_dict in results_list:
                    if isinstance(item_dict, dict) and "type" in item_dict and "data" in item_dict:
                        content_type_value_str = item_dict["type"]
                        actual_content_type = content_type_value_str

                        if _ContentType is not PlaceholderContentType:
                            if hasattr(_ContentType, content_type_value_str.upper()):
                                actual_content_type = getattr(
                                    _ContentType, content_type_value_str.upper()
                                )
                            elif callable(_ContentType) and not isinstance(
                                _ContentType, type(type)
                            ):
                                try:
                                    actual_content_type = _ContentType(content_type_value_str)
                                except (ValueError, TypeError):
                                    pass

                        parsed_results.append(
                            _Content(type=actual_content_type, data=item_dict["data"])
                        )
                    else:
                        parsed_results.append(
                            _Content(type="unknown_dict_item", data=str(item_dict))
                        )

            error_dict = sdk_response_obj.get("error")
            parsed_error = None
            if (
                error_dict
                and isinstance(error_dict, dict)
                and "code" in error_dict
                and "message" in error_dict
            ):
                parsed_error = _ErrorData(
                    code=error_dict["code"],
                    message=error_dict["message"],
                    data=error_dict.get("data"),
                )

            return cls(
                results=parsed_results if parsed_results else None,
                error=parsed_error,
                raw_response=sdk_response_obj,
            )

        logger.warning(
            "SDK response format not directly parseable: %s. Storing as raw.",
            type(sdk_response_obj),
        )
        return cls(raw_response={"unknown_response_format": str(sdk_response_obj)})


def print_tool_call_summary(
    tool_name: str, params: dict[str, Any], response_wrapper: MockToolCallResponse
):
    """Print a summary of a tool call and its response.

    Args:
        tool_name: Name of the tool that was called
        params: Parameters passed to the tool
        response_wrapper: Wrapped response from the tool call
    """
    logger.info("--- Calling Tool: %s ---", tool_name)
    logger.info("Params: %s", json.dumps(params))
    if response_wrapper.error:
        logger.error("Error Code: %s", getattr(response_wrapper.error, "code", "N/A"))
        logger.error("Error Message: %s", getattr(response_wrapper.error, "message", "N/A"))
        if hasattr(response_wrapper.error, "data") and response_wrapper.error.data:
            logger.error("Error Data: %s", response_wrapper.error.data)
    elif response_wrapper.results:
        logger.info("Results:")
        for content_item in response_wrapper.results:
            content_type_val = getattr(content_item, "type", "unknown_type")
            content_type_str = (
                content_type_val.value
                if hasattr(content_type_val, "value") and not isinstance(content_type_val, str)
                else str(content_type_val)
            )
            logger.info("  - Type: %s", content_type_str)
            logger.info("    Data: %s", str(getattr(content_item, "data", "N/A"))[:200])
    elif getattr(response_wrapper, "_raw_response", None):  # pylint: disable=protected-access
        logger.info(
            "Raw Response (could not parse into known structure): %s",
            json.dumps(getattr(response_wrapper, "_raw_response"), indent=2),
        )
    else:
        logger.warning("No results or error in response, and no raw data found.")
    logger.info("------------------------------------\n")


# --- Main Test Logic ---
async def main_test_logic():
    """Main test logic for MCP client functionality."""
    if _Content is PlaceholderContent:
        logger.warning("Client is using placeholder for Content type.")
    if _ContentType is PlaceholderContentType:
        logger.warning("Client is using placeholder for ContentType type.")
    if _ErrorData is PlaceholderErrorData:
        logger.error(
            "CRITICAL: Client using placeholder for ErrorData. Error parsing will be basic."
        )
    if _CallToolResult is PlaceholderCallToolResult:
        logger.error(
            "CRITICAL: Client using placeholder for CallToolResult. "
            "Tool call result parsing may be basic."
        )

    logger.info("Attempting to establish MCP stream connection to %s...", MCP_FULL_ENDPOINT_URL)
    try:
        async with streamablehttp_client(MCP_FULL_ENDPOINT_URL) as (
            read_stream,
            write_stream,
            initial_http_response_or_other,
        ):
            status_code_to_log = "N/A"
            if initial_http_response_or_other:
                if hasattr(initial_http_response_or_other, "status_code"):
                    status_code_to_log = initial_http_response_or_other.status_code
                else:
                    logger.info(
                        "Stream conn: Third yielded item type: %s, value: %s",
                        type(initial_http_response_or_other),
                        str(initial_http_response_or_other)[:100],
                    )

            if status_code_to_log != "N/A":
                logger.info("Stream conn: Initial HTTP status: %s", status_code_to_log)
            else:
                logger.info("Stream conn established (status code N/A from third yielded item).")

            async with ClientSession(read_stream, write_stream) as client:
                logger.info("ClientSession created. Attempting to initialize...")
                initialize_response = await client.initialize()
                logger.info(
                    "Successfully initialized with server. Server capabilities: %s",
                    initialize_response,
                )

                available_tools_raw = await client.list_tools()
                logger.info("Raw response from list_tools: %s", available_tools_raw)
                if hasattr(available_tools_raw, "tools"):
                    for tool_instance in available_tools_raw.tools:
                        logger.info(
                            "  - Discovered Tool: Name=%s, Desc=%s",
                            tool_instance.name,
                            tool_instance.description,
                        )
                        if hasattr(tool_instance, "inputSchema"):
                            logger.info("    Schema: %s", tool_instance.inputSchema)
                else:
                    logger.warning("No tools listed or unexpected format.")

                logger.info("\n--- Starting Tool Call Tests ---")
                test_dir = "test_client_final_final_dir"
                params_create = {"path": test_dir}
                response_create_raw = await client.call_tool(
                    name="file_system_create_directory", arguments={"params": params_create}
                )
                print_tool_call_summary(
                    "file_system_create_directory",
                    params_create,
                    MockToolCallResponse.from_sdk_response(response_create_raw),
                )

                test_file_path = f"{test_dir}/hello_mcp_client_ultimate.txt"
                params_write = {
                    "path": test_file_path,
                    "content": "Hello from the hopefully final Python MCP test client!",
                }
                response_write_raw = await client.call_tool(
                    name="file_system_write_file", arguments={"params": params_write}
                )
                print_tool_call_summary(
                    "file_system_write_file",
                    params_write,
                    MockToolCallResponse.from_sdk_response(response_write_raw),
                )

                params_read = {"path": test_file_path}
                response_read_raw = await client.call_tool(
                    name="file_system_read_file", arguments={"params": params_read}
                )
                print_tool_call_summary(
                    "file_system_read_file",
                    params_read,
                    MockToolCallResponse.from_sdk_response(response_read_raw),
                )

                params_list_dir = {"path": test_dir}
                response_list_raw = await client.call_tool(
                    name="file_system_list_directory", arguments={"params": params_list_dir}
                )
                print_tool_call_summary(
                    "file_system_list_directory (specific dir)",
                    params_list_dir,
                    MockToolCallResponse.from_sdk_response(response_list_raw),
                )

                safe_command = "echo 'MCP shell test from client: This should be it!'"
                params_exec = {"command": safe_command}
                response_exec_raw = await client.call_tool(
                    name="execute_shell_command", arguments={"params": params_exec}
                )
                print_tool_call_summary(
                    "execute_shell_command (echo)",
                    params_exec,
                    MockToolCallResponse.from_sdk_response(response_exec_raw),
                )

                # --- OpenAI LLM Tool Call ---
                llm_params_openai = {
                    "prompt": "Write a Python function that returns Fibonacci numbers up to n.",
                    "language": "python",
                    "model": "gpt-4o",
                    "temperature": 0.2,
                    "max_tokens": 256,
                }
                llm_response_raw_openai = await client.call_tool(
                    name="llm_generate_code_openai", arguments={"params": llm_params_openai}
                )
                print_tool_call_summary(
                    "llm_generate_code_openai",
                    llm_params_openai,
                    MockToolCallResponse.from_sdk_response(llm_response_raw_openai),
                )

                # --- Gemini LLM Tool Call ---
                llm_params_gemini = {
                    "prompt": "Write a Python function that sorts a list using bubble sort.",
                    "language": "python",
                    "model": "gemini-1.5-pro",
                    "temperature": 0.2,
                    "max_tokens": 256,
                }
                llm_response_raw_gemini = await client.call_tool(
                    name="llm_generate_code_gemini", arguments={"params": llm_params_gemini}
                )
                print_tool_call_summary(
                    "llm_generate_code_gemini",
                    llm_params_gemini,
                    MockToolCallResponse.from_sdk_response(llm_response_raw_gemini),
                )

                # --- Local LLM Tool Call (Placeholder) ---
                llm_params_local = {
                    "prompt": "Generate a bash script that lists all files in a directory.",
                    "language": "bash",
                    "model": "ollama:code",  # placeholder
                    "temperature": 0.2,
                    "max_tokens": 128,
                }
                llm_response_raw_local = await client.call_tool(
                    name="llm_generate_code_local", arguments={"params": llm_params_local}
                )
                print_tool_call_summary(
                    "llm_generate_code_local",
                    llm_params_local,
                    MockToolCallResponse.from_sdk_response(llm_response_raw_local),
                )

    except ConnectionRefusedError:
        logger.error("Connection refused. Is the MCP server running at %s?", MCP_FULL_ENDPOINT_URL)
    except httpx.ConnectError as connect_error:
        logger.error(
            "HTTPX ConnectError to %s: %s. Is server URL correct & server running?",
            MCP_FULL_ENDPOINT_URL,
            connect_error,
        )
    except Exception as general_error:  # pylint: disable=broad-exception-caught
        logger.error("An error occurred during client operations: %s", general_error, exc_info=True)


if __name__ == "__main__":
    try:
        asyncio.run(main_test_logic())
    except KeyboardInterrupt:
        logger.info("Test client terminated by user.")
