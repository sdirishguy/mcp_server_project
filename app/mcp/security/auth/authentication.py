"""
Authentication system for the Model Context Protocol (MCP).

This module provides interfaces and implementations for authenticating
users and services connecting to MCP.
"""

import time
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class AuthenticationResult(BaseModel):
    """Result of an authentication attempt."""

    authenticated: bool = Field(..., description="Whether authentication was successful")
    user_id: str | None = Field(None, description="ID of the authenticated user")
    roles: list[str] | None = Field(None, description="Roles assigned to the user")
    permissions: list[str] | None = Field(None, description="Permissions granted to the user")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")
    token: str | None = Field(None, description="Authentication token")
    expires_at: int | None = Field(None, description="Token expiration timestamp (Unix)")


class AuthenticationProvider(ABC):
    """Interface for authentication providers."""

    @abstractmethod
    async def authenticate(self, credentials: dict[str, Any]) -> AuthenticationResult:
        """Authenticate a user with provided credentials.

        Args:
            credentials: Authentication credentials

        Returns:
            AuthenticationResult: Result of the authentication attempt
        """
        raise NotImplementedError

    @abstractmethod
    async def validate_token(self, token: str) -> AuthenticationResult:
        """Validate an authentication token.

        Args:
            token: The token to validate

        Returns:
            AuthenticationResult: Result of the token validation
        """
        raise NotImplementedError

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> AuthenticationResult:
        """Refresh an authentication token.

        Args:
            refresh_token: The refresh token

        Returns:
            AuthenticationResult: Result with a new token if successful
        """
        raise NotImplementedError


class AuthenticationManager:
    """Manages multiple authentication providers."""

    def __init__(self):
        self._providers: dict[str, AuthenticationProvider] = {}

    def register_provider(self, provider_id: str, provider: AuthenticationProvider) -> None:
        """Register an authentication provider.

        Args:
            provider_id: Unique identifier for the provider
            provider: The authentication provider instance
        """
        self._providers[provider_id] = provider

    async def authenticate(
        self, provider_id: str, credentials: dict[str, Any]
    ) -> AuthenticationResult:
        """Authenticate using a specific provider.

        Args:
            provider_id: ID of the provider to use
            credentials: Authentication credentials

        Returns:
            AuthenticationResult: Result of the authentication attempt

        Raises:
            KeyError: If no provider exists with the given ID
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
        """
        # Token format: provider_id:token_value
        try:
            provider_id, token_value = token.split(":", 1)
            if provider_id in self._providers:
                return await self._providers[provider_id].validate_token(token_value)
        except ValueError:
            # Try each provider if format is invalid
            pass

        # Try all providers
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
        """
        return list(self._providers.keys())


class InMemoryAuthProvider(AuthenticationProvider):
    """Simple in-memory authentication provider for testing and development."""

    def __init__(self, token_expiry_minutes: int = 60):
        self._users: dict[str, dict[str, Any]] = {}
        self._tokens: dict[str, dict[str, Any]] = {}
        self._token_expiry_minutes = token_expiry_minutes

    def add_user(
        self, username: str, password: str, roles: list[str] = None, permissions: list[str] = None
    ) -> None:
        """Add a user to the provider.

        Args:
            username: Username
            password: Password
            roles: Roles assigned to the user
            permissions: Permissions granted to the user
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
        """
        username = credentials.get("username")
        password = credentials.get("password")

        if not username or not password:
            return AuthenticationResult(authenticated=False)

        user = self._users.get(username)
        if not user or user["password"] != password:
            return AuthenticationResult(authenticated=False)

        # Generate token
        token = f"{username}_{int(time.time())}"
        expires_at = int(time.time() + self._token_expiry_minutes * 60)

        # Store token
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
        """
        token_data = self._tokens.get(token)
        if not token_data:
            return AuthenticationResult(authenticated=False)

        # Check if token is expired
        if token_data["expires_at"] < int(time.time()):
            # Remove expired token
            del self._tokens[token]
            return AuthenticationResult(authenticated=False)

        username = token_data["username"]
        user = self._users.get(username)
        if not user:
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
        """
        # Validate the refresh token (same as the access token in this simple
        # implementation for now).
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
