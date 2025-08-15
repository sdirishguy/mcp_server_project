"""
Main module for the MCP Server Project.

This module sets up the FastAPI/Starlette ASGI application with authentication,
authorization, audit logging, and MCP tool routing. It provides secure HTTP
endpoints for Model Context Protocol operations.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, TypedDict, cast

from fastmcp import FastMCP
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

# SecurityMiddleware not available in current Starlette version
# We'll implement security headers manually
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from app.docs_app import app as docs_asgi_app
from app.logging_config import RequestIDMiddleware, configure_json_logging
from app.mcp.adapters.api.rest_api_adapter import RestApiAdapter
from app.mcp.adapters.database.postgres_adapter import PostgreSQLAdapter
from app.mcp.cache.memory.in_memory_cache import CacheManager, InMemoryCache
from app.mcp.core.adapter import AdapterManager, AdapterRegistry
from app.mcp.security.audit.audit_logging import (
    AuditEvent,
    AuditEventOutcome,
    AuditEventType,
    create_default_audit_logger,
)
from app.mcp.security.auth.authentication import AuthenticationManager, InMemoryAuthProvider
from app.mcp.security.auth.authorization import (
    Action,
    AuthorizationManager,
    ResourceType,
    create_admin_role,
)
from app.monitoring import (
    MonitoringMiddleware,
    metrics_endpoint,
    record_auth_attempt,
)
from app.settings import settings
from app.tools import ALL_TOOLS

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)


# ----- Auth models (simplified for brevity here) -----


class User:
    """Simple user model for authentication state."""

    def __init__(
        self,
        user_id: str,
        roles: list[str] | None = None,
        permissions: list[str] | None = None,
    ) -> None:
        """Initialize user with ID, roles, and permissions."""
        self.user_id = user_id
        self.roles = roles or []
        self.permissions = permissions or []


# --- MCP component setup ---


async def setup_mcp() -> dict[str, Any]:
    """Set up MCP components including auth, audit, cache, and adapters."""
    auth_manager = AuthenticationManager()
    auth_provider = InMemoryAuthProvider()
    # Bootstrap creds from .env via Settings
    auth_provider.add_user(settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD, roles=["admin"])
    auth_manager.register_provider("local", auth_provider)

    authz_manager = AuthorizationManager()
    authz_manager.add_role(create_admin_role())

    audit_log_file = os.getenv("AUDIT_LOG_FILE", "audit.log")
    audit_logger = create_default_audit_logger(audit_log_file)

    l1_cache: InMemoryCache = InMemoryCache(max_size=1000)
    cache_manager = CacheManager(l1_cache)

    registry = AdapterRegistry()
    registry.register("postgres", PostgreSQLAdapter)
    registry.register("rest_api", RestApiAdapter)
    adapter_manager = AdapterManager(registry)

    return {
        "auth_manager": auth_manager,
        "authz_manager": authz_manager,
        "audit_logger": audit_logger,
        "cache_manager": cache_manager,
        "adapter_manager": adapter_manager,
    }


# ------------------- Route handlers -------------------


@limiter.limit("5 per minute")
async def login(request: Request) -> JSONResponse:
    """Handle user login with credential validation and audit logging."""
    if not hasattr(request.app.state, "mcp_components"):
        return JSONResponse({"error": "MCP Server not ready"}, status_code=503)
    mcp_components = request.app.state.mcp_components
    try:
        credentials = await request.json()
        auth_result = await mcp_components["auth_manager"].authenticate(
            provider_id="local",
            credentials=credentials,
        )
        if auth_result.authenticated:
            record_auth_attempt("success")
            await mcp_components["audit_logger"].log_event(
                AuditEvent(
                    event_type=AuditEventType.AUTHENTICATION,
                    event_action="login",
                    outcome=AuditEventOutcome.SUCCESS,
                    user_id=auth_result.user_id,
                    details={"provider": "local"},
                )
            )
            return JSONResponse(
                {
                    "authenticated": True,
                    "user_id": auth_result.user_id,
                    "token": auth_result.token,
                    "roles": auth_result.roles,
                    "expires_at": auth_result.expires_at,
                }
            )
        else:
            record_auth_attempt("failure")
            await mcp_components["audit_logger"].log_event(
                AuditEvent(
                    event_type=AuditEventType.AUTHENTICATION,
                    event_action="login",
                    outcome=AuditEventOutcome.FAILURE,
                    details={"provider": "local"},
                )
            )
            return JSONResponse(
                {"authenticated": False, "error": "Invalid credentials"},
                status_code=401,
            )
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.exception("Login failed")
        return JSONResponse({"error": f"Login failed: {str(e)}"}, status_code=500)


async def create_adapter(request: Request) -> JSONResponse:
    """Create a new adapter instance with authorization checks."""
    if not hasattr(request.app.state, "mcp_components"):
        return JSONResponse({"error": "MCP Server not ready"}, status_code=503)
    mcp_components = request.app.state.mcp_components
    adapter_type = request.path_params["adapter_type"]
    try:
        user = request.state.user
        has_permission = mcp_components["authz_manager"].check_permission(
            roles=user.roles or [],
            permissions=user.permissions or [],
            resource_type=ResourceType.ADAPTER,
            resource_id=adapter_type,
            action=Action.CREATE,
        )
        if not has_permission:
            await mcp_components["audit_logger"].log_event(
                AuditEvent(
                    event_type=AuditEventType.AUTHORIZATION,
                    event_action="create_adapter",
                    outcome=AuditEventOutcome.FAILURE,
                    user_id=user.user_id,
                    resource_type="adapter",
                    resource_id=adapter_type,
                    details={"action": "create"},
                )
            )
            return JSONResponse({"message": "Forbidden"}, status_code=403)

        body = await request.json()

        # Create adapter instance using the adapter manager
        import uuid

        instance_id = str(uuid.uuid4())
        await mcp_components["adapter_manager"].create_adapter(
            adapter_id=adapter_type,
            instance_id=instance_id,
            config=body,
        )

        await mcp_components["audit_logger"].log_event(
            AuditEvent(
                event_type=AuditEventType.AUTHORIZATION,
                event_action="create_adapter",
                outcome=AuditEventOutcome.SUCCESS,
                user_id=user.user_id,
                resource_type="adapter",
                resource_id=adapter_type,
                details={"instance_id": instance_id, "config": body},
            )
        )

        return JSONResponse(
            {
                "message": "Adapter created",
                "type": adapter_type,
                "instance_id": instance_id,
                "config": body,
            }
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.exception("Adapter creation failed")
        return JSONResponse({"message": f"Adapter creation failed: {str(e)}"}, status_code=500)


async def execute_request(request: Request) -> JSONResponse:
    """Execute a request on an adapter instance."""
    if not hasattr(request.app.state, "mcp_components"):
        return JSONResponse({"error": "MCP Server not ready"}, status_code=503)
    mcp_components = request.app.state.mcp_components
    try:
        body = await request.json()
        instance_id = request.path_params["instance_id"]

        # Execute request using the adapter manager
        from app.mcp.core.adapter import DataRequest

        data_request = DataRequest(
            query=f"{body.get('method', 'GET')} {body.get('path', '/')}",
            parameters={
                "method": body.get("method", "GET"),
                "path": body.get("path", "/"),
                "params": body.get("params", {}),
                "headers": body.get("headers", {}),
                "body": body.get("body"),
            },
            context={},  # default empty context
            max_results=100,  # sane default
            timeout_ms=30000,  # 30s
        )

        response = await mcp_components["adapter_manager"].execute_request(
            instance_id,
            data_request,
        )

        return JSONResponse(
            {
                "message": "Executed",
                "instance_id": instance_id,
                "status_code": response.status_code,
                "data": response.data,
                "metadata": response.metadata,
                "error": response.error,
            }
        )
    except KeyError as e:
        return JSONResponse(
            {"message": f"Adapter instance not found: {str(e)}"},
            status_code=404,
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.exception("Execute failed")
        return JSONResponse({"message": f"Execute failed: {str(e)}"}, status_code=500)


async def protected_route(request: Request) -> JSONResponse:
    """Protected route that requires authentication."""
    user = getattr(request.state, "user", None)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    return JSONResponse(
        {"message": "This is a protected route", "user": user.user_id, "roles": user.roles}
    )


async def whoami(request: Request) -> JSONResponse:
    """Return server status and available auth providers."""
    if not hasattr(request.app.state, "mcp_components"):
        return JSONResponse({"error": "MCP Server not ready"}, status_code=503)
    mcp_components = request.app.state.mcp_components
    return JSONResponse(
        {
            "message": "MCP Server is running",
            "providers": mcp_components["auth_manager"].get_provider_ids(),
        }
    )


async def health(_request: Request) -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({"status": "ok", "message": "MCP Server is running!"})


# --- FastMCP app and tools ---


class ToolEntry(TypedDict):
    name: str
    description: str
    handler: Callable[..., Awaitable[dict[str, Any]]]


mcp: FastMCP = FastMCP("MCP Server", stateless_http=True)
tools_typed: list[ToolEntry] = cast("list[ToolEntry]", ALL_TOOLS)
for tool in tools_typed:
    mcp.tool(name=tool["name"], description=tool["description"])(tool["handler"])
logger.info("Registered %d tools with FastMCP.", len(tools_typed))
mcp_app = mcp.http_app(path="/mcp.json/")


# ------------------- Routing -------------------


routes = [
    Mount("/docs", app=docs_asgi_app),
    Route("/metrics", metrics_endpoint),
    Route("/api/auth/login", login, methods=["POST"]),
    Route("/api/adapters/{adapter_type}", create_adapter, methods=["POST"]),
    Route("/api/adapters/{instance_id}/execute", execute_request, methods=["POST"]),
    Route("/api/protected", protected_route),
    Route("/whoami", whoami),
    Route("/health", health),
    Mount("/mcp", app=mcp_app),
    Mount("/api", app=mcp_app),  # exposes /api/mcp.json/
]


# --- Lifespan handler ---


@asynccontextmanager
async def app_lifespan(starlette_app: Starlette) -> AsyncIterator[None]:
    # Ensure JSON logging inside worker/reloader processes
    configure_json_logging(settings.LOG_LEVEL)

    if hasattr(mcp_app, "lifespan") and mcp_app.lifespan:
        async with mcp_app.lifespan(starlette_app):
            starlette_app.state.mcp_components = await setup_mcp()
            logger.info("MCP components initialized and available via app.state.mcp_components")
            yield
    else:
        starlette_app.state.mcp_components = await setup_mcp()
        logger.info("MCP components initialized and available via app.state.mcp_components")
        yield


# ---- Middleware ----


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware for adding security headers to all responses."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Add security headers to the response."""
        response = await call_next(request)

        # Add security headers
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'"
        )

        return response


