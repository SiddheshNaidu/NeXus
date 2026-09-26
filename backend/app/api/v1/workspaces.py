"""Workspace endpoints — Sprint 1.

GET /workspaces              — list all workspaces the caller belongs to.
GET /workspaces/{id}         — get a single workspace (caller must be a member).
GET /workspaces/{id}/collections — list collections in a workspace (viewer+).
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.models.users import User
from app.db.models.workspaces import Collection
from app.db.session import get_db
from app.schemas.workspaces import CollectionRead, WorkspaceWithRole
from app.services.permissions import (
    Role,
    get_workspace_or_404,
    list_user_workspaces,
    require_workspace_role,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get(
    "",
    response_model=list[WorkspaceWithRole],
    summary="List workspaces",
    description="Returns all workspaces the authenticated user belongs to.",
)
async def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WorkspaceWithRole]:
    pairs = await list_user_workspaces(db, current_user)
    return [
        WorkspaceWithRole(
            id=ws.id,
            name=ws.name,
            mode=ws.mode,
            created_at=ws.created_at,
            role=member.role,
        )
        for ws, member in pairs
    ]


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceWithRole,
    summary="Get workspace",
    description="Returns a workspace. Caller must be a member.",
)
async def get_workspace(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceWithRole:
    membership = await require_workspace_role(db, current_user, workspace_id, Role.VIEWER)
    workspace = await get_workspace_or_404(db, workspace_id)
    return WorkspaceWithRole(
        id=workspace.id,
        name=workspace.name,
        mode=workspace.mode,
        created_at=workspace.created_at,
        role=membership.role,
    )


@router.get(
    "/{workspace_id}/collections",
    response_model=list[CollectionRead],
    summary="List collections",
    description="Returns all collections in a workspace. Requires viewer role.",
)
async def list_collections(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CollectionRead]:
    await require_workspace_role(db, current_user, workspace_id, Role.VIEWER)
    result = await db.execute(
        select(Collection).where(Collection.workspace_id == workspace_id)
    )
    collections = result.scalars().all()
    return [CollectionRead.model_validate(c) for c in collections]
