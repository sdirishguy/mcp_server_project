"""
Audit logging system for the Model Context Protocol (MCP).
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
    @abstractmethod
    def log(
        self,
        event: AuditEventType | str,
        *,
        actor: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None: ...

    async def log_event(
        self,
        event: AuditEventType | str,
        *,
        actor: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.log(event, actor=actor, context=context)


class StdoutAuditLogger(AuditLogger):
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("audit")

    def log(
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
        same_file = any(
            isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None) == handler.baseFilename
            for h in self._logger.handlers
        )
        if not same_file:
            self._logger.addHandler(handler)

    def log(
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


_DEF_LOGGER: AuditLogger | None = None


def create_default_audit_logger(log_file: str | None = None) -> AuditLogger:
    path = log_file or os.getenv("AUDIT_LOG_FILE")
    return FileAuditLogger(path) if path else StdoutAuditLogger()


def get_audit_logger() -> AuditLogger:
    global _DEF_LOGGER
    if _DEF_LOGGER is None:
        _DEF_LOGGER = create_default_audit_logger()
    return _DEF_LOGGER
