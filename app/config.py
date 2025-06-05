# app/config.py

import os
from pathlib import Path
import logging

# --- Logging setup ---
logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO").upper(),
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp.config")

# --- Server Configuration ---
DEFAULT_SERVER_PORT = 8000  # Convention for MCP/FastAPI
SERVER_PORT = int(os.environ.get("MCP_SERVER_PORT", DEFAULT_SERVER_PORT))
logger.info(f"Server port configured to: {SERVER_PORT}")

# --- Tools Base Directory ---
DEFAULT_BASE_DIR = Path("/app/host_data")
MCP_BASE_WORKING_DIR = Path(
    os.environ.get("MCP_BASE_WORKING_DIR", str(DEFAULT_BASE_DIR))
).resolve()

try:
    MCP_BASE_WORKING_DIR.mkdir(parents=True, exist_ok=True)
    # Try to make it accessible for container user (non-root)
    if MCP_BASE_WORKING_DIR.exists():
        os.chmod(MCP_BASE_WORKING_DIR, 0o750)
    logger.info(f"MCP base working directory: {MCP_BASE_WORKING_DIR}")
except Exception as e:
    logger.error(f"Could not create or access MCP base working directory {MCP_BASE_WORKING_DIR}: {e}")
    # If this fails, file-system tools will also fail!

# --- Security Configuration ---
# For production, set via env: MCP_ALLOW_SHELL=0 to disable shell tool
ALLOW_ARBITRARY_SHELL_COMMANDS = os.environ.get("MCP_ALLOW_SHELL", "1") == "1"
if not ALLOW_ARBITRARY_SHELL_COMMANDS:
    logger.warning("Shell command tool is DISABLED by config.")

logger.info("Configuration loaded.")
