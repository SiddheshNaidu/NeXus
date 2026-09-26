"""Identity endpoints — Sprint 1.

GET /me  — returns the authenticated user and all workspaces they belong to.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.models.users import User
from app.db.session import get_db
from app.schemas.users import MeResponse, UserRead
from app.schemas.workspaces import WorkspaceWithRole
from app.services.permissions import list_user_workspaces

router = APIRouter()


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Current user",
    description="Returns the authenticated user and their workspace memberships.",
)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    pairs = await list_user_workspaces(db, current_user)

    workspaces = [
        WorkspaceWithRole(
            id=ws.id,
            name=ws.name,
            mode=ws.mode,
            created_at=ws.created_at,
            role=member.role,
        )
        for ws, member in pairs
    ]

    return MeResponse(
        user=UserRead.model_validate(current_user),
        workspaces=workspaces,
    )
