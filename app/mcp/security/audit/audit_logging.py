"""
Audit logging system for the Model Context Protocol (MCP).

This module provides interfaces and implementations for recording
security-relevant events for compliance and forensics.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

__all__ = [
    "AuditEventType",
    "AuditEventOutcome",
    "AuditEvent",
    "AuditLogger",
    "StdoutAuditLogger",
    "FileAuditLogger",
    "create_default_audit_logger",
    "get_audit_logger",
]

# -----------------------------------------------------------------------------
# Types
# -----------------------------------------------------------------------------


class AuditEventType(str, Enum):
    LOGIN = "auth.login"
    LOGOUT = "auth.logout"
    ADAPTER_CREATE = "adapter.create"
    ADAPTER_FETCH = "adapter.fetch"
    TOOL_EXECUTE = "tool.execute"
    HTTP_REQUEST = "http.request"
    HTTP_RESPONSE = "http.response"
    ERROR = "error"


class AuditEventOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    


@dataclass(init=False)
class AuditEvent:
    """Back-compat container used by existing callers/tests.

    Accepts new `event_type=` or legacy `event_action=`.
    Maps `user_id`/`username` to `actor`.
    Any extra/unknown kwargs are merged into `context`.
    """
    event_type: AuditEventType | str
    actor: str | None
    outcome: AuditEventOutcome | str | None
    context: dict[str, Any] | None

    def __init__(
        self,
        *,
        event_type: AuditEventType | str | None = None,
        event_action: AuditEventType | str | None = None,  # legacy
        actor: str | None = None,
        user_id: str | None = None,                        # legacy -> actor
        username: str | None = None,                       # legacy -> actor
        outcome: AuditEventOutcome | str | None = None,
        context: dict[str, Any] | None = None,
        details: dict[str, Any] | str | None = None,       # legacy, merged into context
        **extra: Any,                                      # capture any other legacy fields
    ) -> None:
        self.event_type = event_type or event_action or AuditEventType.ERROR
        self.actor = actor or user_id or username

        ctx: dict[str, Any] = {}
        if context:
            ctx.update(context)
        if details is not None:
            # keep structure if dict; otherwise store as string
            ctx.setdefault("details", details if isinstance(details, dict) else str(details))
        # fold any unknown legacy kwargs into context (without clobbering)
        for k, v in extra.items():
            ctx.setdefault(k, v)

        self.outcome = outcome
        self.context = ctx or None

    def to_log_args(self) -> tuple[str, str | None, dict[str, Any] | None]:
        ctx = dict(self.context or {})
        if self.outcome is not None:
            ctx.setdefault("outcome", str(self.outcome))
        return (str(self.event_type), self.actor, ctx or None)



# -----------------------------------------------------------------------------
# Interface
# -----------------------------------------------------------------------------


class AuditLogger(ABC):
    """Abstract audit logger interface."""

    @abstractmethod
    def log(
        self,
        event: AuditEventType | str,
        *,
        actor: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:  # noqa: D401
        ...

    async def log_event(
        self,
        event: AuditEvent | AuditEventType | str,
        *,
        actor: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Back-compat async helper so callers can `await audit_logger.log_event(...)`."""
        if isinstance(event, AuditEvent):
            ev, ac, ctx = event.to_log_args()
            self.log(ev, actor=ac, context=ctx)
        else:
            self.log(event, actor=actor, context=context)


# -----------------------------------------------------------------------------
# Implementations
# -----------------------------------------------------------------------------


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
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)

        # Avoid duplicate handlers for the same file
        same_file = any(
            isinstance(h, logging.FileHandler)
            and getattr(h, "baseFilename", None) == handler.baseFilename
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


# -----------------------------------------------------------------------------
# Factory / accessor
# -----------------------------------------------------------------------------

_DEF_LOGGER: AuditLogger | None = None


def create_default_audit_logger(log_file: str | None = None) -> AuditLogger:
    """Create and return the default audit logger.

    If `log_file` is provided, use a file-backed logger.
    Else, check AUDIT_LOG_FILE env var. Otherwise, stdout.
    """
    path = log_file or os.getenv("AUDIT_LOG_FILE")
    if path:
        return FileAuditLogger(path)
    return StdoutAuditLogger()


def get_audit_logger() -> AuditLogger:
    global _DEF_LOGGER
    if _DEF_LOGGER is None:
        _DEF_LOGGER = create_default_audit_logger()
    return _DEF_LOGGER


# -----------------------------------------------------------------------------
# Legacy constant names to satisfy older code (back-compat shims)
# -----------------------------------------------------------------------------

# Some older call sites refer to these; map them to closest modern events.
AuditEventType.AUTHENTICATION = AuditEventType.LOGIN  # type: ignore[attr-defined]
AuditEventType.AUTHORIZATION = AuditEventType.LOGIN   # type: ignore[attr-defined]
