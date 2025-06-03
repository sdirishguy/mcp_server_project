# app/config.py
import os
from pathlib import Path
import logging

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Server Port Configuration ---
DEFAULT_SERVER_PORT = 8000  # Default to 8000 for local dev
SERVER_PORT = int(os.environ.get("MCP_SERVER_PORT", DEFAULT_SERVER_PORT))
logger.info(f"Server port configured to: {SERVER_PORT}")

# --- Tools Working Directory Configuration ---
# Prefer a writable local directory for WSL2/Windows (you can change this!)
DEFAULT_LOCAL_MCP_BASE_WORKING_DIR = "/mnt/d/mcp_server_project/shared_host_folder"
DEFAULT_DOCKER_MCP_BASE_WORKING_DIR = "/app/host_data"  # Used in Docker container

# If running in Docker, the user should override with env var.
DEFAULT_MCP_BASE_WORKING_DIR = os.environ.get(
    "MCP_BASE_WORKING_DIR", 
    DEFAULT_LOCAL_MCP_BASE_WORKING_DIR
)

MCP_BASE_WORKING_DIR = Path(DEFAULT_MCP_BASE_WORKING_DIR)

try:
    MCP_BASE_WORKING_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"MCP base working directory: {MCP_BASE_WORKING_DIR.resolve()}")
except Exception as e:
    logger.error(f"Could not create or access MCP base working directory {MCP_BASE_WORKING_DIR}: {e}")
    # Optionally: raise or exit if this is fatal
    # raise RuntimeError(f"Failed to initialize MCP working directory: {e}")

# --- Security: Shell Command Tools ---
ALLOW_ARBITRARY_SHELL_COMMANDS = True  # Set to False for extra safety, or use env var

logger.info("Configuration loaded.")
