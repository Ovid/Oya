"""Health check endpoint tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from oya.main import app


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


async def test_health_check_returns_healthy(client: AsyncClient):
    """Health endpoint returns healthy status."""
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
