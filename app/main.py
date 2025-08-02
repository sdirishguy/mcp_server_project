# app/main.py

import logging
import hashlib
import uuid
import os

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
from starlette.requests import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

# --- MCP component imports ---
from app.mcp.core.adapter import AdapterRegistry, AdapterManager, DataRequest, DataResponse
from app.mcp.security.auth.authentication import AuthenticationManager, InMemoryAuthProvider
from app.mcp.security.auth.authorization import AuthorizationManager, create_admin_role, ResourceType, Action
from app.mcp.security.audit.audit_logging import create_default_audit_logger, AuditEvent, AuditEventType, AuditEventOutcome
from app.mcp.cache.memory.in_memory_cache import InMemoryCache, CacheManager
from app.mcp.adapters.database.postgres_adapter import PostgreSQLAdapter
from app.mcp.adapters.api.rest_api_adapter import RestApiAdapter

from app.tools import ALL_TOOLS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - SERVER - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# --- Auth Middleware ---
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        public_paths = [
            "/api/auth/login",
            "/health",
            "/whoami",
            "/api/mcp.json/"
        ]
        if request.method == "OPTIONS" or any(request.url.path.startswith(path) for path in public_paths):
            return await call_next(request)

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
            await mcp_components["audit_logger"].log_event(
                AuditEvent(
                    event_type=AuditEventType.AUTHENTICATION,
                    event_action="token_validation",
                    outcome=AuditEventOutcome.SUCCESS,
                    user_id=auth_result.user_id,
                    resource_type="api",
                    resource_id=request.url.path,
                    details={"method": request.method}
                )
            )
            return await call_next(request)
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return JSONResponse({"message": "Authentication error"}, status_code=500)

# --- MCP component setup ---
async def setup_mcp():
    auth_manager = AuthenticationManager()
    auth_provider = InMemoryAuthProvider()
    auth_provider.add_user("admin", "admin123", roles=["admin"])
    auth_manager.register_provider("local", auth_provider)

    authz_manager = AuthorizationManager()
    authz_manager.add_role(create_admin_role())

    LOG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "audit.log"))
    audit_logger = create_default_audit_logger(LOG_FILE)

    l1_cache = InMemoryCache(max_size=1000)
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
        "adapter_manager": adapter_manager
    }

# --- FastMCP app and tools ---
mcp = FastMCP("MCP Server", stateless_http=True)
for tool in ALL_TOOLS:
    mcp.tool(name=tool["name"], description=tool["description"])(tool["handler"])
logger.info(f"Registered {len(ALL_TOOLS)} tools with FastMCP.")
mcp_app = mcp.http_app(path="/mcp.json/")

# --- Lifespan handler ---
async def app_lifespan(app):
    # Run FastMCP lifespan if needed
    if hasattr(mcp_app, "lifespan") and mcp_app.lifespan:
        async with mcp_app.lifespan(app):
            app.state.mcp_components = await setup_mcp()
            logger.info("MCP components initialized and available via app.state.mcp_components")
            yield
    else:
        app.state.mcp_components = await setup_mcp()
        logger.info("MCP components initialized and available via app.state.mcp_components")
        yield

# --- Endpoint function definitions (NO decorators) ---

async def whoami(request):
    if not hasattr(request.app.state, "mcp_components"):
        return JSONResponse({"error": "MCP Server not ready"}, status_code=503)
    mcp_components = request.app.state.mcp_components
    return JSONResponse({
        "message": "MCP Server is running",
        "providers": mcp_components["auth_manager"].get_provider_ids()
    })

async def health(request):
    return JSONResponse({"status": "ok", "message": "MCP Server is running!"})

async def login(request: Request):
    if not hasattr(request.app.state, "mcp_components"):
        return JSONResponse({"error": "MCP Server not ready"}, status_code=503)
    mcp_components = request.app.state.mcp_components
    try:
        credentials = await request.json()
        auth_result = await mcp_components["auth_manager"].authenticate(
            provider_id="local",
            credentials=credentials
        )
        if auth_result.authenticated:
            await mcp_components["audit_logger"].log_event(
                AuditEvent(
                    event_type=AuditEventType.AUTHENTICATION,
                    event_action="login",
                    outcome=AuditEventOutcome.SUCCESS,
                    user_id=auth_result.user_id,
                    details={"provider": "local"}
                )
            )
            return JSONResponse({
                "authenticated": True,
                "user_id": auth_result.user_id,
                "token": auth_result.token,
                "roles": auth_result.roles,
                "expires_at": auth_result.expires_at
            })
        else:
            await mcp_components["audit_logger"].log_event(
                AuditEvent(
                    event_type=AuditEventType.AUTHENTICATION,
                    event_action="login",
                    outcome=AuditEventOutcome.FAILURE,
                    details={"provider": "local"}
                )
            )
            return JSONResponse(
                status_code=401,
                content={"authenticated": False, "error": "Invalid credentials"}
            )
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Login failed: {str(e)}"}
        )

