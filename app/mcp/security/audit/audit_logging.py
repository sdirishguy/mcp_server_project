"""
Audit logging system for the Model Context Protocol (MCP).

This module provides interfaces and implementations for recording
security-relevant events for compliance and forensics.
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, UTC
from enum import Enum
from typing import Any


class AuditEventType(str, Enum):
    """Types of audit events."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    CONFIGURATION = "configuration"
    SYSTEM = "system"


class AuditEventOutcome(str, Enum):
    """Possible outcomes of audit events."""

    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"


class AuditEvent:
    """Represents an audit event."""

    def __init__(
        self,
        event_type: AuditEventType,
        event_action: str,
        outcome: AuditEventOutcome,
        user_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ):
        """Initialize an audit event."""
        self.event_type = event_type
        self.event_action = event_action
        self.outcome = outcome
        self.user_id = user_id
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.details = details or {}
        # Use timezone-aware UTC timestamp (fixes deprecation warning)
        self.timestamp = timestamp or datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "event_type": self.event_type.value,
            "event_action": self.event_action,
            "outcome": self.outcome.value,
            "user_id": self.user_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


class AuditLogger(ABC):
    """Interface for audit loggers."""

    @abstractmethod
    async def log_event(self, event: AuditEvent) -> None:
        """Log an audit event."""
        raise NotImplementedError


class FileAuditLogger(AuditLogger):
    """Audit logger that writes to a file."""

    def __init__(self, log_file: str):
        self._log_file = log_file
        self._logger = logging.getLogger("mcp.audit")

        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)

        # Configure file handler
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter("%(message)s")
        handler.setForm
