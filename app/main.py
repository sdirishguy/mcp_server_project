# app/main.py
import asyncio
import logging
import uvicorn

from mcp.server.fastmcp import FastMCP
# We won't use mcp.server.fastmcp.server.Settings directly to control Uvicorn's binding here
# but FastMCP might still use it for its internal app-level config.
from mcp.server.fastmcp.server import Settings as FastMCPSettings 
# ---> ADD THESE STARLETTE IMPORTS IF THEY ARE MISSING <---
from starlette.applications import Starlette
from starlette.routing import Mount 
from starlette.responses import JSONResponse 
# ---> END OF STARLETTE IMPORTS <---
from .config import SERVER_PORT, logger
from .tools import MCP_TOOLS_REGISTRY

try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.info(".env file processed if present.")
except ImportError:
    logger.info("python-dotenv not installed or .env file not found.")

# Create FastMCP instance - its internal settings might still default
# but Uvicorn's settings will control the actual server binding.
mcp_app_level_settings = FastMCPSettings(
    # These might be used by FastMCP for generating URLs or other internal logic
    host="0.0.0.0", # Informational for FastMCP itself
    port=SERVER_PORT, # Informational for FastMCP itself
    log_level=logging.getLevelName(logger.getEffectiveLevel())
)
mcp_instance = FastMCP(
    name="MyDockerizedMCPApp",
    tools=MCP_TOOLS_REGISTRY,
    settings=mcp_app_level_settings
)
logger.info(f"FastMCP instance '{mcp_instance.name}' created. Its internal settings.host='{mcp_instance.settings.host}', settings.port={mcp_instance.settings.port}")

# Create a Starlette root application
root_starlette_app = Starlette(debug=True) # Add debug=True for more verbose errors from Starlette

# Mount the FastMCP components.
# The documentation suggests these methods return ASGI apps.
# The MCP spec typically uses /mcp for SSE and /mcp.json for JSON-RPC (often via POST)
# The streamable_http_app might handle both if it's the primary one.
# The docs say: "Streamable HTTP servers are mounted at /mcp."
# And "SSE servers are mounted at /sse" by default if using FastMCP's own run()
# Let's try mounting streamable_http_app at /mcp as it's preferred.
try:
    http_app_callable = mcp_instance.streamable_http_app() # Call the method
    root_starlette_app.mount("/mcp", app=http_app_callable, name="mcp_http") # Primary MCP endpoint
    logger.info(f"Mounted streamable_http_app from FastMCP at /mcp. Type: {type(http_app_callable)}")

    # If SSE is truly separate and also needed at a different path or for the /mcp path itself
    # and streamable_http_app doesn't cover it:
    # sse_app_callable = mcp_instance.sse_app()
    # root_starlette_app.mount("/mcp_sse_specific_path", app=sse_app_callable, name="mcp_sse")
    # However, "Streamable HTTP transport is superseding SSE transport" implies streamable_http_app is key.
    # It also mentions "Streamable HTTP transport supports: ... JSON or SSE response formats"
    # This means streamable_http_app mounted at /mcp should handle both.

except AttributeError as e:
    logger.error(f"Failed to get or mount FastMCP sub-apps: {e}", exc_info=True)
except Exception as e_mount:
    logger.error(f"General error mounting FastMCP sub-apps: {e_mount}", exc_info=True)


# Add our own simple health check to the root Starlette app
async def health_check_endpoint(request):
    from starlette.responses import JSONResponse
    logger.info("Health check endpoint /health called.")
    return JSONResponse({"status": "ok", "message": "MCP Server (Starlette + FastMCP) is healthy."})

root_starlette_app.add_route("/health", health_check_endpoint, methods=["GET"], name="health")
logger.info("Added /health check endpoint to root Starlette app.")


# This block runs when you execute `python -m app.main`
# It will now start Uvicorn with our Starlette app.
if __name__ == "__main__":
    logger.info(f"Starting Starlette-wrapped FastMCP server with Uvicorn on host 0.0.0.0, port {SERVER_PORT}...")
    try:
        uvicorn.run(
            root_starlette_app, # Serve the Starlette app
            host="0.0.0.0",     # Explicit host for Uvicorn
            port=SERVER_PORT,   # Explicit port for Uvicorn
            log_level=logging.getLevelName(logger.getEffectiveLevel()).lower()
        )
    except Exception as e:
        logger.critical(f"Failed to start Uvicorn server: {e}", exc_info=True)
    finally:
        logger.info("Server process finished or was interrupted.")