class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication middleware for validating bearer tokens."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Handle authentication for incoming requests."""
        public_prefixes = (
            "/api/auth/login",
            "/health",
            "/whoami",
            "/metrics",  # Prometheus metrics endpoint
            "/mcp/mcp.json",  # MCP JSON endpoint (SSE)
            "/api/mcp.json",
            "/docs",  # Swagger UI + openapi.json + assets
        )

        # Allow OPTIONS requests and public endpoints to pass through
        if request.method == "OPTIONS" or any(
            request.url.path.startswith(p) for p in public_prefixes
        ):
            return await call_next(request)

        # For all other requests, check authentication
        auth_header = request.headers.get("authorization", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

        if not token:
            return JSONResponse({"message": "Authentication required"}, status_code=401)

        try:
            mcp_components = request.app.state.mcp_components
            auth_result = await mcp_components["auth_manager"].validate_token(token)
            if not auth_result.authenticated:
                return JSONResponse({"message": "Invalid token"}, status_code=401)
            request.state.user = auth_result
            return await call_next(request)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Authentication error: %s", str(e))
            return JSONResponse({"message": "Authentication error"}, status_code=500)


# --- Starlette app assembly ---


middleware = [
    Middleware(RequestIDMiddleware),
    Middleware(MonitoringMiddleware),
    Middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
        allow_headers=["*"],
        expose_headers=[
            "X-Request-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
    ),
    Middleware(SecurityHeadersMiddleware),
    Middleware(AuthMiddleware),
]

# mypy has trouble with Starlette's lifespan protocol; the app works as intended.
app = Starlette(  # type: ignore[arg-type]
    debug=True,
    routes=routes,
    lifespan=app_lifespan,
    middleware=middleware,
)


# Custom rate limiting exception handler with proper headers
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Custom rate limit handler with proper headers."""
    response = JSONResponse(
        {"error": "Rate limit exceeded", "retry_after": exc.retry_after}, status_code=429
    )

    # Add rate limiting headers
    if exc.retry_after:
        response.headers["Retry-After"] = str(exc.retry_after)

    # Add rate limit info headers
    response.headers["X-RateLimit-Limit"] = str(exc.limit)
    response.headers["X-RateLimit-Remaining"] = "0"
    response.headers["X-RateLimit-Reset"] = str(
        int(exc.reset_time.timestamp()) if exc.reset_time else 0
    )

    return response


# Add rate limiting exception handler
app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)


if __name__ == "__main__":
    configure_json_logging(settings.LOG_LEVEL)
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.SERVER_PORT,
        reload=True,
    )
