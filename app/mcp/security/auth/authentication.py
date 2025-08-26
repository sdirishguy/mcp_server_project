"""
Authentication system for the Model Context Protocol (MCP).

This module provides interfaces and implementations for authenticating
users and services connecting to MCP.

ARCHITECTURE: Provider-based authentication system
- Supports multiple authentication providers (JWT, InMemory, future: OAUTH, LDAP)
- Clean separation between authentication logic and storage
- Pluggable design allows easy extension for new auth methods

CRITICAL ISSUE RESOLVED: Token validation sync problems
- Previous dual token tracking caused 401 errors in tests/CI
- Now single source of truth through provider's own token storage
- Eliminates race conditions between login and validation
"""

import time
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class AuthenticationResult(BaseModel):
    """Result of an authentication attempt.

    DESIGN: Comprehensive authentication response
    - Includes all necessary information for authorization decisions
    - Supports both successful and failed authentication scenarios
    - Extensible metadata field for provider-specific information
    - Unix timestamp for consistent expiration handling
    """

    authenticated: bool = Field(..., description="Whether authentication was successful")
    user_id: str | None = Field(None, description="ID of the authenticated user")
    roles: list[str] | None = Field(None, description="Roles assigned to the user")
    permissions: list[str] | None = Field(None, description="Permissions granted to the user")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")
    token: str | None = Field(None, description="Authentication token")
    expires_at: int | None = Field(None, description="Token expiration timestamp (Unix)")


class AuthenticationProvider(ABC):
    """Interface for authentication providers.

    DESIGN PATTERN: Abstract base class for providers
    - Ensures consistent interface across all authentication methods
    - Supports standard auth flow: authenticate -> get token -> validate token
    - Includes token refresh capability for long-running sessions
    - Each provider handles its own token format and validation logic
    """

    @abstractmethod
    async def authenticate(self, credentials: dict[str, Any]) -> AuthenticationResult:
        """Authenticate a user with provided credentials.

        Args:
            credentials: Authentication credentials (username/password, API key, etc.)

        Returns:
            AuthenticationResult: Result of the authentication attempt

        DESIGN: Flexible credential format
        - Dict allows different providers to accept different credential types
        - Username/password, API keys, OAuth tokens, etc.
        - Provider validates format and returns structured result
        """
        raise NotImplementedError

    @abstractmethod
    async def validate_token(self, token: str) -> AuthenticationResult:
        """Validate an authentication token.

        Args:
            token: The token to validate

        Returns:
            AuthenticationResult: Result of the token validation

        CRITICAL: Single source of truth for token validation
        - Each provider maintains its own token storage/validation
        - No external token tracking needed
        - Prevents sync issues between multiple token stores
        """
        raise NotImplementedError

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> AuthenticationResult:
        """Refresh an authentication token.

        Args:
            refresh_token: The refresh token

        Returns:
            AuthenticationResult: Result with a new token if successful

        FUTURE: Token refresh for long-running sessions
        - Allows extending sessions without re-authentication
        - Supports rotating tokens for security
        - Currently implemented as re-issue in simple providers
        """
        raise NotImplementedError


