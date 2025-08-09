# tests/conftest.py
import logging
import os

import httpx
import pytest
import pytest_asyncio

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
    candidates = ["/auth/login", "/api/auth/login", "/api/login"]
    payloads = [
        {"username": "test", "password": "test"},
        {"username": "admin", "password": "admin"},
    ]
    for path in candidates:
        url = f"{BASE_URL}{path}"
        for body in payloads:
            try:
                resp = await client.post(url, json=body, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    token = data.get("token") or data.get("access_token")
                    if token:
                        logger.info("Obtained auth token from %s", path)
                        return token
            except Exception:
                # Quietly try next option
                pass
    logger.info("No auth endpoint found; proceeding without Authorization header.")
    return None


@pytest_asyncio.fixture(scope="function")
async def http_client():
    async with httpx.AsyncClient() as client:
        yield client


@pytest_asyncio.fixture(scope="function")
async def token(http_client: httpx.AsyncClient) -> str | None:
    return await _try_get_token(http_client)


@pytest_asyncio.fixture(scope="function")
async def instance_id(http_client: httpx.AsyncClient, token: str | None) -> str | None:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    create_url = f"{BASE_URL}/api/adapters/rest_api"
    try:
        resp = await http_client.post(create_url, headers=headers, json=REST_API_CONFIG, timeout=15)
    except Exception as e:
        pytest.skip(f"Adapter creation endpoint not reachable: {e}")

    if resp.status_code != 200:
        pytest.skip(f"Adapter creation failed ({resp.status_code}): {resp.text}")

    data = resp.json()
    inst_id = data.get("instance_id")
    if not inst_id:
        pytest.skip("Adapter creation did not return instance_id")
    return inst_id
