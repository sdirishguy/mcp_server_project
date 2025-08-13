# app/settings.py
from __future__ import annotations

from typing import Any

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Logging & auth
    LOG_LEVEL: str = "INFO"
    ADMIN_USERNAME: str = Field(default="admin", description="Admin username")
    ADMIN_PASSWORD: str = Field(default="admin123", description="Admin password")

    # Server
    SERVER_PORT: int = 8000

    # MCP / adapters
    MCP_BASE_DIR: str = "./shared_host_folder"
    REST_ADAPTER_BASE_URL: AnyHttpUrl | None = None

    # CORS (comma-separated string OK: "http://a.com,http://b.com")
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v


settings = Settings()
