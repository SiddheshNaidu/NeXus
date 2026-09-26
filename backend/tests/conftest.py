"""Base test fixtures shared across all sprints.

conftest.py is auto-loaded by pytest for all tests in tests/.
Only put fixtures here that are truly sprint-agnostic.

Sprint-specific fixtures (including 'client') live in conftest_sprintN.py
and are loaded per test file via pytest_plugins.
"""
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings


@pytest_asyncio.fixture()
async def db_session():
    """Generic per-test DB session (NullPool). Used by tests that need DB
    access but are not sprint-specific."""
    engine = create_async_engine(settings.database_url, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()
