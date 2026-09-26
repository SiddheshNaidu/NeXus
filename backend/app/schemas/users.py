"""User schemas — Sprint 1 (extends Sprint 0 contract)."""
import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.workspaces import WorkspaceWithRole


class UserRead(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MeResponse(BaseModel):
    """Response shape for GET /me."""
    user: UserRead
    workspaces: list[WorkspaceWithRole]
