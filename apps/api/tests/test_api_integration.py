import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test the health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_ready_check(client: AsyncClient):
    """Test the ready check endpoint."""
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_forgot_password_stub(client: AsyncClient):
    """Test the forgot password endpoint returns success."""
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "test@example.com"}
    )
    assert response.status_code == 200
    assert "reset link" in response.json()["message"]
