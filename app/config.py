"""
Configuration module for the MCP Server Project.

This module handles environment variables, logging setup, API keys,
and security settings for the Model Context Protocol server.
"""

# app/config.py
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_SERVER_PORT = 3000
SERVER_PORT = int(os.environ.get("MCP_SERVER_PORT", DEFAULT_SERVER_PORT))
logger.info("Server port configured to: %s", SERVER_PORT)

# Base working directory for the MCP server (for sandboxing filesystem ops)
DEFAULT_BASE_DIR = Path(os.environ.get("MCP_BASE_WORKING_DIR", "./shared_host_folder")).resolve()
MCP_BASE_WORKING_DIR = DEFAULT_BASE_DIR

try:
    MCP_BASE_WORKING_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("MCP base working directory: %s", MCP_BASE_WORKING_DIR.resolve())
except OSError as e:
    logger.error(
        "Could not create or access MCP base working directory %s: %s", MCP_BASE_WORKING_DIR, e
    )

# --- API Keys ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- Added by hardening patch ---
# development|staging|production
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
ALLOWED_CORS_ORIGINS = [
    s.strip() for s in os.getenv("ALLOWED_CORS_ORIGINS", "").split(",") if s.strip()
]
if ENVIRONMENT == "production" and not ALLOWED_CORS_ORIGINS:
    logger.warning("No ALLOWED_CORS_ORIGINS set in production. " "CORS will be very restrictive.")

# Shell execution controls
# Default OFF unless explicitly enabled.
ALLOW_ARBITRARY_SHELL_COMMANDS = (
    os.getenv("ALLOW_ARBITRARY_SHELL_COMMANDS", "false").lower() == "true"
)
SHELL_ALLOWLIST = [s.strip() for s in os.getenv("SHELL_ALLOWLIST", "").split(",") if s.strip()]

if ENVIRONMENT == "production":
    # In prod, force-disable arbitrary shell unless explicitly overridden.
    if os.getenv("ALLOW_ARBITRARY_SHELL_COMMANDS", "").lower() != "true":
        ALLOW_ARBITRARY_SHELL_COMMANDS = False

logger.info("Configuration loaded.")
