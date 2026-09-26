"""seed_test_data.py — manually seed two users, two workspaces, and memberships.

Run from the backend root:
    python seed_test_data.py

Uses asyncio.run() + create_async_engine directly so it works outside of any
FastAPI request context (no UnboundExecutionError).
"""
import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.models.users import User
from app.db.models.workspaces import Workspace, WorkspaceMember


async def seed() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        alice_id = uuid.uuid4()
        bob_id   = uuid.uuid4()
        alpha_id = uuid.uuid4()
        beta_id  = uuid.uuid4()

        alice = User(id=alice_id, name="Alice", email="alice@nexus.local")
        bob   = User(id=bob_id,   name="Bob",   email="bob@nexus.local")
        alpha = Workspace(id=alpha_id, name="Workspace Alpha", mode="personal")
        beta  = Workspace(id=beta_id,  name="Workspace Beta",  mode="personal")

        session.add_all([alice, bob, alpha, beta])
        await session.flush()

        # Alice is Admin of Alpha
        session.add(WorkspaceMember(workspace_id=alpha_id, user_id=alice_id, role="admin"))
        # Bob is Viewer of Beta
        session.add(WorkspaceMember(workspace_id=beta_id,  user_id=bob_id,   role="viewer"))
        # Bob has NO membership in Alpha — isolation test

        await session.commit()

    await engine.dispose()

    print("Seed complete.")
    print(f"  Alice UUID : {alice_id}")
    print(f"  Bob   UUID : {bob_id}")
    print(f"  Alpha UUID : {alpha_id}")
    print(f"  Beta  UUID : {beta_id}")


if __name__ == "__main__":
    asyncio.run(seed())
