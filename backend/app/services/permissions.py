"""Permission service — Sprint 1.

This is the single authoritative place for all permission checks.
Every protected route and service call must go through this module.

Rule (PRD §9): authenticate → resolve workspace → check membership → resolve permitted documents → perform operation.

Role hierarchy (PRD §8):
    viewer      — read access only
    contributor — viewer + upload + manage own documents + retry
    admin       — contributor + manage workspace (collections, users, access)
"""
import uuid
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError
from app.db.models.users import User
from app.db.models.workspaces import Workspace, WorkspaceMember


class Role(str, Enum):
    VIEWER = "viewer"
    CONTRIBUTOR = "contributor"
    ADMIN = "admin"


# Ordered from least to most privileged — used for hierarchy comparisons
_ROLE_RANK: dict[Role, int] = {
    Role.VIEWER: 0,
    Role.CONTRIBUTOR: 1,
    Role.ADMIN: 2,
}


def role_at_least(actual: str, required: Role) -> bool:
    """Return True if *actual* role satisfies the *required* minimum."""
    try:
        actual_role = Role(actual)
    except ValueError:
        return False
    return _ROLE_RANK[actual_role] >= _ROLE_RANK[required]


# ---------------------------------------------------------------------------
# Core service functions — call these from routes AND from other services
# ---------------------------------------------------------------------------


async def get_membership(
    db: AsyncSession,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> WorkspaceMember | None:
    """Return the WorkspaceMember row, or None if the user is not a member."""
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.workspace_id == workspace_id,
        )
    )
    return result.scalar_one_or_none()


async def get_workspace_or_404(
    db: AsyncSession,
    workspace_id: uuid.UUID,
) -> Workspace:
    """Load and return the Workspace, raising 404 if it does not exist."""
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise NotFoundError(f"Workspace {workspace_id} not found.")
    return workspace


async def require_workspace_role(
    db: AsyncSession,
    user: User,
    workspace_id: uuid.UUID,
    minimum_role: Role,
) -> WorkspaceMember:
    """Assert that *user* holds at least *minimum_role* in *workspace_id*.

    Raises:
        NotFoundError  — workspace does not exist
        ForbiddenError — user is not a member or role is insufficient
    Returns the WorkspaceMember row on success.

    This function is the reusable core — call it from services, not just routes.
    """
    await get_workspace_or_404(db, workspace_id)

    membership = await get_membership(db, user.id, workspace_id)
    if membership is None:
        raise ForbiddenError("You are not a member of this workspace.")

    if not role_at_least(membership.role, minimum_role):
        raise ForbiddenError(
            f"This action requires the '{minimum_role.value}' role. "
            f"Your role is '{membership.role}'."
        )

    return membership


async def list_user_workspaces(
    db: AsyncSession,
    user: User,
) -> list[tuple[Workspace, WorkspaceMember]]:
    """Return all (Workspace, WorkspaceMember) pairs for this user."""
    result = await db.execute(
        select(Workspace, WorkspaceMember)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user.id)
    )
    return result.all()  # type: ignore[return-value]