class AuthenticationManager:
    """Manages multiple authentication providers.

    ARCHITECTURE: Multi-provider management
    - Allows multiple authentication methods in same application
    - Provider selection based on requirements (JWT for production, InMemory for testing)
    - Fallback mechanisms for graceful degradation
    - Centralized token validation across all providers
    """

    def __init__(self):
        self._providers: dict[str, AuthenticationProvider] = {}

    def register_provider(self, provider_id: str, provider: AuthenticationProvider) -> None:
        """Register an authentication provider.

        Args:
            provider_id: Unique identifier for the provider (e.g., "jwt", "local")
            provider: The authentication provider instance

        DESIGN: Runtime provider registration
        - Allows conditional provider setup based on configuration
        - Supports provider switching without code changes
        - Easy testing with mock providers
        """
        self._providers[provider_id] = provider

    async def authenticate(self, provider_id: str, credentials: dict[str, Any]) -> AuthenticationResult:
        """Authenticate using a specific provider.

        Args:
            provider_id: ID of the provider to use
            credentials: Authentication credentials

        Returns:
            AuthenticationResult: Result of the authentication attempt

        Raises:
            KeyError: If no provider exists with the given ID

        DESIGN: Explicit provider selection
        - Allows different auth methods for different endpoints/clients
        - Clear provider selection prevents accidental fallbacks
        - Supports provider-specific features and configurations
        """
        if provider_id not in self._providers:
            return AuthenticationResult(authenticated=False)

        return await self._providers[provider_id].authenticate(credentials)

    async def validate_token(self, token: str) -> AuthenticationResult:
        """Validate a token against all registered providers.

        Args:
            token: The token to validate

        Returns:
            AuthenticationResult: Result of the token validation

        CRITICAL FIX: Simplified token validation
        - Tries provider-specific format first (provider_id:token_value)
        - Falls back to trying all providers for compatibility
        - Returns first successful validation result
        - No external token tracking needed
        """
        # Token format: provider_id:token_value (optional)
        try:
            provider_id, token_value = token.split(":", 1)
            if provider_id in self._providers:
                return await self._providers[provider_id].validate_token(token_value)
        except ValueError:
            # Try each provider if format doesn't include provider prefix
            pass

        # Try all providers for compatibility
        for provider in self._providers.values():
            result = await provider.validate_token(token)
            if result.authenticated:
                return result

        return AuthenticationResult(authenticated=False)

    async def refresh_token(self, provider_id: str, refresh_token: str) -> AuthenticationResult:
        """Refresh a token using a specific provider.

        Args:
            provider_id: ID of the provider to use
            refresh_token: The refresh token

        Returns:
            AuthenticationResult: Result with a new token if successful
        """
        if provider_id not in self._providers:
            return AuthenticationResult(authenticated=False)

        return await self._providers[provider_id].refresh_token(refresh_token)

    def get_provider_ids(self) -> list[str]:
        """Get IDs of all registered providers.

        Returns:
            List[str]: List of provider IDs

        DEBUGGING: Useful for troubleshooting auth issues
        - Shows which providers are actually registered
        - Helps debug provider selection logic
        - Used by /whoami endpoint for system introspection
        """
        return list(self._providers.keys())


class InMemoryAuthProvider(AuthenticationProvider):
    """Simple in-memory authentication provider for testing and development.

    DESIGN: Lightweight provider for non-production use
    - Stores users and tokens in memory (lost on restart)
    - No external dependencies (database, Redis, etc.)
    - Perfect for testing, development, and simple deployments
    - Fast and predictable for CI/CD environments

    SECURITY NOTE: Not suitable for production clustering
    - Tokens stored in single process memory
    - No persistence across restarts
    - No sharing across multiple server instances
    """

    def __init__(self, token_expiry_minutes: int = 60):
        self._users: dict[str, dict[str, Any]] = {}
        self._tokens: dict[str, dict[str, Any]] = {}  # CRITICAL: Single source of truth
        self._token_expiry_minutes = token_expiry_minutes

    def add_user(self, username: str, password: str, roles: list[str] = None, permissions: list[str] = None) -> None:
        """Add a user to the provider.

        Args:
            username: Username
            password: Password (plain text for simplicity - hash in production)
            roles: Roles assigned to the user
            permissions: Permissions granted to the user

        SECURITY CONSIDERATION: Plain text passwords
        - Acceptable for testing and development
        - Production deployments should hash passwords
        - Consider bcrypt, scrypt, or Argon2 for production
        """
        self._users[username] = {
            "password": password,
            "roles": roles or [],
            "permissions": permissions or [],
        }

    async def authenticate(self, credentials: dict[str, Any]) -> AuthenticationResult:
        """Authenticate a user with username and password.

        Args:
            credentials: Dict containing "username" and "password"

        Returns:
            AuthenticationResult: Result of the authentication attempt

        DESIGN: Simple credential validation
        - Expects username/password in credentials dict
        - Generates timestamp-based tokens for simplicity
        - Stores token metadata for later validation
        - Returns all user information for authorization decisions
        """
        username = credentials.get("username")
        password = credentials.get("password")

        if not username or not password:
            return AuthenticationResult(authenticated=False)

        user = self._users.get(username)
        if not user or user["password"] != password:
            return AuthenticationResult(authenticated=False)

        # Generate simple token: username_timestamp
        # DESIGN: Predictable tokens for testing
        token = f"{username}_{int(time.time())}"
        expires_at = int(time.time() + self._token_expiry_minutes * 60)

        # CRITICAL: Store token in provider's own storage
        self._tokens[token] = {"username": username, "expires_at": expires_at}

        return AuthenticationResult(
            authenticated=True,
            user_id=username,
            roles=user["roles"],
            permissions=user["permissions"],
            token=token,
            expires_at=expires_at,
        )

    async def validate_token(self, token: str) -> AuthenticationResult:
        """Validate a token.

        Args:
            token: The token to validate

        Returns:
            AuthenticationResult: Result of the token validation

        CRITICAL FIX: Single source of truth validation
        - Checks only self._tokens (no external tracking)
        - Handles token expiration automatically
        - Cleans up expired tokens to prevent memory leaks
        - Returns full user information for authorization
        """
        token_data = self._tokens.get(token)
        if not token_data:
            return AuthenticationResult(authenticated=False)

        # Check if token is expired
        if token_data["expires_at"] < int(time.time()):
            # Remove expired token to prevent memory leaks
            del self._tokens[token]
            return AuthenticationResult(authenticated=False)

        username = token_data["username"]
        user = self._users.get(username)
        if not user:
            # User was deleted after token was issued
            return AuthenticationResult(authenticated=False)

        return AuthenticationResult(
            authenticated=True,
            user_id=username,
            roles=user["roles"],
            permissions=user["permissions"],
            token=token,
            expires_at=token_data["expires_at"],
        )

    async def refresh_token(self, refresh_token: str) -> AuthenticationResult:
        """Refresh a token.

        Args:
            refresh_token: The refresh token (same as the original token in this
                implementation)

        Returns:
            AuthenticationResult: Result with a new token if successful

        DESIGN: Simple refresh implementation
        - Uses same token as both access and refresh token
        - Validates existing token first
        - Generates new token with fresh expiration
        - Maintains same user privileges
        """
        # Validate the refresh token (same as the access token in this simple implementation)
        result = await self.validate_token(refresh_token)
        if not result.authenticated:
            return result

        # Generate new token
        username = result.user_id
        token = f"{username}_{int(time.time())}"
        expires_at = int(time.time() + self._token_expiry_minutes * 60)

        # Store new token
        self._tokens[token] = {"username": username, "expires_at": expires_at}

        # Update result with new token
        result.token = token
        result.expires_at = expires_at

        return result


