"""Workspace schemas — locked contract for Sprint 0."""
import uuid
from datetime import datetime

from pydantic import BaseModel


class WorkspaceRead(BaseModel):
    id: uuid.UUID
    name: str
    mode: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CollectionRead(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}
