"""FastAPI authorization dependencies — Sprint 1.

These are thin wrappers around the permission service that integrate with
FastAPI's Depends() system. Routes declare which minimum role they need by
depending on require_viewer, require_contributor, or require_admin.

Usage:
    @router.get("/workspaces/{workspace_id}/sensitive")
    async def sensitive(
        workspace_id: uuid.UUID,
        membership: WorkspaceMember = Depends(require_contributor(workspace_id)),
    ): ...

Or use the factory directly for dynamic role requirements:
    membership = await require_workspace_role(db, user, workspace_id, Role.ADMIN)
"""
import uuid

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.models.users import User
from app.db.models.workspaces import WorkspaceMember
from app.db.session import get_db
from app.services.permissions import Role, require_workspace_role


def require_viewer(workspace_id: uuid.UUID) -> object:
    """Dependency factory: caller must be at least a viewer."""
    async def dep(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> WorkspaceMember:
        return await require_workspace_role(db, user, workspace_id, Role.VIEWER)
    return dep


def require_contributor(workspace_id: uuid.UUID) -> object:
    """Dependency factory: caller must be at least a contributor."""
    async def dep(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> WorkspaceMember:
        return await require_workspace_role(db, user, workspace_id, Role.CONTRIBUTOR)
    return dep


def require_admin(workspace_id: uuid.UUID) -> object:
    """Dependency factory: caller must be an admin."""
    async def dep(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> WorkspaceMember:
        return await require_workspace_role(db, user, workspace_id, Role.ADMIN)
    return dep
