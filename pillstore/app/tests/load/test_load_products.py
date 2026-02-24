import asyncio
import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

TRANSPORT = ASGITransport(app=app)
CONCURRENT = 30
REQUESTS_PER_ENDPOINT = 50


async def _run_concurrent(
    path: str,
    concurrent: int = CONCURRENT,
    total: int = REQUESTS_PER_ENDPOINT,
) -> tuple[int, float]:
    async with AsyncClient(transport=TRANSPORT, base_url="http://test", timeout=10.0) as client:
        start = time.perf_counter()
        sem = asyncio.Semaphore(concurrent)

        async def one_request():
            async with sem:
                r = await client.get(path)
                return r.status_code == 200

        tasks = [one_request() for _ in range(total)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.perf_counter() - start
    ok = sum(1 for x in results if x is True)
    failed = sum(1 for x in results if isinstance(x, Exception))
    if failed:
        pytest.fail(f"{failed} requests failed with exceptions (e.g. DB not available)")
    return ok, elapsed


@pytest.mark.asyncio
async def test_load_health():
    ok, elapsed = await _run_concurrent("/health", concurrent=20, total=100)
    assert ok == 100, f"Expected 100 OK, got {ok}"
    assert elapsed < 15.0, f"Health should complete in <15s, got {elapsed:.1f}s"


@pytest.mark.asyncio
async def test_load_products_list():
    ok, elapsed = await _run_concurrent(
        "/api/v2/products",
        concurrent=20,
        total=REQUESTS_PER_ENDPOINT,
    )
    assert ok == REQUESTS_PER_ENDPOINT, f"Expected all OK, got {ok}"
    assert elapsed < 20.0, f"Products list should complete in <20s, got {elapsed:.1f}s"
