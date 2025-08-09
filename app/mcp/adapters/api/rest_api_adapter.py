"""
REST API adapter for the Model Context Protocol (MCP).

This module provides an adapter for connecting to REST APIs.
"""

from typing import Any

from ...core.adapter import (AdapterCapability, AdapterMetadata, DataRequest,
                             DataResponse, MCPAdapter)


class RestApiAdapter(MCPAdapter):
    """Adapter for REST APIs."""

    def __init__(self):
        """Initialize the REST API adapter."""
        self._client = None
        self._base_url = None
        self._headers = {}

    async def initialize(self, config: dict[str, Any]) -> bool:
        """Initialize the adapter with configuration parameters.

        Args:
            config: Configuration parameters for the adapter

        Returns:
            bool: True if initialization was successful, False otherwise
        """
        try:
            self._base_url = config.get("base_url")
            if not self._base_url:
                print("Missing required parameter: base_url")
                return False

            self._headers = config.get("headers", {})

            # In a real implementation, we would use httpx.AsyncClient
            # For this example, we'll simulate the client
            self._client = {
                "connected": True,
                "base_url": self._base_url,
                "headers": self._headers,
                "timeout": config.get("timeout_seconds", 30.0),
                "follow_redirects": config.get("follow_redirects", True),
            }

            return True
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Failed to initialize REST API adapter: {e}")
            return False

    async def get_metadata(self) -> AdapterMetadata:
        """Return metadata about this adapter's capabilities.

        Returns:
            AdapterMetadata: Metadata about the adapter
        """
        return AdapterMetadata(
            name="REST API",
            version="1.0.0",
            description="Adapter for REST APIs",
            capabilities=[
                AdapterCapability.READ,
                AdapterCapability.WRITE,
            ],
            schema_supported=False,
            authentication_required=True,
        )

    async def execute(self, request: DataRequest) -> DataResponse:
        """Execute a data request against this adapter.

        Args:
            request: The data request to execute

        Returns:
            DataResponse: The response from the data source
        """
        try:
            if not self._client or not self._client["connected"]:
                return DataResponse(
                    data=None,
                    status_code=500,
                    error="API client not initialized",
                )

            # Parse the query as a URL path and HTTP method
            parts = request.query.split(" ", 1)
            method = parts[0].upper() if len(parts) > 1 else "GET"
            path = parts[1] if len(parts) > 1 else parts[0]

            url = f"{self._base_url.rstrip('/')}/{path.lstrip('/')}"

            # In a real implementation, we would use httpx to make the request
            # For this example, we'll simulate the request

            # Simulate different responses based on the path
            if "users" in path.lower():
                # Simulate a users endpoint
                data = [
                    {"id": 1, "name": "John Doe", "email": "john@example.com"},
                    {"id": 2, "name": "Jane Doe", "email": "jane@example.com"},
                ]
                status_code = 200
            elif "products" in path.lower():
                # Simulate a products endpoint
                data = [
                    {"id": 1, "name": "Product A", "price": 19.99, "in_stock": True},
                    {"id": 2, "name": "Product B", "price": 29.99, "in_stock": False},
                ]
                status_code = 200
            elif "auth" in path.lower() or "login" in path.lower():
                # Simulate an auth endpoint
                if method == "POST" and request.parameters and "username" in request.parameters:
                    data = {
                        "token": "simulated_jwt_token",
                        "expires_in": 3600,
                        "user_id": 123,
                    }
                    status_code = 200
                else:
                    data = {"error": "Invalid credentials"}
                    status_code = 401
            else:
                # Generic response
                data = {"message": "Endpoint not found"}
                status_code = 404

            # Return the response
            return DataResponse(
                data=data,
                metadata={
                    "status_code": status_code,
                    "headers": {
                        "Content-Type": "application/json",
                        "X-API-Version": "1.0",
                    },
                    "url": url,
                    "method": method,
                },
                status_code=200 if status_code < 400 else status_code,
                error=None if status_code < 400 else f"HTTP error: {status_code}",
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            return DataResponse(
                data=None,
                status_code=500,
                error=str(e),
            )

    async def health_check(self) -> bool:
        """Check if the adapter is functioning properly.

        Returns:
            bool: True if the adapter is healthy, False otherwise
        """
        try:
            if not self._client or not self._client["connected"]:
                return False

            # In a real implementation, we would make a request to the base URL
            # For this example, we'll just check if the client is connected
            return self._client["connected"]
        except Exception:  # pylint: disable=broad-exception-caught
            return False

    async def shutdown(self) -> None:
        """Clean up resources when shutting down."""
        if self._client and self._client["connected"]:
            # In a real implementation, we would close the client
            # For this example, we'll just set connected to False
            self._client["connected"] = False
            self._client = None
