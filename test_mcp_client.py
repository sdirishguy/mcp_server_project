# test_mcp_client.py
import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING

import httpx # <--- ADDED IMPORT FOR httpx
from mcp.client.streamable_http import streamablehttp_client 
import mcp.types
from mcp import ClientSession, Tool, Resource

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - CLIENT - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Dynamic Type Resolution with Placeholders ---
if TYPE_CHECKING:
    _Content = mcp.types.Content
    _ContentType = mcp.types.ContentType
    _ErrorData = mcp.types.ErrorData
    _CallToolResult = mcp.types.CallToolResult
else:
    _Content = getattr(mcp.types, 'Content', None)
    _ContentType = getattr(mcp.types, 'ContentType', None)
    _ErrorData = mcp.types.ErrorData 
    _CallToolResult = mcp.types.CallToolResult
    if _Content is None:
        logger.warning("Client: Could not dynamically resolve mcp.types.Content, using placeholder.")
        class PlaceholderContent:
            def __init__(self, type, data): self.type = type; self.data = data
        _Content = PlaceholderContent
    if _ContentType is None:
        logger.warning("Client: Could not dynamically resolve mcp.types.ContentType, using placeholder.")
        class PlaceholderContentType:
            TEXT = "text"; JSON = "json"; IMAGE = "image"
        _ContentType = PlaceholderContentType

# --- Server Configuration ---
SERVER_BASE_URL = "http://localhost:3000"
MCP_SESSION_PATH = "/mcp/" 
MCP_FULL_ENDPOINT_URL = f"{SERVER_BASE_URL.rstrip('/')}{MCP_SESSION_PATH}"

# --- Mock Response and Print Helper (Keep as is from response #50) ---
class MockToolCallResponse:
    def __init__(self, results: Optional[List[_Content]] = None, error: Optional[_ErrorData] = None, raw_response: Optional[Dict] = None):
        self.results = results; self.error = error; self._raw_response = raw_response
    @classmethod
    def from_sdk_response(cls, sdk_response_obj):
        if not all([_Content, _ErrorData, _ContentType]): logger.error("Client: Core types for response parsing not resolved.")
        if hasattr(sdk_response_obj, 'results') and hasattr(sdk_response_obj, 'error'):
            pr = []; err = sdk_response_obj.error
            if sdk_response_obj.results:
                for item in sdk_response_obj.results:
                    if isinstance(item, _Content): pr.append(item)
                    elif isinstance(item, dict) and "type" in item and "data" in item: pr.append(_Content(type=item["type"], data=item["data"]))
                    else: pr.append(_Content(type="unknown_sdk_result_item", data=str(item)))
            if err and not isinstance(err, _ErrorData) and isinstance(err, dict):
                err = _ErrorData(code=err.get("code","ERR"), message=err.get("message", "Unknown"), data=err.get("data"))
            return cls(results=pr if pr else None, error=err)
        elif isinstance(sdk_response_obj, dict):
            rl = sdk_response_obj.get("results"); pr = []
            if rl:
                for item_dict in rl:
                    if isinstance(item_dict, dict) and "type" in item_dict and "data" in item_dict:
                        ctvs = item_dict["type"]; actual_ct = ctvs
                        if _ContentType is not PlaceholderContentType:
                           if hasattr(_ContentType, ctvs.upper()): actual_ct = getattr(_ContentType, ctvs.upper())
                           elif hasattr(_ContentType, '__call__') and not isinstance(_ContentType, type(type)):
                               try: actual_ct = _ContentType(ctvs)
                               except (ValueError, TypeError): pass
                        pr.append(_Content(type=actual_ct, data=item_dict["data"]))
                    else: pr.append(_Content(type="unknown_dict_item", data=str(item_dict)))
            ed = sdk_response_obj.get("error"); pe = None
            if ed and isinstance(ed, dict) and "code" in ed and "message" in ed:
                pe = _ErrorData(code=ed["code"], message=ed["message"], data=ed.get("data"))
            return cls(results=pr if pr else None, error=pe, raw_response=sdk_response_obj)
        return cls(raw_response={"unknown_response_format": str(sdk_response_obj)})

