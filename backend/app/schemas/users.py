"""User schemas — locked contract for Sprint 0."""
import uuid
from datetime import datetime

from pydantic import BaseModel


class UserRead(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}
