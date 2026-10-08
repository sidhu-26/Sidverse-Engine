import pytest
from httpx import AsyncClient
from starlette import status

from app.core.database import get_db
from app.main import app


@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient) -> None:
    """Test that the application health check endpoint returns 200 and status ok."""
    response = await async_client.get("/api/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_db_health_check_success(async_client: AsyncClient) -> None:
    """Test that the database health check returns connected when db dependency succeeds."""

    class MockAsyncSession:
        async def execute(self, query: object) -> object:
            class MockResult:
                def scalar(self) -> int:
                    return 1

            return MockResult()

        async def close(self) -> None:
            pass

    async def mock_get_db() -> object:
        yield MockAsyncSession()

    app.dependency_overrides[get_db] = mock_get_db
    try:
        response = await async_client.get("/api/health/db")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "ok", "database": "connected"}
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_db_health_check_failure(async_client: AsyncClient) -> None:
    """Test that the database health check returns 503 when db execution fails."""

    class FailingAsyncSession:
        async def execute(self, query: object) -> object:
            raise ConnectionError("Database unreachable")

        async def close(self) -> None:
            pass

    async def mock_get_db_error():
        yield FailingAsyncSession()

    app.dependency_overrides[get_db] = mock_get_db_error
    try:
        response = await async_client.get("/api/health/db")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.json() == {"status": "error", "database": "disconnected"}
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_security_headers(async_client: AsyncClient) -> None:
    """Test that baseline security headers are present in responses."""
    response = await async_client.get("/api/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert response.headers.get("X-Frame-Options") == "DENY"


@pytest.mark.asyncio
async def test_not_found_error_format(async_client: AsyncClient) -> None:
    """Test that 404 errors return the standardized error payload."""
    response = await async_client.get("/api/nonexistent-route")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
