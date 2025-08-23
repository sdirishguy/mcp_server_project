"""
Unified configuration for the MCP Server Project.

This module uses a single Pydantic settings class to load all configuration
from environment variables and `.env` files.  It consolidates variables
previously scattered between `settings.py` and the old `config.py` so that
there is one source of truth.  It also sets up a module‑level logger and
ensures the base working directory exists.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralised application settings loaded from environment variables.

    All configuration for the server should be defined here.  Defaults are
    provided for development, and values can be overridden via environment
    variables or a `.env` file.  Unknown settings are ignored.
    """

    # Pydantic settings configuration: load from `.env` and ignore unknown keys
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Logging & authentication
    LOG_LEVEL: str = "INFO"
    ADMIN_USERNAME: str = Field(default="admin", description="Admin username")
    ADMIN_PASSWORD: str = Field(default="admin123", description="Admin password")

    # Server configuration
    SERVER_PORT: int = 8000

    # MCP / adapters
    MCP_BASE_WORKING_DIR: str = "./shared_host_folder"
    REST_ADAPTER_BASE_URL: AnyHttpUrl | None = None

    # CORS (comma‑separated string also supported via env var)
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://example.com",
    ]

    # Environment (development|staging|production)
    ENVIRONMENT: str = "development"

    # Shell execution controls
    ALLOW_ARBITRARY_SHELL_COMMANDS: bool = False
    SHELL_ALLOWLIST: list[str] = []

    # JWT authentication
    JWT_SECRET: str = Field(default="change-me", description="Secret key used to sign JWT tokens")
    JWT_EXPIRY_MINUTES: int = Field(default=60, description="Number of minutes before issued JWT tokens expire")

    # API keys for external LLM services
    OPENAI_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_cors(cls, v: Any) -> list[str]:
        """Allow CORS origins to be provided as a comma‑separated string."""
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v


# Instantiate the settings at import time
settings = Settings()


# Configure a module‑level logger using the configured log level
logger = logging.getLogger(__name__)

log_level = settings.LOG_LEVEL.upper()
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger.setLevel(log_level)


# Ensure the base working directory exists; resolve the path for consistency
_base_path = Path(settings.MCP_BASE_WORKING_DIR).resolve()
try:
    _base_path.mkdir(parents=True, exist_ok=True)
except OSError as exc:
    logger.error(
        "Could not create or access MCP base working directory %s: %s",
        _base_path,
        exc,
    )

# If running in production, disable arbitrary shell commands unless explicitly enabled
if settings.ENVIRONMENT.lower() == "production" and os.getenv("ALLOW_ARBITRARY_SHELL_COMMANDS", "").lower() != "true":
    settings.ALLOW_ARBITRARY_SHELL_COMMANDS = False
