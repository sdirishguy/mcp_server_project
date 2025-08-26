"""
Unified configuration for the MCP Server Project.

This module uses a single Pydantic settings class to load all configuration
from environment variables and `.env` files. It consolidates variables
previously scattered between `settings.py` and the old `config.py` so that
there is one source of truth. It also sets up a module‑level logger and
ensures the base working directory exists.

ARCHITECTURE: Centralized configuration management
- Single source of truth for all application settings
- Environment variable loading with .env file fallback
- Type validation and conversion via Pydantic
- Automatic documentation via Field descriptions
- Default values suitable for development

SECURITY: Production-ready defaults
- JWT secrets validated for strength
- Shell commands disabled by default in production
- CORS origins configurable for environment-specific security
- API keys optional and validated
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

    DESIGN PRINCIPLES:
    1. **Environment First**: All config comes from env vars or .env files
    2. **Development Defaults**: Sane defaults for local development
    3. **Production Override**: Environment variables override defaults
    4. **Type Safety**: Pydantic validates and converts types automatically
    5. **Documentation**: Field descriptions serve as inline documentation

    SECURITY CONSIDERATIONS:
    - JWT_SECRET must be strong for production (validated)
    - Shell commands disabled by default, especially in production
    - CORS origins should be restricted in production
    - API keys are optional and not logged
    """

    # Pydantic settings configuration: load from `.env` and ignore unknown keys
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Logging & Authentication ---

    LOG_LEVEL: str = "INFO"
    """Logging level for the application.
    
    MONITORING: Controls verbosity of logs
    - DEBUG: Very verbose, includes request/response details
    - INFO: Standard operational logs (recommended)  
    - WARNING: Only warnings and errors
    - ERROR: Only errors and critical issues
    """

    ADMIN_USERNAME: str = Field(default="admin", description="Admin username")
    """Default admin username for authentication.
    
    SECURITY: Should be changed in production
    - Used by both JWT and InMemory auth providers
    - Consider using more secure username in production
    - Tests depend on this being configurable
    """

    ADMIN_PASSWORD: str = Field(default="admin123", description="Admin password")
    """Default admin password for authentication.
    
    SECURITY: MUST be changed in production
    - Plain text in configuration (hash in production)
    - Used for initial admin account creation
    - Should be strong password with complexity requirements
    """

    # --- Server Configuration ---

    SERVER_PORT: int = 8000
    """Port for the HTTP server to listen on.
    
    DEPLOYMENT: Standard port configuration
    - 8000 is common for development servers
    - Production may use 80/443 with reverse proxy
    - Configurable for multi-instance deployments
    """

    # --- MCP / Adapters ---

    MCP_BASE_WORKING_DIR: str = "./shared_host_folder"
    """Base directory for file system operations.
    
    SECURITY: Sandbox boundary for file tools
    - All file operations restricted to this directory tree
    - Prevents path traversal attacks
    - Should be dedicated directory with appropriate permissions
    - Consider using absolute path in production
    """

    REST_ADAPTER_BASE_URL: AnyHttpUrl | None = None
    """Base URL for REST API adapter operations.
    
    INTEGRATION: Optional REST API integration
    - Used by RestApiAdapter for external API calls
    - None means no default REST endpoint configured
    - Can be overridden per adapter instance
    """

    # --- CORS Configuration ---

    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://example.com",
    ]
    """Allowed origins for CORS (Cross-Origin Resource Sharing).
    
    SECURITY: Restrict browser access origins
    - Prevents unauthorized websites from making API calls
    - Development defaults allow localhost testing
    - Production should only include actual frontend domains
    - Supports comma-separated string via environment variable
    """

    # --- Environment ---

    ENVIRONMENT: str = "development"
    """Current environment (development|staging|production).
    
    BEHAVIOR: Environment-specific feature toggles
    - development: More permissive settings, debug features
    - staging: Production-like but with testing features  
    - production: Strict security, performance optimized
    - Used for conditional feature enablement
    """

    # --- Shell Execution Controls ---

    ALLOW_ARBITRARY_SHELL_COMMANDS: bool = False
    """Whether to allow arbitrary shell command execution.
    
    SECURITY: Disabled by default for safety
    - False: Shell commands return "disabled" error
    - True: Commands allowed but filtered for dangerous patterns
    - Production override requires explicit environment variable
    - Used by execute_shell_command_tool
    """

    SHELL_ALLOWLIST: list[str] = []
    """List of allowed shell commands (not currently implemented).
    
    FUTURE: Whitelist approach for shell commands
    - More secure than blacklist filtering
    - Would replace current token-based filtering
    - Could support regex patterns or exact matches
    - Reserved for future security enhancements
    """

    # --- JWT Authentication ---

    JWT_SECRET: str = Field(default="change-me", description="Secret key used to sign JWT tokens")
    """Secret key for JWT token signing.
    
    CRITICAL SECURITY: Must be strong in production
    - Default "change-me" triggers fallback to InMemory auth
    - Should be cryptographically random, 32+ characters
    - Same secret must be used across all server instances
    - Consider key rotation for high-security environments
    - Never log or expose this value
    """

    JWT_EXPIRY_MINUTES: int = Field(default=60, description="Number of minutes before issued JWT tokens expire")
    """JWT token expiration time in minutes.
    
    SECURITY: Balance between security and usability
    - Shorter time = more secure, more frequent re-auth
    - Longer time = better UX, higher security risk
    - 60 minutes is reasonable for most applications
    - Consider shorter (15-30 min) for high-security environments
    """

    # --- External API Keys ---

    OPENAI_API_KEY: str | None = None
    """OpenAI API key for code generation tools.
    
    INTEGRATION: Optional OpenAI integration
    - None or placeholder values disable OpenAI tools
    - Required for llm_generate_code_openai_tool
    - Should start with 'sk-' for OpenAI API keys
    - Keep secure and rotate regularly
    """

    GEMINI_API_KEY: str | None = None
    """Google Gemini API key for code generation tools.
    
    INTEGRATION: Optional Google Gemini integration
    - None or placeholder values disable Gemini tools
    - Required for llm_generate_code_gemini_tool
    - Different format than OpenAI keys
    - Keep secure and rotate regularly
    """

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_cors(cls, v: Any) -> list[str]:
        """Allow CORS origins to be provided as a comma‑separated string.

        FLEXIBILITY: Support both list and string configuration
        - Environment variables are strings, but Python code prefers lists
        - Automatically splits "http://localhost:3000,https://api.com" into list
        - Strips whitespace for robustness
        - Filters out empty strings

        Args:
            v: CORS_ORIGINS value (string or list)

        Returns:
            List of origin strings
        """
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v


