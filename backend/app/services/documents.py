"""Document service — Sprint 3 (upgraded from Sprint 2).

Handles the full upload + processing pipeline:
  1. Compute SHA-256 of the raw file bytes.
  2. Build a safe storage key and persist the file via the storage backend.
  3. Insert a Document row (status = queued).
  4. Insert a ProcessingJob row (status = queued).
  5. Run the processing worker:
     a. Extract plain text from the stored file bytes.
     b. Split text into fixed-size chunks with overlap.
     c. Fetch Gemini embeddings for each chunk (async, batched).
     d. Persist DocumentChunk rows with embeddings.
     e. Mark the document and job as completed/ready.

Text extraction is intentionally simple (plain UTF-8 decode with fallback).
Complex PDF/OCR parsing is deferred to a later sprint.

Embedding calls are made to Google Gemini via app/providers/embeddings.py.
Tests can substitute a mock provider to avoid real API calls.
"""
import hashlib
import re
import uuid as _uuid
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession

import app.storage.local as _storage_module
from app.db.models.documents import Document, DocumentChunk
from app.db.models.jobs import ProcessingJob
from app.db.models.users import User
from app.providers import EmbeddingProvider
from app.providers.embeddings import get_embedding_provider
from app.storage import StorageInterface

# ---------------------------------------------------------------------------
# Chunking parameters
# ---------------------------------------------------------------------------
CHUNK_SIZE = 512      # characters per chunk
CHUNK_OVERLAP = 64    # character overlap between consecutive chunks


def _safe_filename(name: str) -> str:
    """Strip path components and replace non-safe characters."""
    basename = PurePosixPath(name).name
    safe = re.sub(r"[^\w.\-]", "_", basename)
    return safe or "upload"


def _storage_key(workspace_id: _uuid.UUID, doc_id: _uuid.UUID, filename: str) -> str:
    return f"workspaces/{workspace_id}/docs/{doc_id}/{_safe_filename(filename)}"


def _extract_text(data: bytes, mime_type: str | None) -> str:
    """Extract plain text from raw file bytes.

    Strategy:
    - Try UTF-8 decode first (covers plain text, CSV, Markdown, HTML, etc.)
    - Fall back to latin-1 (lossless byte-level decode).
    Future: route to PDF/DOCX parsers based on mime_type.
    """
    try:
        return data.decode("utf-8")
    except (UnicodeDecodeError, ValueError):
        return data.decode("latin-1", errors="replace")


def _split_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split *text* into fixed-length chunks with *overlap* character overlap.

    Returns at least one chunk even for very short texts.
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    chunks: list[str] = []
    step = chunk_size - overlap
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start += step

    return chunks


async def _process_document(
    db: AsyncSession,
    doc: Document,
    job: ProcessingJob,
    data: bytes,
    embedding_provider: EmbeddingProvider,
) -> None:
    """Core processing pipeline: extract → chunk → embed → store.

    Mutates *doc* and *job* in place; caller is responsible for commit.
    """
    # Stage: extracting
    doc.status = "processing"
    doc.processing_stage = "extracting"
    doc.processing_progress = 10
    job.status = "running"
    job.stage = "extracting"
    await db.flush()

    text = _extract_text(data, doc.mime_type)
    chunks_text = _split_chunks(text)

    if not chunks_text:
        # Empty file — still mark ready, just no chunks
        _mark_complete(doc, job, chunk_count=0)
        return

    # Stage: indexing — fetch embeddings
    doc.processing_stage = "indexing"
    doc.processing_progress = 50
    job.stage = "indexing"
    await db.flush()

    vectors = await embedding_provider.embed(chunks_text)

    # Persist chunks
    for i, (chunk_text, vector) in enumerate(zip(chunks_text, vectors)):
        chunk_hash = hashlib.sha256(chunk_text.encode()).hexdigest()
        chunk = DocumentChunk(
            document_id=doc.id,
            chunk_index=i,
            raw_text=chunk_text,
            contextual_text=chunk_text,
            chunk_hash=chunk_hash,
            embedding=vector,
        )
        db.add(chunk)

    _mark_complete(doc, job, chunk_count=len(chunks_text))


def _mark_complete(doc: Document, job: ProcessingJob, chunk_count: int) -> None:
    now = datetime.now(tz=timezone.utc)
    doc.status = "ready"
    doc.processing_stage = "ready"
    doc.processing_progress = 100

    job.status = "completed"
    job.stage = "ready"
    job.progress = 100
    job.message = f"Processing complete. {chunk_count} chunk(s) indexed."
    job.started_at = job.started_at or now
    job.finished_at = now


async def create_document_from_upload(
    db: AsyncSession,
    uploader: User,
    workspace_id: _uuid.UUID,
    filename: str,
    content_type: str | None,
    data: bytes,
    storage: StorageInterface | None = None,
    embedding_provider: EmbeddingProvider | None = None,
) -> tuple[Document, ProcessingJob]:
    """Save a file, create a Document + ProcessingJob, run the processing pipeline.

    Returns (document, job) after processing completes.

    *storage* defaults to the module-level singleton; pass a different instance
    in tests to redirect I/O to a temp directory.

    *embedding_provider* defaults to the Gemini singleton; pass a mock in
    tests to avoid real API calls.
    """
    _storage = storage if storage is not None else _storage_module.storage
    _embedder = embedding_provider if embedding_provider is not None else get_embedding_provider()

    doc_id = _uuid.uuid4()
    doc_hash = hashlib.sha256(data).hexdigest()
    storage_key = _storage_key(workspace_id, doc_id, filename)

    # 1. Persist raw bytes to disk
    await _storage.save(storage_key, data, content_type)

    # 2. Insert Document (queued)
    doc = Document(
        id=doc_id,
        workspace_id=workspace_id,
        name=_safe_filename(filename),
        mime_type=content_type,
        size_bytes=len(data),
        status="queued",
        storage_key=storage_key,
        document_hash=doc_hash,
        uploaded_by=uploader.id,
    )
    db.add(doc)
    await db.flush()

    # 3. Insert ProcessingJob (queued)
    job = ProcessingJob(
        document_id=doc_id,
        status="queued",
        attempt=1,
    )
    db.add(job)
    await db.flush()

    # 4. Run the processing pipeline
    try:
        await _process_document(db, doc, job, data, _embedder)
    except Exception as exc:
        doc.status = "failed"
        doc.error_message = str(exc)
        job.status = "failed"
        job.error_message = str(exc)

    await db.commit()
    await db.refresh(doc)
    await db.refresh(job)

    return doc, job
