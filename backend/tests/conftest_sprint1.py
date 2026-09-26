"""Sprint 1 test fixtures.

Strategy: each test gets a completely independent async engine + NullPool session.
NullPool means no connection is ever reused between tests, eliminating the
asyncpg "transaction in error state" bleed-through from a shared pool.

Seed layout:
  user_a  is ADMIN   of workspace_a
  user_a  is VIEWER  of workspace_b
  user_b  is ADMIN   of workspace_b
  user_b  has NO access to workspace_a  ← critical isolation row
"""
import uuid as _uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.db.models.users import User
from app.db.models.workspaces import Collection, Workspace, WorkspaceMember
from app.db.session import get_db
from app.main import app


class SeedData:
    user_a: User
    user_b: User
    workspace_a: Workspace   # user_a = ADMIN
    workspace_b: Workspace   # user_b = ADMIN, user_a = VIEWER


@pytest_asyncio.fixture()
async def db_session():
    """Per-test engine+session. NullPool — no connection reuse across tests."""
    engine = create_async_engine(settings.database_url, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture()
async def seed(db_session: AsyncSession) -> SeedData:
    """Insert rows, yield, delete them after the test regardless of outcome."""
    s = SeedData()

    s.user_a = User(id=_uuid.uuid4(), name="Alice", email=f"alice+{_uuid.uuid4()}@test.local")
    s.user_b = User(id=_uuid.uuid4(), name="Bob",   email=f"bob+{_uuid.uuid4()}@test.local")
    s.workspace_a = Workspace(id=_uuid.uuid4(), name="Workspace A", mode="personal")
    s.workspace_b = Workspace(id=_uuid.uuid4(), name="Workspace B", mode="personal")
    db_session.add_all([s.user_a, s.user_b, s.workspace_a, s.workspace_b])
    await db_session.flush()

    db_session.add(WorkspaceMember(workspace_id=s.workspace_a.id, user_id=s.user_a.id, role="admin"))
    db_session.add(WorkspaceMember(workspace_id=s.workspace_b.id, user_id=s.user_b.id, role="admin"))
    db_session.add(WorkspaceMember(workspace_id=s.workspace_b.id, user_id=s.user_a.id, role="viewer"))
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
            delete(User).where(User.id.in_([s.user_a.id, s.user_b.id]))
        )
        await db_session.commit()


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession):
    """AsyncClient wired to the test's db_session for the get_db dependency."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