async def create_adapter(request: Request):
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
            action=Action.CREATE
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
                    details={"action": "create"}
                )
            )
            return JSONResponse(
                status_code=403,
                content={"error": "Permission denied"}
            )
        config = await request.json()
        instance_id = config.get("instance_id")
        if not instance_id:
            instance_id = f"{adapter_type}_{uuid.uuid4().hex[:8]}"
        await mcp_components["adapter_manager"].create_adapter(
            adapter_id=adapter_type,
            instance_id=instance_id,
            config=config
        )
        await mcp_components["audit_logger"].log_event(
            AuditEvent(
                event_type=AuditEventType.CONFIGURATION,
                event_action="create_adapter",
                outcome=AuditEventOutcome.SUCCESS,
                user_id=user.user_id,
                resource_type="adapter",
                resource_id=instance_id,
                details={"adapter_type": adapter_type}
            )
        )
        return JSONResponse({"instance_id": instance_id})
    except Exception as e:
        await mcp_components["audit_logger"].log_event(
            AuditEvent(
                event_type=AuditEventType.CONFIGURATION,
                event_action="create_adapter",
                outcome=AuditEventOutcome.ERROR,
                user_id=request.state.user.user_id if hasattr(request.state, "user") else None,
                resource_type="adapter",
                resource_id=adapter_type,
                details={"error": str(e)}
            )
        )
        logger.error(f"Adapter creation error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

async def execute_request(request: Request):
    if not hasattr(request.app.state, "mcp_components"):
        return JSONResponse({"error": "MCP Server not ready"}, status_code=503)
    mcp_components = request.app.state.mcp_components
    instance_id = request.path_params["instance_id"]
    try:
        user = request.state.user
        has_permission = mcp_components["authz_manager"].check_permission(
            roles=user.roles or [],
            permissions=user.permissions or [],
            resource_type=ResourceType.ADAPTER,
            resource_id=instance_id,
            action=Action.EXECUTE
        )
        if not has_permission:
            await mcp_components["audit_logger"].log_event(
                AuditEvent(
                    event_type=AuditEventType.AUTHORIZATION,
                    event_action="execute_request",
                    outcome=AuditEventOutcome.FAILURE,
                    user_id=user.user_id,
                    resource_type="adapter",
                    resource_id=instance_id,
                    details={"action": "execute"}
                )
            )
            return JSONResponse(
                status_code=403,
                content={"error": "Permission denied"}
            )
        body = await request.json()
        data_request = DataRequest(**body)
        query_hash = hashlib.md5(f"{data_request.query}:{str(data_request.parameters)}".encode()).hexdigest()
        cache_key = f"adapter:{instance_id}:{query_hash}"
        cached_response = await mcp_components["cache_manager"].get(cache_key)
        if cached_response:
            await mcp_components["audit_logger"].log_event(
                AuditEvent(
                    event_type=AuditEventType.DATA_ACCESS,
                    event_action="execute_cached",
                    outcome=AuditEventOutcome.SUCCESS,
                    user_id=user.user_id,
                    resource_type="adapter",
                    resource_id=instance_id,
                    details={"query": data_request.query, "cache_hit": True}
                )
            )
            return cached_response
        response = await mcp_components["adapter_manager"].execute_request(
            instance_id=instance_id,
            request=data_request
        )
        if isinstance(response, dict) and response.get("status_code", 200) == 200:
            await mcp_components["cache_manager"].set(cache_key, response, ttl_seconds=300)
        await mcp_components["audit_logger"].log_event(
            AuditEvent(
                event_type=AuditEventType.DATA_ACCESS,
                event_action="execute",
                outcome=AuditEventOutcome.SUCCESS,
                user_id=user.user_id,
                resource_type="adapter",
                resource_id=instance_id,
                details={"query": data_request.query, "cache_hit": False}
            )
        )
        return response
    except Exception as e:
        await mcp_components["audit_logger"].log_event(
            AuditEvent(
                event_type=AuditEventType.DATA_ACCESS,
                event_action="execute",
                outcome=AuditEventOutcome.ERROR,
                user_id=request.state.user.user_id if hasattr(request.state, "user") else None,
                resource_type="adapter",
                resource_id=instance_id,
                details={"error": str(e)}
            )
        )
        logger.error(f"Execute request error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

async def protected_route(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    return JSONResponse({
        "message": "This is a protected route",
        "user": user.user_id,
        "roles": user.roles
    })

# --- Routes using Route objects ---
routes = [
    Route("/api/auth/login", login, methods=["POST"]),
    Route("/api/adapters/{adapter_type}", create_adapter, methods=["POST"]),
    Route("/api/adapters/{instance_id}/execute", execute_request, methods=["POST"]),
    Route("/api/protected", protected_route),
    Route("/whoami", whoami),
    Route("/health", health),
    Mount("/mcp", app=mcp_app),
]

# --- Starlette app assembly ---
app = Starlette(
    debug=True,
    routes=routes,
    lifespan=app_lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthMiddleware)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
