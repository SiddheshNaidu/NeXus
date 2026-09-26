"""Search schemas — locked contract for Sprint 0."""
import uuid
from typing import Any

from pydantic import BaseModel


class SearchRequest(BaseModel):
    workspace_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    query: str
    document_ids: list[uuid.UUID] = []
    collection_ids: list[uuid.UUID] = []


class EvidenceItem(BaseModel):
    id: str
    document_id: uuid.UUID
    document_name: str
    page: int | None = None
    section: str | None = None
    text: str


class SourceItem(BaseModel):
    document_id: uuid.UUID
    document_name: str
    page: int | None = None
    used: bool


class Claim(BaseModel):
    text: str
    evidence_ids: list[str]


class AnswerBody(BaseModel):
    text: str
    source_count: int


class SearchResponse(BaseModel):
    status: str  # answered | insufficient_evidence | conflict | no_results | error
    conversation_id: uuid.UUID | None = None
    answer: AnswerBody | None = None
    claims: list[Claim] = []
    sources: list[SourceItem] = []
    evidence: list[EvidenceItem] = []
    metadata: dict[str, Any] | None = None
