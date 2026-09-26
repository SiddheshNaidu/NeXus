"""Conversation schemas — locked contract for Sprint 0."""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ConversationRead(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageRead(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    result_json: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
