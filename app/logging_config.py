"""
JSON logging and Request ID helpers for the MCP Server.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp  # <-- add this


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "path", "method", "status_code", "elapsed_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class RequestIDMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, header_name: str = "X-Request-ID") -> None:
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        rid = request.headers.get(self.header_name) or str(uuid.uuid4())
        request.state.request_id = rid

        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception:
            response = Response("Internal Server Error", status_code=500)
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0

        response.headers[self.header_name] = rid

        logger = logging.getLogger("app.access")
        extra = {
            "request_id": rid,
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "elapsed_ms": round(elapsed_ms, 2),
        }
        logger.info("request", extra=extra)
        return response


def configure_json_logging(level: str = "INFO") -> None:
    """Configure root logger to emit structured JSON lines."""
    root = logging.getLogger()
    root.setLevel(level.upper())

    # Remove any pre-existing handlers (uvicorn adds its own)
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)

    # Quiet noisy loggers a bit; inherit our root level/format
    for noisy in ("uvicorn.access", "uvicorn.error", "asyncio"):
        logging.getLogger(noisy).setLevel(level.upper())
