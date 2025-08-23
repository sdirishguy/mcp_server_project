"""
PostgreSQL adapter for the Model Context Protocol (MCP).

This module provides an adapter for connecting to PostgreSQL databases.
"""

import asyncio
from typing import Any

from ...core.adapter import (
    AdapterCapability,
    AdapterMetadata,
    DataRequest,
    DataResponse,
    MCPAdapter,
)


class PostgreSQLAdapter(MCPAdapter):
    """Adapter for PostgreSQL databases."""

    def __init__(self):
        """Initialize the PostgreSQL adapter."""
        self._pool = None
        self._config = None

    async def initialize(self, config: dict[str, Any]) -> bool:
        """Initialize the adapter with configuration parameters.

        Args:
            config: Configuration parameters for the adapter

        Returns:
            bool: True if initialization was successful, False otherwise
        """
        try:
            self._config = config

            # Check required config parameters
            required_params = ["host", "port", "user", "password", "database"]
            missing = [p for p in required_params if p not in config]
            if missing:
                print(f"Missing required parameter(s): {', '.join(missing)}")
                return False

            # Try to initialize a real connection pool with asyncpg if available
            try:
                import asyncpg  # type: ignore

                # Build DSN from parts; allow overriding with dsn directly
                dsn = config.get(
                    "dsn",
                    f"postgresql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}",
                )
                min_size = int(config.get("min_connections", 1))
                max_size = int(config.get("max_connections", 10))
                self._pool = await asyncpg.create_pool(dsn=dsn, min_size=min_size, max_size=max_size)
                return True
            except ImportError:
                # asyncpg is not installed; fall back to simulated connection
                await asyncio.sleep(0.1)
                self._pool = {
                    "connected": True,
                    "host": config["host"],
                    "port": config["port"],
                    "user": config["user"],
                    "database": config["database"],
                    "min_size": config.get("min_connections", 1),
                    "max_size": config.get("max_connections", 10),
                }
                return True
            except Exception as e:
                print(f"Failed to initialize PostgreSQL adapter: {e}")
                return False
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Failed to initialize PostgreSQL adapter: {e}")
            return False

    async def get_metadata(self) -> AdapterMetadata:
        """Return metadata about this adapter's capabilities.

        Returns:
            AdapterMetadata: Metadata about the adapter
        """
        return AdapterMetadata(
            name="PostgreSQL",
            version="1.0.0",
            description="Adapter for PostgreSQL databases",
            capabilities=[
                AdapterCapability.READ,
                AdapterCapability.WRITE,
                AdapterCapability.SEARCH,
            ],
            schema_supported=True,
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
            # Ensure pool is initialized and connected
            if not self._pool:
                return DataResponse(
                    data=None,
                    status_code=500,
                    error="Database connection not initialized",
                )

            # If we have a real asyncpg pool, use it to execute the query
            try:
                import asyncpg  # type: ignore
            except ImportError:
                asyncpg = None

            # Distinguish between pool types
            if asyncpg and isinstance(self._pool, asyncpg.pool.Pool):  # type: ignore[attr-defined]
                try:
                    sql = request.query
                    # Determine if this is a read or write query
                    cmd = sql.strip().split()[0].lower()
                    async with self._pool.acquire() as conn:
                        if cmd in {"select", "with"}:
                            rows = await conn.fetch(sql)
                            # Convert asyncpg Record to dict
                            data = [dict(row) for row in rows]
                            return DataResponse(data=data, metadata={"row_count": len(data)}, status_code=200)
                        else:
                            result = await conn.execute(sql)
                            return DataResponse(data={"result": result}, status_code=200)
                except Exception as e:
                    return DataResponse(data=None, status_code=500, error=str(e))
            else:
                # Simulated execution path
                await asyncio.sleep(0.05)
                query = request.query.strip().upper()
                if query.startswith("SELECT"):
                    if "USERS" in query:
                        data = [
                            {"id": 1, "username": "john_doe", "email": "john@example.com"},
                            {"id": 2, "username": "jane_doe", "email": "jane@example.com"},
                        ]
                    elif "PRODUCTS" in query:
                        data = [
                            {"id": 1, "name": "Product A", "price": 19.99},
                            {"id": 2, "name": "Product B", "price": 29.99},
                        ]
                    else:
                        data = [{"result": "Simulated query result"}]
                    return DataResponse(data=data, metadata={"row_count": len(data)}, status_code=200)
                elif query.startswith("INSERT") or query.startswith("UPDATE") or query.startswith("DELETE"):
                    return DataResponse(data={"affected_rows": 1}, status_code=200)
                else:
                    return DataResponse(data={"result": "Query executed successfully"}, status_code=200)
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
            if not self._pool or not self._pool["connected"]:
                return False

            # In a real implementation, we would execute a simple query
            # For this example, we'll just check if the pool is connected
            return self._pool["connected"]
        except Exception:  # pylint: disable=broad-exception-caught
            return False

    async def shutdown(self) -> None:
        """Clean up resources when shutting down."""
        if not self._pool:
            return
        try:
            # If this is a real asyncpg pool, close it properly
            try:
                import asyncpg  # type: ignore
            except ImportError:
                asyncpg = None
            if asyncpg and isinstance(self._pool, asyncpg.pool.Pool):  # type: ignore[attr-defined]
                await self._pool.close()
            else:
                # Simulated pool: mark as disconnected
                if isinstance(self._pool, dict):
                    self._pool["connected"] = False
        finally:
            self._pool = None
