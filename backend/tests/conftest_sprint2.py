"""Sprint 2 test fixtures.

Extends the Sprint 1 seed with:
  - user_c who is CONTRIBUTOR of workspace_a
  - user_v who is VIEWER     of workspace_a

Storage is injected by overriding the get_storage FastAPI dependency.
The active storage instance is stored in _active_storage so tests can
verify disk contents via conftest_sprint2._active_storage.
"""
import uuid as _uuid
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.v1.documents import get_storage
from app.core.config import settings
from app.db.models.users import User
from app.db.models.workspaces import Workspace, WorkspaceMember
from app.db.session import get_db
from app.main import app
from app.storage.local import LocalStorage

# Module-level slot: holds the per-test LocalStorage during a test run.
# Tests read this to verify disk I/O.
_active_storage: LocalStorage | None = None


class SeedData2:
    user_c: User       # contributor of workspace_a
    user_v: User       # viewer     of workspace_a
    workspace_a: Workspace


@pytest_asyncio.fixture()
async def db_session():
    engine = create_async_engine(settings.database_url, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture()
async def seed2(db_session: AsyncSession) -> SeedData2:
    s = SeedData2()
    s.user_c = User(id=_uuid.uuid4(), name="Carol",  email=f"carol+{_uuid.uuid4()}@test.local")
    s.user_v = User(id=_uuid.uuid4(), name="Victor", email=f"victor+{_uuid.uuid4()}@test.local")
    s.workspace_a = Workspace(id=_uuid.uuid4(), name="Sprint2 Workspace", mode="personal")

    db_session.add_all([s.user_c, s.user_v, s.workspace_a])
    await db_session.flush()

    db_session.add(WorkspaceMember(workspace_id=s.workspace_a.id, user_id=s.user_c.id, role="contributor"))
    db_session.add(WorkspaceMember(workspace_id=s.workspace_a.id, user_id=s.user_v.id, role="viewer"))
    await db_session.commit()

    try:
        yield s
    finally:
        await db_session.execute(
            delete(WorkspaceMember).where(WorkspaceMember.workspace_id == s.workspace_a.id)
        )
        await db_session.execute(delete(Workspace).where(Workspace.id == s.workspace_a.id))
        await db_session.execute(
            delete(User).where(User.id.in_([s.user_c.id, s.user_v.id]))
        )
        await db_session.commit()


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession, tmp_path: Path):
    """AsyncClient with get_db and get_storage dependency overrides.

    Sets conftest_sprint2._active_storage to the temp LocalStorage so tests
    can check disk I/O via:
        import tests.conftest_sprint2 as cs2
        await cs2._active_storage.exists(key)
    """
    global _active_storage
    ts = LocalStorage(root=str(tmp_path / "storage"))
    _active_storage = ts

    async def override_get_db():
        yield db_session

    def override_get_storage():
        return ts

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = override_get_storage

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_storage, None)
    _active_storage = None
