"""Sprint 0 acceptance tests — health endpoint."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_response_shape(client: AsyncClient):
    response = await client.get("/api/v1/health")
    body = response.json()
    assert body["status"] == "ok"
    assert "timestamp" in body
    assert "version" in body
    assert "database" in body


@pytest.mark.asyncio
async def test_health_database_ok(client: AsyncClient):
    """Database must connect successfully for the health check."""
    response = await client.get("/api/v1/health")
    assert response.json()["database"] == "ok"


@pytest.mark.asyncio
async def test_openapi_schema_loads(client: AsyncClient):
    """OpenAPI schema must be accessible (docs load check)."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "NEXUS AI Evidence Intelligence Workspace"
    assert "/api/v1/health" in schema["paths"]
