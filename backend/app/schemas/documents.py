"""Document schemas — locked contract for Sprint 0."""
import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentBase(BaseModel):
    name: str
    mime_type: str | None = None


class DocumentRead(DocumentBase):
    id: uuid.UUID
    workspace_id: uuid.UUID
    collection_id: uuid.UUID | None = None
    size_bytes: int | None = None
    page_count: int | None = None
    status: str
    processing_stage: str | None = None
    processing_progress: int | None = None
    processing_route: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentStatusResponse(BaseModel):
    document_id: uuid.UUID
    status: str
    stage: str | None = None
    progress: int | None = None
    message: str | None = None
