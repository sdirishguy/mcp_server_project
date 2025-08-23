# app/mcp/security/audit/audit_logging.py
"""
Audit logging system for the Model Context Protocol (MCP).

Minimal, modern API:
    await audit_logger.log_event(
        AuditEventType.LOGIN,
        actor="username-or-id",
        context={"success": True, "ip": "1.2.3.4"},
    )
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from enum import Enum
from typing import Any

__all__ = [
    "AuditEventType",
    "AuditLogger",
    "StdoutAuditLogger",
    "FileAuditLogger",
    "create_default_audit_logger",
    "get_audit_logger",
]


class AuditEventType(str, Enum):
    LOGIN = "auth.login"
    LOGOUT = "auth.logout"
    ADAPTER_CREATE = "adapter.create"
    ADAPTER_FETCH = "adapter.fetch"
    TOOL_EXECUTE = "tool.execute"
    HTTP_REQUEST = "http.request"
    HTTP_RESPONSE = "http.response"
    ERROR = "error"


class AuditLogger(ABC):
    """Abstract audit logger interface."""

    @abstractmethod
    async def log_event(
        self,
        event: AuditEventType | str,
        *,
        actor: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None: ...


class StdoutAuditLogger(AuditLogger):
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("audit")

    async def log_event(
        self,
        event: AuditEventType | str,
        *,
        actor: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "ts": int(datetime.now(UTC).timestamp()),
            "event": str(event),
            "actor": actor or "system",
            "context": context or {},
        }
        self._logger.info("%s", payload)


class FileAuditLogger(AuditLogger):
    def __init__(self, log_file: str) -> None:
        self._logger = logging.getLogger("audit.file")
        self._logger.setLevel(logging.INFO)

        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter("%(message)s"))

        # avoid duplicate handlers for same file
        if not any(
            isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None) == handler.baseFilename
            for h in self._logger.handlers
        ):
            self._logger.addHandler(handler)

    async def log_event(
        self,
        event: AuditEventType | str,
        *,
        actor: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "ts": int(datetime.now(UTC).timestamp()),
            "event": str(event),
            "actor": actor or "system",
            "context": context or {},
        }
        self._logger.info("%s", payload)


# Factory / accessor

_DEF_LOGGER: AuditLogger | None = None


def create_default_audit_logger(log_file: str | None = None) -> AuditLogger:
    """Create and return the default audit logger.

    If a path (or AUDIT_LOG_FILE env) is provided, writes to that file; otherwise stdout.
    """
    file_path = log_file or os.getenv("AUDIT_LOG_FILE")
    if file_path:
        return FileAuditLogger(file_path)
    return StdoutAuditLogger()


def get_audit_logger() -> AuditLogger:
    global _DEF_LOGGER
    if _DEF_LOGGER is None:
        _DEF_LOGGER = create_default_audit_logger()
    return _DEF_LOGGER
