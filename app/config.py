# app/config.py
import os
from pathlib import Path
import logging

from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_SERVER_PORT = 3000
SERVER_PORT = int(os.environ.get("MCP_SERVER_PORT", DEFAULT_SERVER_PORT))
logger.info(f"Server port configured to: {SERVER_PORT}")

DEFAULT_MCP_BASE_WORKING_DIR = "/app/host_data"
MCP_BASE_WORKING_DIR_STR = os.environ.get("MCP_BASE_WORKING_DIR", DEFAULT_MCP_BASE_WORKING_DIR)
MCP_BASE_WORKING_DIR = Path(MCP_BASE_WORKING_DIR_STR)

try:
    MCP_BASE_WORKING_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"MCP base working directory: {MCP_BASE_WORKING_DIR.resolve()}")
except Exception as e:
    logger.error(f"Could not create or access MCP base working directory {MCP_BASE_WORKING_DIR}: {e}")

# --- API Keys ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

ALLOW_ARBITRARY_SHELL_COMMANDS = True

logger.info("Configuration loaded.")
