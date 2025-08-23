"""
Audit logging system for the Model Context Protocol (MCP).

This module provides interfaces and implementations for recording
security-relevant events for compliance and forensics.
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
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
        """Initialize an audit event.

        Args:
            event_type: Type of event
            event_action: Specific action being performed
            outcome: Outcome of the event
            user_id: ID of the user performing the action
            resource_type: Type of resource being accessed
            resource_id: ID of the resource being accessed
            details: Additional details about the event
            timestamp: Time of the event
        """
        self.event_type = event_type
        self.event_action = event_action
        self.outcome = outcome
        self.user_id = user_id
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.details = details or {}
        self.timestamp = timestamp or datetime.utcnow()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dict[str, Any]: Dictionary representation of the event
        """
        return {
            "event_type": self.event_type,
            "event_action": self.event_action,
            "outcome": self.outcome,
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
        """Log an audit event.

        Args:
            event: The audit event to log
        """
        raise NotImplementedError


class FileAuditLogger(AuditLogger):
    """Audit logger that writes to a file."""

    def __init__(self, log_file: str):
        """Initialize the file audit logger.

        Args:
            log_file: Path to the log file
        """
        self._log_file = log_file
        self._logger = logging.getLogger("mcp.audit")

        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)

        # Configure file handler
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)

        self._logger.addHandler(handler)
        self._logger.setLevel(logging.INFO)

    async def log_event(self, event: AuditEvent) -> None:
        """Log an audit event to file.

        Args:
            event: The audit event to log
        """
        event_json = json.dumps(event.to_dict())
        self._logger.info(event_json)


class ConsoleAuditLogger(AuditLogger):
    """Audit logger that writes to the console."""

    def __init__(self):
        """Initialize the console audit logger."""
        self._logger = logging.getLogger("mcp.audit.console")

        # Configure console handler
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)

        self._logger.addHandler(handler)
        self._logger.setLevel(logging.INFO)

    async def log_event(self, event: AuditEvent) -> None:
        """Log an audit event to console.

        Args:
            event: The audit event to log
        """
        # Build compact human-readable summary; full JSON is handled by FileAuditLogger.
        log_message = f"{event.event_type}:{event.event_action} - Outcome: {event.outcome}"

        if event.user_id:
            log_message += f" - User: {event.user_id}"

        if event.resource_type and event.resource_id:
            log_message += f" - Resource: {event.resource_type}:{event.resource_id}"

        # Log at appropriate level based on outcome
        if event.outcome == AuditEventOutcome.SUCCESS:
            self._logger.info(log_message)
        elif event.outcome == AuditEventOutcome.FAILURE:
            self._logger.warning(log_message)
        else:  # ERROR
            self._logger.error(log_message)


class MultiAuditLogger(AuditLogger):
    """Audit logger that forwards events to multiple loggers."""

    def __init__(self, loggers: list[AuditLogger]):
        """Initialize the multi audit logger.

        Args:
            loggers: List of audit loggers to use
        """
        self._loggers = loggers

    async def log_event(self, event: AuditEvent) -> None:
        """Log an audit event to all loggers.

        Args:
            event: The audit event to log
        """
        for logger in self._loggers:
            await logger.log_event(event)

    def add_logger(self, logger: AuditLogger) -> None:
        """Add a logger to the multi logger.

        Args:
            logger: The audit logger to add
        """
        self._loggers.append(logger)


def create_default_audit_logger(log_file: str = "audit.log") -> AuditLogger:
    """Create a default audit logger that logs to both file and console.

    Args:
        log_file: Path to the log file

    Returns:
        AuditLogger: The default audit logger
    """
    return MultiAuditLogger([FileAuditLogger(log_file), ConsoleAuditLogger()])
