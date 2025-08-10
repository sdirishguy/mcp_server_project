"""Test configuration and fixtures for MCP server tests.

This module provides pytest fixtures and utilities for testing the MCP server
functionality, including HTTP client setup, authentication token handling,
and adapter instance management.
"""

import logging
import os

import httpx
import pytest

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")

REST_API_CONFIG = {
    "name": "test-rest-adapter",
    "base_url": "https://httpbin.org",
    "headers": {},
    "timeout": 10,
}
TEST_QUERY = {"method": "get", "path": "/get", "params": {"hello": "world"}}


async def _try_get_token(client: httpx.AsyncClient) -> str | None:
    """Try to get an authentication token from common auth endpoints."""
    candidates = ["/auth/login", "/api/auth/login", "/api/login"]
    payloads = [
        {"username": "test", "password": "test"},
        {"username": "admin", "password": "admin"},
    ]

    for path in candidates:
        url = f"{BASE_URL}{path}"
        for body in payloads:
            try:
                resp = await client.post(url, json=body, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    auth_token = data.get("token") or data.get("access_token")
                    if auth_token:
                        logger.info("Obtained auth token from %s", path)
                        return auth_token
            except (httpx.RequestError, httpx.HTTPStatusError, httpx.TimeoutException):
                # Quietly try next option
                pass
            except Exception as e:
                # Log unexpected errors but continue
                logger.debug("Unexpected error during auth attempt: %s", e)
                pass

    logger.info("No auth endpoint found; proceeding without Authorization header.")
    return None


@pytest.fixture(scope="function")
async def http_client():
    """Provide an httpx AsyncClient for making HTTP requests in tests."""
    # Create client with explicit timeout and connection limits for CI stability
    timeout = httpx.Timeout(10.0, connect=5.0)
    limits = httpx.Limits(max_keepalive_connections=1, max_connections=2)

    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        yield client


@pytest.fixture(scope="function")
async def token(
    http_client: httpx.AsyncClient,  # pylint: disable=redefined-outer-name
) -> str | None:
    """Attempt to obtain an authentication token from the server.

    Tries multiple common auth endpoints with test credentials.
    Returns None if no authentication endpoint is available.
    """
    return await _try_get_token(http_client)


@pytest.fixture(scope="function")
async def instance_id(
    http_client: httpx.AsyncClient,  # pylint: disable=redefined-outer-name
    token: str | None,  # pylint: disable=redefined-outer-name
) -> str | None:
    """Create a test REST API adapter instance and return its ID.

    Creates an adapter configured to use httpbin.org for testing.
    Skips the test if adapter creation fails or is not supported.

    Returns:
        The instance ID of the created adapter, or None if creation failed.

    """
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    create_url = f"{BASE_URL}/api/adapters/rest_api"
    try:
        resp = await http_client.post(create_url, headers=headers, json=REST_API_CONFIG, timeout=15)
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        pytest.skip(f"Adapter creation endpoint not reachable: {e}")

    if resp.status_code != 200:
        pytest.skip(f"Adapter creation failed ({resp.status_code}): {resp.text}")

    data = resp.json()
    inst_id = data.get("instance_id")
    if not inst_id:
        pytest.skip("Adapter creation did not return instance_id")
    return inst_id
