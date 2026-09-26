"""Sprint 0 acceptance tests — health endpoint."""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.db.session import get_db
from app.main import app


import pytest_asyncio

@pytest_asyncio.fixture()
async def client():
    engine = create_async_engine(settings.database_url, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()


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
