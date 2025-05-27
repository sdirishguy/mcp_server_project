# app/config.py
import os
from pathlib import Path
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Server Configuration ---
DEFAULT_SERVER_PORT = 3000
SERVER_PORT = int(os.environ.get("MCP_SERVER_PORT", DEFAULT_SERVER_PORT))
logger.info(f"Server port configured to: {SERVER_PORT}")

# --- Tools Configuration ---
# Base working directory within the container for file system tools.
# This path can be a mount point for a host volume (e.g., -v /mnt/wsl/my_projects:/app/projects_data).
# If the env var is not set, it defaults to a 'data' subdirectory in the app's working dir.
DEFAULT_MCP_BASE_WORKING_DIR = "/app/host_data" # Defaulting to a clearly named directory for mounted data
MCP_BASE_WORKING_DIR_STR = os.environ.get("MCP_BASE_WORKING_DIR", DEFAULT_MCP_BASE_WORKING_DIR)
MCP_BASE_WORKING_DIR = Path(MCP_BASE_WORKING_DIR_STR)

# Ensure the base working directory exists if it's inside the container's default paths
# If MCP_BASE_WORKING_DIR points to a mount that doesn't exist from the host,
# Docker will create it as a directory owned by root if it's a new named volume,
# or it might fail if it's a host path that doesn't exist and docker can't create it.
# Here, we ensure the default path *inside the container* is created if no env var is set.
# If a volume is mounted to MCP_BASE_WORKING_DIR, this mkdir may operate on the mount.
try:
    MCP_BASE_WORKING_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"MCP base working directory: {MCP_BASE_WORKING_DIR.resolve()}")
except Exception as e:
    logger.error(f"Could not create or access MCP base working directory {MCP_BASE_WORKING_DIR}: {e}")
    # Depending on severity, you might want to exit or handle this more gracefully.
    # For now, we log and continue; tools will fail if the path is unusable.

# --- Security Configuration ---
# For execute_shell_command, consider if you want to restrict available commands
# or add other security layers in a production environment.
# For this educational build, we'll allow commands as passed.
ALLOW_ARBITRARY_SHELL_COMMANDS = True # Or read from an environment variable

logger.info("Configuration loaded.")