def print_tool_call_summary(tool_name: str, params: Dict[str, Any], response_wrapper: MockToolCallResponse):
    logger.info(f"--- Calling Tool: {tool_name} ---"); logger.info(f"Params: {json.dumps(params)}")
    if response_wrapper.error:
        logger.error(f"Error Code: {response_wrapper.error.code}"); logger.error(f"Error Message: {response_wrapper.error.message}")
        if response_wrapper.error.data: logger.error(f"Error Data: {response_wrapper.error.data}")
    elif response_wrapper.results:
        logger.info("Results:")
        for ci in response_wrapper.results:
            ctv = ci.type; cts = ctv.value if hasattr(ctv, 'value') and not isinstance(ctv, str) else str(ctv)
            logger.info(f"  - Type: {cts}"); logger.info(f"    Data: {str(ci.data)[:200]}")
    elif response_wrapper._raw_response: logger.info(f"Raw Response (parse failed): {json.dumps(response_wrapper._raw_response, indent=2)}")
    else: logger.warning("No results/error/raw in response.")
    logger.info("------------------------------------\n")

# --- Main Test Logic ---
async def main_test_logic():
    if _Content is PlaceholderContent or _ContentType is PlaceholderContentType:
        logger.warning("Client is using placeholder types for Content/ContentType. Result parsing might be limited.")
    if not _ErrorData or not _CallToolResult:
        logger.critical("Essential MCP types ErrorData or CallToolResult could not be resolved. Client will likely fail.")
        return

    logger.info(f"Attempting to establish MCP stream connection to {MCP_FULL_ENDPOINT_URL}...")
    try:
        # Removed timeout argument from streamablehttp_client
        async with streamablehttp_client(MCP_FULL_ENDPOINT_URL) as (read_stream, write_stream, initial_http_response):
            logger.info(f"Stream connection established. Initial HTTP response status: {initial_http_response.status_code if initial_http_response else 'N/A'}")

            async with ClientSession(
                read_stream, 
                write_stream,
                client_id="test-client-py-v1.5", 
                display_name="Python MCP Stream Test Client"
            ) as client:
                logger.info(f"ClientSession created. Attempting to initialize...")
                initialize_response = await client.initialize()
                logger.info(f"Successfully initialized with server. Server capabilities: {initialize_response}")

                # Tool Listing
                available_tools_raw: List[Dict] = await client.list_tools()
                logger.info(f"Raw response from list_tools: {available_tools_raw}")
                if isinstance(available_tools_raw, list):
                    for tool_data in available_tools_raw:
                        tool_instance = Tool(**tool_data) if isinstance(tool_data, dict) else tool_data
                        if isinstance(tool_instance, Tool):
                            logger.info(f"  - Discovered Tool: Name={tool_instance.name}, Desc={tool_instance.description}")
                            if hasattr(tool_instance, 'inputSchema'): logger.info(f"    Schema: {tool_instance.inputSchema}")
                        else: logger.warning(f"Unexpected tool data format: {tool_data}")
                else: logger.warning("No tools listed or unexpected format.")

                logger.info("\n--- Starting Tool Call Tests ---")
                test_dir = "test_client_stream_final_v2" # New unique name
                params_create = {"path": test_dir}
                resp_create = await client.call_tool("file_system_create_directory", params_create)
                print_tool_call_summary("file_system_create_directory", params_create, MockToolCallResponse.from_sdk_response(resp_create))

                test_file = f"{test_dir}/hello_stream_final_v2.txt"
                params_write = {"path": test_file, "content": "Hello from the fully streamed client!"}
                resp_write = await client.call_tool("file_system_write_file", params=params_write)
                print_tool_call_summary("file_system_write_file", params_write, MockToolCallResponse.from_sdk_response(resp_write))

                params_read = {"path": test_file}
                resp_read = await client.call_tool("file_system_read_file", params=params_read)
                print_tool_call_summary("file_system_read_file", params_read, MockToolCallResponse.from_sdk_response(resp_read))

                params_list = {"path": test_dir}
                resp_list = await client.call_tool("file_system_list_directory", params_list)
                print_tool_call_summary("file_system_list_directory", params_list, MockToolCallResponse.from_sdk_response(resp_list))

                params_exec = {"command": "echo 'Shell test via fully streamed client'"}
                resp_exec = await client.call_tool("execute_shell_command", params=params_exec)
                print_tool_call_summary("execute_shell_command", params_exec, MockToolCallResponse.from_sdk_response(resp_exec))

    except ConnectionRefusedError:
        logger.error(f"Connection refused. Is the MCP server running at {MCP_FULL_ENDPOINT_URL}?")
    except httpx.ConnectError as e: # httpx import is now present
        logger.error(f"HTTPX ConnectError to {MCP_FULL_ENDPOINT_URL}: {e}. Is server URL correct & server running?")
    except Exception as e:
        logger.error(f"An error occurred during client operations: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        asyncio.run(main_test_logic())
    except KeyboardInterrupt:
        logger.info("Test client terminated by user.")