"""Evidence schemas — locked contract for Sprint 0."""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class EvidenceRead(BaseModel):
    id: uuid.UUID
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    page_number: int | None = None
    section: str | None = None
    text: str
    relevance_score: float | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
