import datetime as _dt
import json
import logging
import os

import httpx
import pytest

# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------

LOG = logging.getLogger("tests.mcp_client")
if not LOG.handlers:
    LOG.setLevel(logging.INFO)
    _fh = logging.FileHandler(
        f"client_run_{_dt.date.today().isoformat()}.log",
        mode="a",
        encoding="utf-8",
    )
    _sh = logging.StreamHandler()
    _fmt = logging.Formatter("%(asctime)s - CLIENT - %(levelname)s - %(message)s")
    _fh.setFormatter(_fmt)
    _sh.setFormatter(_fmt)
    LOG.addHandler(_fh)
    LOG.addHandler(_sh)

# ------------------------------------------------------------------------------
# Config
# ------------------------------------------------------------------------------

BASE_URL = os.getenv("MCP_TEST_BASE_URL", "http://127.0.0.1:8000")
HEALTH_PATH = "/health"
REQUEST_TIMEOUT = 5.0  # seconds


async def _get_json(client: httpx.AsyncClient, url: str) -> dict:
    """GET a URL and return JSON (or raise)."""
    resp = await client.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    try:
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        LOG.error("Response was not JSON. Text: %s", resp.text[:200])
        raise RuntimeError("Response not JSON") from exc


async def _server_reachable() -> bool:
    """Quick reachability probe against /health."""
    try:
        async with httpx.AsyncClient(base_url=BASE_URL) as client:
            resp = await client.get(HEALTH_PATH, timeout=REQUEST_TIMEOUT)
            return resp.status_code == 200
    except (httpx.ConnectError, httpx.ReadTimeout):
        return False


# ------------------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_endpoint_reports_ok():
    """Server should expose /health and return an OK payload."""
    if not await _server_reachable():
        pytest.skip(f"Server not reachable at {BASE_URL}; start it and rerun the test.")

    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        data = await _get_json(client, HEALTH_PATH)

    LOG.info("Health payload: %s", json.dumps(data, indent=2)[:200])
    assert isinstance(data, dict)
    # Be tolerant to future changes; just ensure the essentials exist.
    assert data.get("status") == "ok"
    assert "message" in data


@pytest.mark.asyncio
async def test_health_endpoint_latency_under_threshold():
    """Basic SLO: /health should respond quickly under light load."""
    if not await _server_reachable():
        pytest.skip(f"Server not reachable at {BASE_URL}; start it and rerun the test.")

    start = _dt.datetime.now()
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        await client.get(HEALTH_PATH, timeout=REQUEST_TIMEOUT)
    elapsed_ms = (_dt.datetime.now() - start).total_seconds() * 1000.0

    LOG.info("Health latency: %.2f ms", elapsed_ms)
    # Conservative threshold you can tighten later.
    assert elapsed_ms < 500.0