class JWTAuthProvider(AuthenticationProvider):
    """JWT‑based authentication provider.

    This provider issues JSON Web Tokens (JWTs) signed with a server‑side
    secret.  It validates tokens by verifying the signature and expiration.
    User accounts are stored in memory similarly to ``InMemoryAuthProvider``.

    The token payload includes the subject (username), roles, permissions and
    expiration timestamp.  When authenticating, it returns an
    ``AuthenticationResult`` containing the encoded token and expiry.

    SECURITY: Production-ready authentication
    - Uses HMAC-SHA256 for token signing
    - Self-contained tokens (no server-side storage needed)
    - Stateless authentication suitable for horizontal scaling
    - Includes standard JWT claims (sub, exp, etc.)

    DESIGN: Hybrid approach
    - JWT tokens for stateless authentication
    - In-memory user storage for simplicity
    - Could be extended to use database/LDAP for users
    - Base64URL encoding for URL-safe tokens
    """

    def __init__(self, secret: str, expiry_minutes: int = 60) -> None:
        """Initialize JWT provider with signing secret.

        SECURITY: Secret key management
        - Secret should be cryptographically strong (32+ bytes)
        - Same secret must be used across all server instances
        - Consider key rotation for high-security environments
        """
        self._secret = secret.encode()
        self._expiry_minutes = expiry_minutes
        self._users: dict[str, dict[str, Any]] = {}

    def add_user(
        self, username: str, password: str, roles: list[str] | None = None, permissions: list[str] | None = None
    ) -> None:
        """Register a user with the provider.

        Args:
            username: Username
            password: Plain‑text password (for demo purposes; consider hashing in real deployments)
            roles: Roles assigned to the user
            permissions: Permissions granted to the user
        """
        self._users[username] = {
            "password": password,
            "roles": roles or [],
            "permissions": permissions or [],
        }

    @staticmethod
    def _base64url_encode(data: bytes) -> str:
        """Encode bytes as base64url without padding.

        JWT SPEC: Base64URL encoding without padding
        - Standard Base64 uses +, /, = characters
        - Base64URL uses -, _, no padding for URL safety
        - Required by JWT specification (RFC 7519)
        """
        import base64

        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    @staticmethod
    def _base64url_decode(data: str) -> bytes:
        """Decode a base64url encoded string, adding padding if necessary.

        JWT SPEC: Handle missing padding
        - Base64URL encoding removes padding
        - Must add back correct padding for decoding
        - Calculates padding length from string length
        """
        import base64

        padding = "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(data + padding)

    def _sign(self, msg: bytes) -> bytes:
        """Return HMAC‑SHA256 signature for a message using the provider's secret.

        SECURITY: HMAC-SHA256 signing
        - Industry standard for JWT signing
        - Cryptographically secure with proper secret
        - Prevents token tampering and forgery
        - Fast computation suitable for high-throughput
        """
        import hashlib
        import hmac

        return hmac.new(self._secret, msg, hashlib.sha256).digest()

    async def authenticate(self, credentials: dict[str, Any]) -> AuthenticationResult:
        """Authenticate a user and issue a JWT token.

        Args:
            credentials: Dict containing ``username`` and ``password`` keys

        Returns:
            AuthenticationResult: Result of the authentication attempt

        JWT CREATION PROCESS:
        1. Validate credentials against stored users
        2. Create JWT header (algorithm, type)
        3. Create JWT payload (subject, roles, expiration)
        4. Base64URL encode header and payload
        5. Sign header.payload with HMAC-SHA256
        6. Return header.payload.signature as token
        """
        username = credentials.get("username")
        password = credentials.get("password")
        if not username or not password:
            return AuthenticationResult(authenticated=False)

        user = self._users.get(username)
        if not user or user["password"] != password:
            return AuthenticationResult(authenticated=False)

        # Build JWT header and payload
        import json
        import time

        # JWT Header: Algorithm and type
        header = {"alg": "HS256", "typ": "JWT"}
        exp_timestamp = int(time.time() + self._expiry_minutes * 60)

        # JWT Payload: Claims about the user
        payload = {
            "sub": username,  # Subject (standard claim)
            "roles": user["roles"],  # Custom claim
            "permissions": user["permissions"],  # Custom claim
            "exp": exp_timestamp,  # Expiration (standard claim)
        }

        # Create JWT: header.payload.signature
        header_b64 = self._base64url_encode(json.dumps(header, separators=(",", ":")).encode())
        payload_b64 = self._base64url_encode(json.dumps(payload, separators=(",", ":")).encode())
        signing_input = f"{header_b64}.{payload_b64}".encode()
        signature = self._sign(signing_input)
        signature_b64 = self._base64url_encode(signature)
        token = f"{header_b64}.{payload_b64}.{signature_b64}"

        return AuthenticationResult(
            authenticated=True,
            user_id=username,
            roles=user["roles"],
            permissions=user["permissions"],
            token=token,
            expires_at=exp_timestamp,
        )

    async def validate_token(self, token: str) -> AuthenticationResult:
        """Validate a JWT token and return authentication result.

        Args:
            token: JWT string

        Returns:
            AuthenticationResult: Result of validation

        JWT VALIDATION PROCESS:
        1. Split token into header.payload.signature
        2. Recreate signing input from header.payload
        3. Verify signature matches expected signature
        4. Parse payload and check expiration
        5. Return user information from token claims

        SECURITY: Constant-time signature comparison
        - Uses hmac.compare_digest to prevent timing attacks
        - Validates signature before trusting payload
        - Checks expiration to prevent replay attacks
        """
        import json
        import time

        try:
            header_b64, payload_b64, signature_b64 = token.split(".")
        except ValueError:
            return AuthenticationResult(authenticated=False)

        try:
            # Verify signature first (before trusting payload)
            signing_input = f"{header_b64}.{payload_b64}".encode()
            expected_sig = self._sign(signing_input)
            provided_sig = self._base64url_decode(signature_b64)

            # SECURITY: Constant-time comparison prevents timing attacks
            import hmac

            if not hmac.compare_digest(expected_sig, provided_sig):
                return AuthenticationResult(authenticated=False)

            # Parse payload after signature verification
            payload_bytes = self._base64url_decode(payload_b64)
            payload = json.loads(payload_bytes)

            # Check expiration
            if payload.get("exp") and int(payload["exp"]) < int(time.time()):
                return AuthenticationResult(authenticated=False)

            # Extract user information from token claims
            username = payload.get("sub")
            roles = payload.get("roles", [])
            permissions = payload.get("permissions", [])
            if username is None:
                return AuthenticationResult(authenticated=False)

            return AuthenticationResult(
                authenticated=True,
                user_id=username,
                roles=roles,
                permissions=permissions,
                token=token,
                expires_at=payload.get("exp"),
            )
        except Exception:
            # Any parsing/validation error results in failed authentication
            # SECURITY: Fail closed - any error means invalid token
            return AuthenticationResult(authenticated=False)

    async def refresh_token(self, refresh_token: str) -> AuthenticationResult:
        """Refresh a JWT token by issuing a new one with a fresh expiration.

        Args:
            refresh_token: The old JWT

        Returns:
            AuthenticationResult: Result containing a new token if the old one is valid

        DESIGN: Token refresh via re-authentication
        - Validates old token to ensure it's legitimate
        - Re-issues new token with fresh expiration
        - Maintains same user privileges and roles
        - Could be enhanced with separate refresh tokens
        """
        result = await self.validate_token(refresh_token)
        if not result.authenticated:
            return result

        # Issue a new token
        username = result.user_id
        # For simplicity, reuse the stored user data; ensure user still exists
        user = self._users.get(username or "")
        if not user:
            return AuthenticationResult(authenticated=False)
        return await self.authenticate({"username": username, "password": user["password"]})
