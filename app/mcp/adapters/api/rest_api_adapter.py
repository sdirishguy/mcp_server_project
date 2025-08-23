"""
REST API adapter for the Model Context Protocol (MCP).

This module provides an adapter for connecting to REST APIs.
"""

from typing import Any

from ...core.adapter import (
    AdapterCapability,
    AdapterMetadata,
    DataRequest,
    DataResponse,
    MCPAdapter,
)


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

            # Use httpx.AsyncClient for real HTTP requests
            import httpx  # Imported lazily to avoid overhead when not needed

            timeout = config.get("timeout_seconds", 30.0)
            follow_redirects = config.get("follow_redirects", True)
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=self._headers,
                timeout=timeout,
                follow_redirects=follow_redirects,
            )

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

            # Parse the query as "METHOD /path" or just path for GET
            parts = request.query.strip().split(" ", 1)
            if len(parts) == 2:
                method_str, path = parts[0].upper(), parts[1]
            else:
                method_str, path = "GET", parts[0]

            method = method_str.lower()
            url_path = path.lstrip("/")

            # Build request parameters
            params = {}
            headers = self._headers.copy()
            body = None
            if request.parameters:
                params = request.parameters.get("params", {}) or {}
                # Override default headers with those specified in request parameters
                headers.update(request.parameters.get("headers", {}) or {})
                body = request.parameters.get("body")

            try:
                client = self._client
                if client is None:
                    return DataResponse(
                        data=None,
                        status_code=500,
                        error="API client not initialized",
                    )

                # Perform the HTTP request using httpx
                response = await client.request(
                    method,
                    url_path,
                    params=params,
                    headers=headers,
                    json=body,
                )

                # Attempt to decode JSON, fall back to text if JSON fails
                try:
                    data = response.json()
                except Exception:
                    data = response.text

                return DataResponse(
                    data=data,
                    metadata={
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "url": str(response.url),
                        "method": method_str,
                    },
                    status_code=response.status_code,
                    error=None if response.is_success else response.text,
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                return DataResponse(
                    data=None,
                    status_code=500,
                    error=str(e),
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
        # Close the underlying httpx client if it exists
        try:
            if self._client:
                await self._client.aclose()
        except Exception:
            pass
        finally:
            self._client = None
