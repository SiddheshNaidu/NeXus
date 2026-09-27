"""seed_test_data.py — seed deterministic dev users, workspaces, and memberships.

UUIDs are fixed so the frontend hardcoded test-user list always matches the DB.

Idempotency strategy
--------------------
Users   — conflict target is EMAIL (the stable natural key).
          ON CONFLICT (email) DO UPDATE SET id = EXCLUDED.id, name = EXCLUDED.name
          This overwrites any stale random UUID from a previous seed run with the
          correct fixed UUID, sidestepping the ix_users_email unique-index trap
          that breaks a plain ON CONFLICT (id) DO NOTHING when the email already
          exists under a different id.

Workspaces   — ON CONFLICT (id) DO NOTHING  (no other unique constraint).
Memberships  — ON CONFLICT (workspace_id, user_id) DO NOTHING.

Run from the backend/ directory:
    python seed_test_data.py          # seed / repair (idempotent)
    python seed_test_data.py --reset  # hard-delete all seed rows then re-insert

Fixed UUIDs (must stay in sync with frontend/src/components/ui/navbar.tsx):
    Alice  (admin)       00000000-0000-0000-0000-000000000001
    Bob    (contributor) 00000000-0000-0000-0000-000000000002
    Carol  (viewer)      00000000-0000-0000-0000-000000000003
    Workspace Alpha      00000000-0000-0000-0000-000000000010
    Workspace Beta       00000000-0000-0000-0000-000000000011
    Workspace Gamma      00000000-0000-0000-0000-000000000012
"""
import asyncio
import sys
import uuid

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.models.users import User
from app.db.models.workspaces import Workspace, WorkspaceMember

# ── Fixed seed identities ─────────────────────────────────────────────────────
# These UUIDs are the single source of truth.
# The frontend navbar.tsx DEV_TEST_USERS list references the same values.

ALICE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
BOB_ID   = uuid.UUID("00000000-0000-0000-0000-000000000002")
CAROL_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")

ALPHA_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")
BETA_ID  = uuid.UUID("00000000-0000-0000-0000-000000000011")
GAMMA_ID = uuid.UUID("00000000-0000-0000-0000-000000000012")

USERS = [
    {"id": ALICE_ID, "name": "Alice",  "email": "alice@nexus.local"},
    {"id": BOB_ID,   "name": "Bob",    "email": "bob@nexus.local"},
    {"id": CAROL_ID, "name": "Carol",  "email": "carol@nexus.local"},
]

WORKSPACES = [
    {"id": ALPHA_ID, "name": "Workspace Alpha", "mode": "personal"},
    {"id": BETA_ID,  "name": "Workspace Beta",  "mode": "personal"},
    {"id": GAMMA_ID, "name": "Workspace Gamma", "mode": "organization"},
]

MEMBERSHIPS = [
    # Alice is admin of Alpha and contributor of Gamma
    {"workspace_id": ALPHA_ID, "user_id": ALICE_ID, "role": "admin"},
    {"workspace_id": GAMMA_ID, "user_id": ALICE_ID, "role": "contributor"},
    # Bob is contributor of Alpha and Beta
    {"workspace_id": ALPHA_ID, "user_id": BOB_ID,   "role": "contributor"},
    {"workspace_id": BETA_ID,  "user_id": BOB_ID,   "role": "contributor"},
    # Carol is viewer of Alpha only
    {"workspace_id": ALPHA_ID, "user_id": CAROL_ID, "role": "viewer"},
]


async def reset(session: AsyncSession) -> None:
    """Hard-delete all seed rows so the next insert starts from a blank slate.

    Deletes by BOTH id and email so orphaned rows from the old random-UUID seed
    are also removed even if their IDs don't match the fixed constants.
    """
    seed_user_ids    = [u["id"]    for u in USERS]
    seed_user_emails = [u["email"] for u in USERS]
    seed_ws_ids      = [w["id"]    for w in WORKSPACES]

    # Memberships first (FK constraint)
    await session.execute(
        delete(WorkspaceMember).where(WorkspaceMember.user_id.in_(seed_user_ids))
    )
    await session.execute(
        delete(Workspace).where(Workspace.id.in_(seed_ws_ids))
    )
    # Delete by id OR email to catch old random-UUID rows sharing the same email
    await session.execute(
        delete(User).where(
            User.id.in_(seed_user_ids) | User.email.in_(seed_user_emails)
        )
    )
    await session.commit()
    print("[seed] Existing seed rows removed.")


async def seed(session: AsyncSession) -> None:
    """Upsert seed rows — safe to run against a database in any prior state.

    Users conflict on EMAIL (the stable natural key) and overwrite the id and
    name columns.  This repairs databases that were seeded with the old
    random-UUID script: the stale row's UUID is replaced with the fixed one in
    a single atomic statement, avoiding the ix_users_email unique-index error
    that a plain ON CONFLICT (id) DO NOTHING would raise.
    """

    # Users — conflict on email, overwrite id + name with the canonical values
    await session.execute(
        pg_insert(User)
        .values(USERS)
        .on_conflict_do_update(
            index_elements=["email"],
            set_={"id": pg_insert(User).excluded.id, "name": pg_insert(User).excluded.name},
        )
    )

    # Workspaces — ON CONFLICT (id) DO NOTHING (id is the only unique key)
    await session.execute(
        pg_insert(Workspace).values(WORKSPACES).on_conflict_do_nothing(index_elements=["id"])
    )

    # Memberships — ON CONFLICT (workspace_id, user_id) DO NOTHING
    await session.execute(
        pg_insert(WorkspaceMember)
        .values(MEMBERSHIPS)
        .on_conflict_do_nothing(index_elements=["workspace_id", "user_id"])
    )

    await session.commit()


async def main(do_reset: bool) -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        if do_reset:
            await reset(session)
        await seed(session)

    await engine.dispose()

    print("[seed] Done.")
    print()
    print("  Dev users (use these UUIDs in X-Dev-User-ID / frontend login):")
    print(f"    Alice  (admin)        {ALICE_ID}")
    print(f"    Bob    (contributor)  {BOB_ID}")
    print(f"    Carol  (viewer)       {CAROL_ID}")
    print()
    print("  Workspaces:")
    print(f"    Alpha  (personal)     {ALPHA_ID}")
    print(f"    Beta   (personal)     {BETA_ID}")
    print(f"    Gamma  (organization) {GAMMA_ID}")
    print()
    print("  Memberships:")
    print("    Alice  → Alpha (admin), Gamma (contributor)")
    print("    Bob    → Alpha (contributor), Beta (contributor)")
    print("    Carol  → Alpha (viewer)")


if __name__ == "__main__":
    do_reset = "--reset" in sys.argv
    asyncio.run(main(do_reset))
