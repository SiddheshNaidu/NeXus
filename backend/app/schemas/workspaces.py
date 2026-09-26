"""Workspace schemas — Sprint 1 (extends Sprint 0 contract)."""
import uuid
from datetime import datetime

from pydantic import BaseModel


class WorkspaceRead(BaseModel):
    id: uuid.UUID
    name: str
    mode: str
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceWithRole(WorkspaceRead):
    """Workspace plus the caller's role — used in /me and /workspaces."""
    role: str


class CollectionRead(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MembershipRead(BaseModel):
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}
