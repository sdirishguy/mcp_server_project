"""
Core adapter interface for the Model Context Protocol (MCP).

This module defines the base interfaces and models for MCP adapters,
which provide standardized access to various data sources.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AdapterCapability(str, Enum):
    """Capabilities that an adapter can support."""

    READ = "read"
    WRITE = "write"
    SEARCH = "search"
    STREAM = "stream"
    FUNCTION_CALL = "function_call"


class AdapterMetadata(BaseModel):
    """Metadata about an adapter's capabilities and requirements."""

    name: str = Field(..., description="Name of the adapter")
    version: str = Field(..., description="Version of the adapter")
    description: str = Field(..., description="Description of the adapter")
    capabilities: list[AdapterCapability] = Field(..., description="Capabilities supported by the adapter")
    schema_supported: bool = Field(False, description="Whether the adapter supports schema operations")
    authentication_required: bool = Field(False, description="Whether authentication is required for this adapter")


class DataRequest(BaseModel):
    """A request to retrieve or manipulate data through an adapter."""

    query: str = Field(..., description="The query to execute")
    parameters: dict[str, Any] | None = Field(None, description="Parameters for the query")
    context: dict[str, Any] | None = Field(None, description="Additional context for the query")
    max_results: int | None = Field(None, description="Maximum number of results to return")
    timeout_ms: int | None = Field(None, description="Timeout for the query in milliseconds")


class DataResponse(BaseModel):
    """A response from a data request."""

    data: Any = Field(..., description="The data returned from the request")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata about the response")
    status_code: int = Field(200, description="Status code of the response")
    error: str | None = Field(None, description="Error message if any")


class MCPAdapter(ABC):
    """Base interface for all MCP adapters."""

    @abstractmethod
    async def initialize(self, config: dict[str, Any]) -> bool:
        """Initialize the adapter with configuration parameters.

        Args:
            config: Configuration parameters for the adapter

        Returns:
            bool: True if initialization was successful, False otherwise
        """

    @abstractmethod
    async def get_metadata(self) -> AdapterMetadata:
        """Return metadata about this adapter's capabilities.

        Returns:
            AdapterMetadata: Metadata about the adapter
        """

    @abstractmethod
    async def execute(self, request: DataRequest) -> DataResponse:
        """Execute a data request against this adapter.

        Args:
            request: The data request to execute

        Returns:
            DataResponse: The response from the data source
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the adapter is functioning properly.

        Returns:
            bool: True if the adapter is healthy, False otherwise
        """

    @abstractmethod
    async def shutdown(self) -> None:
        """Clean up resources when shutting down."""
        raise NotImplementedError


class AdapterRegistry:
    """Registry for discovering and managing available adapters."""

    def __init__(self):
        self._adapters: dict[str, type[MCPAdapter]] = {}

    def register(self, adapter_id: str, adapter_class: type[MCPAdapter]) -> None:
        """Register an adapter class with a unique ID.

        Args:
            adapter_id: Unique identifier for the adapter
            adapter_class: The adapter class to register

        Raises:
            ValueError: If an adapter with the same ID is already registered
        """
        if adapter_id in self._adapters:
            raise ValueError(f"Adapter ID '{adapter_id}' already registered")
        self._adapters[adapter_id] = adapter_class

    def get(self, adapter_id: str) -> type[MCPAdapter]:
        """Get an adapter class by ID.

        Args:
            adapter_id: The ID of the adapter to retrieve

        Returns:
            The adapter class

        Raises:
            KeyError: If no adapter is registered with the given ID
        """
        if adapter_id not in self._adapters:
            raise KeyError(f"No adapter registered with ID '{adapter_id}'")
        return self._adapters[adapter_id]

    def list_adapters(self) -> list[str]:
        """List all registered adapter IDs.

        Returns:
            List[str]: List of registered adapter IDs
        """
        return list(self._adapters.keys())


class AdapterManager:
    """Responsible for instantiating, configuring, and managing adapter lifecycle."""

    def __init__(self, registry: AdapterRegistry):
        self._registry = registry
        self._instances: dict[str, MCPAdapter] = {}

    async def create_adapter(self, adapter_id: str, instance_id: str, config: dict[str, Any]) -> str:
        """Create and initialize an adapter instance.

        Args:
            adapter_id: The ID of the adapter type to create
            instance_id: A unique ID for this adapter instance
            config: Configuration parameters for the adapter

        Returns:
            str: The instance ID of the created adapter

        Raises:
            KeyError: If no adapter is registered with the given ID
            RuntimeError: If adapter initialization fails
        """
        adapter_class = self._registry.get(adapter_id)
        adapter = adapter_class()
        success = await adapter.initialize(config)

        if not success:
            raise RuntimeError(f"Failed to initialize adapter '{adapter_id}'")

        self._instances[instance_id] = adapter
        return instance_id

    async def execute_request(self, instance_id: str, request: DataRequest) -> DataResponse:
        """Execute a request on a specific adapter instance.

        Args:
            instance_id: The ID of the adapter instance
            request: The data request to execute

        Returns:
            DataResponse: The response from the adapter

        Raises:
            KeyError: If no adapter instance exists with the given ID
        """
        if instance_id not in self._instances:
            raise KeyError(f"No adapter instance with ID '{instance_id}'")

        return await self._instances[instance_id].execute(request)

    async def shutdown_adapter(self, instance_id: str) -> None:
        """Shutdown and remove an adapter instance.

        Args:
            instance_id: The ID of the adapter instance to shutdown
        """
        if instance_id in self._instances:
            await self._instances[instance_id].shutdown()
            del self._instances[instance_id]

    async def shutdown_all(self) -> None:
        """Shutdown all adapter instances."""
        for instance_id in list(self._instances.keys()):
            await self.shutdown_adapter(instance_id)

    def get_instance_ids(self) -> list[str]:
        """Get IDs of all active adapter instances.

        Returns:
            List[str]: List of instance IDs
        """
        return list(self._instances.keys())

    async def get_adapter_metadata(self, instance_id: str) -> AdapterMetadata:
        """Get metadata for a specific adapter instance.

        Args:
            instance_id: The ID of the adapter instance

        Returns:
            AdapterMetadata: Metadata about the adapter

        Raises:
            KeyError: If no adapter instance exists with the given ID
        """
        if instance_id not in self._instances:
            raise KeyError(f"No adapter instance with ID '{instance_id}'")

        return await self._instances[instance_id].get_metadata()

    async def health_check(self, instance_id: str) -> bool:
        """Check the health of a specific adapter instance.

        Args:
            instance_id: The ID of the adapter instance

        Returns:
            bool: True if the adapter is healthy, False otherwise

        Raises:
            KeyError: If no adapter instance exists with the given ID
        """
        if instance_id not in self._instances:
            raise KeyError(f"No adapter instance with ID '{instance_id}'")

        return await self._instances[instance_id].health_check()
