"""Sprint 3 test fixtures.

Extends the Sprint 2 seed with two isolated workspaces for cross-tenant
isolation testing:
  - workspace_a: user_c (contributor), user_v (viewer)
  - workspace_b: user_b (contributor) — separate tenant

A MockEmbeddingProvider is provided so tests never call the real Gemini API.
Vectors are deterministic: each call returns a unit vector in the direction
[chunk_index, 0, 0, ...] so similarity scores are reproducible.
"""
import math
import uuid as _uuid
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.v1.documents import get_embedder, get_storage
from app.api.v1.workspaces import get_embedder as ws_get_embedder
from app.core.config import settings
from app.db.models.users import User
from app.db.models.workspaces import Workspace, WorkspaceMember
from app.db.session import get_db
from app.main import app
from app.providers import EmbeddingProvider
from app.storage.local import LocalStorage


# ---------------------------------------------------------------------------
# Mock embedding provider
# ---------------------------------------------------------------------------

class MockEmbeddingProvider(EmbeddingProvider):
    """Returns deterministic unit vectors; never calls Gemini.

    All texts map to the same unit vector so query↔chunk cosine similarity
    is 1.0 in tests.  This keeps retrieval above the adaptive absolute floor
    while still exercising the full search SQL path.  Threshold filtering
    itself is covered by a dedicated hand-crafted-vector test.
    """

    DIMENSION = 1536

    def __init__(self) -> None:
        self._call_count = 0

    @property
    def dimension(self) -> int:
        return self.DIMENSION

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self._call_count += len(texts)
        unit = [0.0] * self.DIMENSION
        unit[0] = 1.0
        return [list(unit) for _ in texts]


def _unit_vec(idx: int, dim: int = 1536) -> list[float]:
    """Return a unit vector with 1.0 at position *idx*."""
    v = [0.0] * dim
    v[idx % dim] = 1.0
    return v


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

class SeedData3:
    # Workspace A
    user_c: User         # contributor of workspace_a
    user_v: User         # viewer     of workspace_a
    workspace_a: Workspace

    # Workspace B (separate tenant)
    user_b: User         # contributor of workspace_b
    workspace_b: Workspace


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def db_session():
    engine = create_async_engine(settings.database_url, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture()
async def seed3(db_session: AsyncSession) -> SeedData3:
    s = SeedData3()

    # Workspace A users
    s.user_c = User(id=_uuid.uuid4(), name="Carol3",  email=f"carol3+{_uuid.uuid4()}@test.local")
    s.user_v = User(id=_uuid.uuid4(), name="Victor3", email=f"victor3+{_uuid.uuid4()}@test.local")
    s.workspace_a = Workspace(id=_uuid.uuid4(), name="Sprint3 Workspace A", mode="personal")

    # Workspace B — different tenant
    s.user_b = User(id=_uuid.uuid4(), name="Bob3", email=f"bob3+{_uuid.uuid4()}@test.local")
    s.workspace_b = Workspace(id=_uuid.uuid4(), name="Sprint3 Workspace B", mode="personal")

    db_session.add_all([s.user_c, s.user_v, s.workspace_a, s.user_b, s.workspace_b])
    await db_session.flush()

    db_session.add(WorkspaceMember(workspace_id=s.workspace_a.id, user_id=s.user_c.id, role="contributor"))
    db_session.add(WorkspaceMember(workspace_id=s.workspace_a.id, user_id=s.user_v.id, role="viewer"))
    db_session.add(WorkspaceMember(workspace_id=s.workspace_b.id, user_id=s.user_b.id, role="contributor"))
    await db_session.commit()

    try:
        yield s
    finally:
        await db_session.execute(
            delete(WorkspaceMember).where(
                WorkspaceMember.workspace_id.in_([s.workspace_a.id, s.workspace_b.id])
            )
        )
        await db_session.execute(
            delete(Workspace).where(Workspace.id.in_([s.workspace_a.id, s.workspace_b.id]))
        )
        await db_session.execute(
            delete(User).where(User.id.in_([s.user_c.id, s.user_v.id, s.user_b.id]))
        )
        await db_session.commit()


# Module-level storage slot (mirrors Sprint 2 pattern)
_active_storage: LocalStorage | None = None


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession, tmp_path: Path):
    """AsyncClient with overridden get_db, get_storage, and both get_embedder deps."""
    global _active_storage
    ts = LocalStorage(root=str(tmp_path / "storage"))
    _active_storage = ts
    mock_embedder = MockEmbeddingProvider()

    async def override_get_db():
        yield db_session

    def override_get_storage():
        return ts

    def override_get_embedder():
        return mock_embedder

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = override_get_storage
    app.dependency_overrides[get_embedder] = override_get_embedder
    app.dependency_overrides[ws_get_embedder] = override_get_embedder

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_storage, None)
    app.dependency_overrides.pop(get_embedder, None)
    app.dependency_overrides.pop(ws_get_embedder, None)
    _active_storage = None
