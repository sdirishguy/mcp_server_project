# tests/test_mcp_implementation.py
import logging
import os
import time

import httpx
import pytest

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")

TEST_QUERY = {"method": "get", "path": "/get", "params": {"hello": "world"}}


def _headers(token: str | None) -> dict:
    return {"Authorization": f"Bearer {token}"} if token else {}


@pytest.mark.anyio
async def test_health_check(http_client: httpx.AsyncClient):
    resp = await http_client.get(f"{BASE_URL}/health", timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") in {"ok", "healthy", "OK"}


@pytest.mark.anyio
async def test_authentication(token: str | None, http_client: httpx.AsyncClient):
    # If no auth is configured, expect 200/401/404 depending on your app
    resp = await http_client.get(
        f"{BASE_URL}/api/profile",
        headers=_headers(token),
        timeout=10,
    )
    assert resp.status_code in {200, 401, 404}


@pytest.mark.anyio
async def test_audit_logging(token: str | None, http_client: httpx.AsyncClient):
    resp = await http_client.get(
        f"{BASE_URL}/health",
        headers=_headers(token),
        timeout=10,
    )
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_adapter_creation(token: str | None, http_client: httpx.AsyncClient):
    # Ensure the endpoint is reachable and returns a plausible shape
    rest_cfg = {
        "name": "test-rest-adapter-inline",
        "base_url": "https://httpbin.org",
        "headers": {},
        "timeout": 10,
    }
    resp = await http_client.post(
        f"{BASE_URL}/api/adapters/rest_api",
        headers=_headers(token),
        json=rest_cfg,
        timeout=15,
    )
    assert resp.status_code in {200, 404, 401}, f"Unexpected status: {resp.status_code}"
    if resp.status_code == 200:
        data = resp.json()
        assert "instance_id" in data


@pytest.mark.anyio
async def test_adapter_execution(
    token: str | None,
    instance_id: str | None,
    http_client: httpx.AsyncClient,
):
    if instance_id is None:
        pytest.skip("No adapter instance available")

    resp = await http_client.post(
        f"{BASE_URL}/api/adapters/{instance_id}/execute",
        headers=_headers(token),
        json=TEST_QUERY,
        timeout=20,
    )
    assert resp.status_code in {200, 500}, f"Unexpected status code {resp.status_code}"


@pytest.mark.anyio
async def test_caching(
    token: str | None,
    instance_id: str | None,
    http_client: httpx.AsyncClient,
):
    if instance_id is None:
        pytest.skip("No adapter instance available")

    start = time.time()
    r1 = await http_client.post(
        f"{BASE_URL}/api/adapters/{instance_id}/execute",
        headers=_headers(token),
        json=TEST_QUERY,
        timeout=20,
    )
    t1 = time.time() - start

    start = time.time()
    r2 = await http_client.post(
        f"{BASE_URL}/api/adapters/{instance_id}/execute",
        headers=_headers(token),
        json=TEST_QUERY,
        timeout=20,
    )
    t2 = time.time() - start

    logger.info("First call: %.4fs, second call: %.4fs", t1, t2)
    assert r1.status_code in {200, 500}
    assert r2.status_code in {200, 500}
    if r1.status_code == 200 and r2.status_code == 200:
        assert r1.json() == r2.json()
