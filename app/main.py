# app/main.py

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.responses import JSONResponse
import logging

from app.tools import ALL_TOOLS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - SERVER - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# 1. Set up FastMCP instance
mcp = FastMCP("MCP Server", stateless_http=True)

# 2. Register all tools
for tool in ALL_TOOLS:
    mcp.tool(
        name=tool["name"],
        description=tool["description"]
    )(tool["handler"])
logger.info(f"Registered {len(ALL_TOOLS)} tools with FastMCP.")

# 3. Build the ASGI Starlette app with http_app (the modern way)
#    (Change path="/mcp.json" if you prefer another URL, but match your client!)
mcp_app = mcp.http_app(path="/mcp.json/")  # Path inside the sub-app

routes = [
    Mount("/api", app=mcp_app),   # MCP endpoint = /api/mcp.json
    # ... you can add other routes/mounts here if needed
]

# 4. Make sure to propagate the lifespan from mcp_app for background session mgmt!
app = Starlette(
    debug=True,
    routes=routes,
    lifespan=mcp_app.lifespan
)

# 5. Extra: Healthcheck route
@app.route("/health")
async def health(request):
    return JSONResponse({"status": "ok", "message": "MCP Server is running!"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
