"""
Monitoring and observability module for the MCP Server Project.

This module provides Prometheus metrics collection, structured logging,
and performance monitoring capabilities.
"""

import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response

# Prometheus metrics
REQUEST_COUNT = Counter(
    "mcp_http_requests_total", "Total number of HTTP requests", ["method", "endpoint", "status"]
)

REQUEST_DURATION = Histogram(
    "mcp_http_request_duration_seconds", "HTTP request duration in seconds", ["method", "endpoint"]
)

ACTIVE_CONNECTIONS = Gauge("mcp_active_connections", "Number of active connections")

TOOL_EXECUTION_COUNT = Counter(
    "mcp_tool_executions_total", "Total number of tool executions", ["tool_name", "status"]
)

TOOL_EXECUTION_DURATION = Histogram(
    "mcp_tool_execution_duration_seconds", "Tool execution duration in seconds", ["tool_name"]
)

AUTHENTICATION_ATTEMPTS = Counter(
    "mcp_authentication_attempts_total", "Total number of authentication attempts", ["status"]
)

# Structured logging setup
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


class MonitoringMiddleware:
    """Middleware for collecting metrics and structured logging."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        method = scope["method"]
        path = scope["path"]

        # Increment active connections
        ACTIVE_CONNECTIONS.inc()

        # Create a custom send function to capture response status
        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                status = message["status"]
                REQUEST_COUNT.labels(method=method, endpoint=path, status=status).inc()

                # Log request with structured data
                logger.info(
                    "HTTP request",
                    method=method,
                    path=path,
                    status=status,
                    duration=time.time() - start_time,
                )

            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            # Log errors with structured data
            logger.error(
                "HTTP request error",
                method=method,
                path=path,
                error=str(e),
                duration=time.time() - start_time,
            )
            raise
        finally:
            # Record request duration
            duration = time.time() - start_time
            REQUEST_DURATION.labels(method=method, endpoint=path).observe(duration)

            # Decrement active connections
            ACTIVE_CONNECTIONS.dec()


@asynccontextmanager
async def tool_execution_monitor(tool_name: str) -> AsyncGenerator[None, None]:
    """Context manager for monitoring tool execution."""
    start_time = time.time()
    try:
        yield
        TOOL_EXECUTION_COUNT.labels(tool_name=tool_name, status="success").inc()
    except Exception as e:
        TOOL_EXECUTION_COUNT.labels(tool_name=tool_name, status="error").inc()
        logger.error("Tool execution error", tool_name=tool_name, error=str(e))
        raise
    finally:
        duration = time.time() - start_time
        TOOL_EXECUTION_DURATION.labels(tool_name=tool_name).observe(duration)


def record_auth_attempt(status: str) -> None:
    """Record authentication attempt."""
    AUTHENTICATION_ATTEMPTS.labels(status=status).inc()


async def metrics_endpoint(request: Request) -> Response:
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type="text/plain")


def get_health_metrics() -> dict[str, Any]:
    """Get health check metrics."""
    return {
        "active_connections": ACTIVE_CONNECTIONS._value.get(),
        "total_requests": REQUEST_COUNT._value.get(),
        "total_tool_executions": TOOL_EXECUTION_COUNT._value.get(),
        "total_auth_attempts": AUTHENTICATION_ATTEMPTS._value.get(),
    }
