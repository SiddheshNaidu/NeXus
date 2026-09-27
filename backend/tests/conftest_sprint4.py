"""Sprint 4 test fixtures.

Two isolated workspaces for cross-tenant isolation testing:
  - workspace_a: user_a (contributor), user_v (viewer)
  - workspace_b: user_b (contributor) — separate tenant

MockEmbeddingProvider  — returns deterministic unit vectors (no Gemini calls).
MockLLMProvider        — returns a fixed canned reply (no Gemini calls).

All three FastAPI dependencies (get_db, get_embedder, get_llm) are overridden
on the shared FastAPI `app` instance and cleaned up after each test.
"""
import uuid as _uuid
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.v1.conversations import get_embedder, get_llm
from app.api.v1.documents import get_embedder as doc_get_embedder
from app.api.v1.documents import get_storage
from app.api.v1.workspaces import get_embedder as ws_get_embedder
from app.core.config import settings
from app.db.models.users import User
from app.db.models.workspaces import Workspace, WorkspaceMember
from app.db.session import get_db
from app.main import app
from app.providers import EmbeddingProvider, LLMProvider
from app.storage.local import LocalStorage


# ---------------------------------------------------------------------------
# Mock providers
# ---------------------------------------------------------------------------

class MockEmbeddingProvider(EmbeddingProvider):
    """Returns deterministic unit vectors — never calls Gemini.

    All texts map to the same unit vector so query↔chunk cosine similarity
    is 1.0, staying above the adaptive absolute floor used in production.
    """

    DIMENSION = 1536

    def __init__(self) -> None:
        self.call_count = 0

    @property
    def dimension(self) -> int:
        return self.DIMENSION

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.call_count += len(texts)
        unit = [0.0] * self.DIMENSION
        unit[0] = 1.0
        return [list(unit) for _ in texts]


class MockLLMProvider(LLMProvider):
    """Returns a fixed canned reply — never calls Gemini."""

    CANNED_REPLY = "This is a mock AI answer based on the provided evidence."

    def __init__(self) -> None:
        self.call_count = 0
        self.last_messages: list[dict] = []

    async def complete(self, messages: list[dict], **kwargs) -> str:
        self.call_count += 1
        self.last_messages = messages
        return self.CANNED_REPLY

    async def complete_structured(self, messages: list[dict], schema: type, **kwargs) -> dict:
        return {}


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

class SeedData4:
    user_a: User         # contributor of workspace_a
    user_v: User         # viewer of workspace_a
    workspace_a: Workspace

    user_b: User         # contributor of workspace_b (separate tenant)
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
async def seed4(db_session: AsyncSession) -> SeedData4:
    s = SeedData4()

    s.user_a = User(id=_uuid.uuid4(), name="Alice4",  email=f"alice4+{_uuid.uuid4()}@test.local")
    s.user_v = User(id=_uuid.uuid4(), name="Vera4",   email=f"vera4+{_uuid.uuid4()}@test.local")
    s.workspace_a = Workspace(id=_uuid.uuid4(), name="Sprint4 Workspace A", mode="personal")

    s.user_b = User(id=_uuid.uuid4(), name="Bob4",    email=f"bob4+{_uuid.uuid4()}@test.local")
    s.workspace_b = Workspace(id=_uuid.uuid4(), name="Sprint4 Workspace B", mode="personal")

    db_session.add_all([s.user_a, s.user_v, s.workspace_a, s.user_b, s.workspace_b])
    await db_session.flush()

    db_session.add(WorkspaceMember(workspace_id=s.workspace_a.id, user_id=s.user_a.id, role="contributor"))
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
            delete(User).where(User.id.in_([s.user_a.id, s.user_v.id, s.user_b.id]))
        )
        await db_session.commit()


# Module-level mocks — set during client fixture so individual tests can
# inspect call counts without passing mocks through fixture parameters.
_mock_embedder: MockEmbeddingProvider | None = None
_mock_llm: MockLLMProvider | None = None


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession, tmp_path: Path):
    """AsyncClient with all provider and storage dependencies mocked."""
    global _mock_embedder, _mock_llm

    ts = LocalStorage(root=str(tmp_path / "storage"))
    mock_embedder = MockEmbeddingProvider()
    mock_llm = MockLLMProvider()

    _mock_embedder = mock_embedder
    _mock_llm = mock_llm

    async def override_get_db():
        yield db_session

    def override_get_storage():
        return ts

    def override_get_embedder():
        return mock_embedder

    def override_get_llm():
        return mock_llm

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = override_get_storage
    # Documents upload embedder
    app.dependency_overrides[doc_get_embedder] = override_get_embedder
    # Workspace search embedder
    app.dependency_overrides[ws_get_embedder] = override_get_embedder
    # Conversation embedder + LLM
    app.dependency_overrides[get_embedder] = override_get_embedder
    app.dependency_overrides[get_llm] = override_get_llm

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_storage, None)
    app.dependency_overrides.pop(doc_get_embedder, None)
    app.dependency_overrides.pop(ws_get_embedder, None)
    app.dependency_overrides.pop(get_embedder, None)
    app.dependency_overrides.pop(get_llm, None)
    _mock_embedder = None
    _mock_llm = None