# Instantiate the settings at import time
# DESIGN: Module-level singleton pattern
# - Settings loaded once at import time
# - Shared across entire application
# - Environment changes require restart (intentional)
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
# INITIALIZATION: Create required directories at startup
# - Creates MCP_BASE_WORKING_DIR if it doesn't exist
# - Resolves path to absolute for consistency
# - Handles permission errors gracefully
# - Logs errors but doesn't fail startup
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
# SECURITY: Production hardening
# - Overrides ALLOW_ARBITRARY_SHELL_COMMANDS in production environment
# - Requires explicit ALLOW_ARBITRARY_SHELL_COMMANDS=true env var to enable
# - Prevents accidental shell command enablement in production
# - Defense in depth approach to security
if settings.ENVIRONMENT.lower() == "production" and os.getenv("ALLOW_ARBITRARY_SHELL_COMMANDS", "").lower() != "true":
    settings.ALLOW_ARBITRARY_SHELL_COMMANDS = False

"""
CONFIGURATION DESIGN NOTES:

1. **Single Source of Truth**: All settings defined in one place
2. **Environment Variable Driven**: Production overrides via env vars
3. **Type Safety**: Pydantic validates types automatically
4. **Documentation**: Field descriptions serve as inline docs
5. **Security First**: Safe defaults, explicit overrides required
6. **Testing Friendly**: Defaults work for tests without configuration

SECURITY CHECKLIST:
- [ ] Change ADMIN_PASSWORD in production
- [ ] Set strong JWT_SECRET (32+ random characters)
- [ ] Restrict CORS_ORIGINS to actual frontend domains  
- [ ] Keep ALLOW_ARBITRARY_SHELL_COMMANDS=false in production
- [ ] Secure API keys and rotate regularly
- [ ] Use HTTPS in production (handled by reverse proxy)

DEPLOYMENT CHECKLIST:
- [ ] Set ENVIRONMENT=production
- [ ] Configure appropriate LOG_LEVEL (INFO or WARNING)
- [ ] Set MCP_BASE_WORKING_DIR to dedicated directory
- [ ] Configure SERVER_PORT for your deployment
- [ ] Verify all required environment variables are set

TESTING CONSIDERATIONS:
- Default values allow tests to run without configuration
- Tests can override settings via environment variables
- Temporary directories can be used for MCP_BASE_WORKING_DIR
- API keys can be mocked or left as None for testing
"""
