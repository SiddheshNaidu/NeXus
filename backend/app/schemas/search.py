"""Search schemas — Sprint 0 locked contract + Sprint 3 additions."""
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


# ---------------------------------------------------------------------------
# Sprint 3 — vector similarity search result schemas
# ---------------------------------------------------------------------------

class ChunkSearchResult(BaseModel):
    """A single chunk returned by a vector similarity search."""
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    chunk_index: int
    text: str
    score: float  # cosine similarity [0, 1]; higher = more relevant


class ChunkSearchResponse(BaseModel):
    """Response envelope for GET /workspaces/{id}/search."""
    query: str
    results: list[ChunkSearchResult]
