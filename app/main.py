# app/main.py
import asyncio
import logging
import uvicorn

from mcp.server.fastmcp import FastMCP
from .config import SERVER_PORT, logger
from .tools import MCP_TOOLS_REGISTRY

# Import Starlette components
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.responses import JSONResponse # For health check

try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.info(".env file processed if present.")
except ImportError:
    logger.info("python-dotenv not installed or .env file not found.")

# Create the FastMCP master instance
mcp_master_instance = FastMCP(
    tools=MCP_TOOLS_REGISTRY,
    server_id="python-mcp-server-docker-v1",
    display_name="Python MCP Development Server (Dockerized)",
    description="An MCP server providing file system and shell command tools, running in Docker.",
)
logger.info(f"FastMCP master instance created with {len(MCP_TOOLS_REGISTRY)} tools.")

# --- Create a root Starlette application and mount MCP components ---
root_asgi_app = Starlette(debug=True) # Enable debug mode for more detailed errors if needed

try:
    sse_app_callable = mcp_master_instance.sse_app() # Call the method to get the ASGI app
    root_asgi_app.mount("/mcp", app=sse_app_callable, name="mcp_sse")
    logger.info(f"Mounted sse_app from FastMCP at /mcp. Type: {type(sse_app_callable)}")
except AttributeError:
    logger.error("mcp_master_instance does not have .sse_app() method or it failed.")
except Exception as e:
    logger.error(f"Error getting or mounting sse_app: {e}", exc_info=True)

try:
    # streamable_http_app likely handles JSON-RPC, often at /mcp.json
    http_app_callable = mcp_master_instance.streamable_http_app() # Call the method
    root_asgi_app.mount("/mcp.json", app=http_app_callable, name="mcp_jsonrpc")
    logger.info(f"Mounted streamable_http_app from FastMCP at /mcp.json. Type: {type(http_app_callable)}")
except AttributeError:
    logger.error("mcp_master_instance does not have .streamable_http_app() method or it failed.")
except Exception as e:
    logger.error(f"Error getting or mounting streamable_http_app: {e}", exc_info=True)

# Add a simple health check to the root Starlette app
async def health_check_endpoint(request):
    logger.info("Health check endpoint /health called.")
    return JSONResponse({"status": "ok", "message": "MCP Server (Starlette + FastMCP) is healthy."})

root_asgi_app.add_route("/health", health_check_endpoint, methods=["GET"], name="health")
logger.info("Added /health check endpoint to root Starlette app.")


async def run_composite_server():
    logger.info("Starting composed ASGI application (Starlette + FastMCP sub-apps) with Uvicorn...")
    try:
        config = uvicorn.Config(
            app=root_asgi_app,  # Pass the composite Starlette app
            host="0.0.0.0",
            port=SERVER_PORT,
            log_level=logging.getLevelName(logger.getEffectiveLevel()).lower(),
        )
        server = uvicorn.Server(config)
        await server.serve()
    except Exception as e:
        logger.critical(f"Uvicorn server crashed: {e}", exc_info=True)
    finally:
        logger.info("Uvicorn server process finished or encountered an error.")

if __name__ == "__main__":
    # The Starlette app 'root_asgi_app' is defined at module level
    # Uvicorn can also run it via import string: "app.main:root_asgi_app"
    # but programmatic start is fine.
    asyncio.run(run_composite_server())