from httpx import ASGITransport, AsyncClient
import pytest

from entrypoints.http import app_factory


@pytest.mark.asyncio
async def test_health_live_returns_ok() -> None:
    app = await app_factory.get_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
