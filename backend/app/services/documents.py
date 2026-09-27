"""Document service — Sprint 3+ (multi-format chunking router).

Handles the full upload + processing pipeline:
  1. Validate MIME type — raise ValidationError (422) for unsupported types.
  2. Compute SHA-256 of the raw file bytes.
  3. Build a safe storage key and persist the file via the storage backend.
  4. Insert a Document row (status = queued).
  5. Insert a ProcessingJob row (status = queued).
  6. Run the processing worker:
     a. Extract plain text / structural chunks from the stored file bytes.
     b. Strip null bytes to prevent PostgreSQL UTF-8 encoding errors.
     c. Route to the appropriate chunker based on MIME type.
     d. Fetch Gemini embeddings for each chunk (async, batched).
     e. Persist DocumentChunk rows with embeddings, section, and metadata.
     f. Mark the document and job as completed/ready.

Chunking strategy by MIME type
───────────────────────────────
  text/plain, application/pdf
      → RecursiveCharacterTextSplitter (character-level, no structural context)
        Separators tried in order: "\\n\\n", "\\n", " ", ""
        chunk_size=512, chunk_overlap=64

  application/vnd.openxmlformats-officedocument.wordprocessingml.document
      → Document-Structure-Aware chunker
        Paragraphs are grouped under their nearest Heading 1 / Heading 2
        ancestor; each group is recursively split at the character level.
        Every resulting Chunk carries section=<heading text> and
        metadata_json={"section": <heading>, "heading_level": 1|2}.

  image/*
      → No text extraction; document stored with 0 chunks.

Embedding calls are made to Google Gemini via app/providers/embeddings.py.
Tests can substitute a mock provider to avoid real API calls.
"""
import asyncio
import hashlib
import io
import re
import uuid as _uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.storage.local as _storage_module
from app.core.errors import ValidationError
from app.db.models.documents import Document, DocumentChunk
from app.db.models.jobs import ProcessingJob
from app.db.models.users import User
from app.providers import EmbeddingProvider
from app.providers.embeddings import get_embedding_provider
from app.storage import StorageInterface

# ---------------------------------------------------------------------------
# Supported MIME types
# ---------------------------------------------------------------------------

_SUPPORTED_MIME_TYPES: frozenset[str] = frozenset({
    "text/plain",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/png",
    "image/jpeg",
    "image/webp",
})

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# ---------------------------------------------------------------------------
# Chunking parameters
# ---------------------------------------------------------------------------
CHUNK_SIZE = 512      # characters per chunk
CHUNK_OVERLAP = 64    # character overlap between consecutive chunks

# Separators tried in order by the recursive splitter (mirrors LangChain's
# RecursiveCharacterTextSplitter defaults for plain prose).
_SEPARATORS = ["\n\n", "\n", " ", ""]


# ---------------------------------------------------------------------------
# Internal chunk representation
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    """A single piece of text ready for embedding.

    Attributes:
        text:     The chunk content (null bytes already stripped).
        section:  The heading this chunk belongs to, or None.
                  Maps directly to DocumentChunk.section.
        metadata: Arbitrary key/value pairs stored in metadata_json.
                  Always includes {"section": ...} when section is set.
    """
    text: str
    section: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _safe_filename(name: str) -> str:
    """Strip path components and replace non-safe characters."""
    basename = PurePosixPath(name).name
    safe = re.sub(r"[^\w.\-]", "_", basename)
    return safe or "upload"


def _storage_key(workspace_id: _uuid.UUID, doc_id: _uuid.UUID, filename: str) -> str:
    return f"workspaces/{workspace_id}/docs/{doc_id}/{_safe_filename(filename)}"


def _strip_nulls(text: str) -> str:
    """Remove null bytes that would break PostgreSQL UTF-8 encoding."""
    return text.replace("\x00", "")


# ---------------------------------------------------------------------------
# Text extraction (unchanged from previous sprint)
# ---------------------------------------------------------------------------

def _extract_text(data: bytes, mime_type: str | None) -> str:
    """Extract plain text from *data* using a parser appropriate for *mime_type*.

    Routing:
      text/plain   → UTF-8 decode, latin-1 fallback
      application/pdf → pdfplumber page extraction
      application/vnd…docx → python-docx paragraph join (flat text)
      image/*      → returns "" (no text; document stored with 0 chunks)

    The result always has null bytes stripped before returning so that
    PostgreSQL never receives an invalid UTF-8 sequence (\\x00).

    Any parse failure (corrupt / truncated binary) is caught and returns ""
    so the pipeline marks the document ready with 0 chunks rather than
    crashing the job.

    Note: For DOCX files the *chunking* pipeline calls _chunk_docx() directly
    to preserve structural metadata; _extract_text() is retained for backwards
    compatibility and for tests that exercise it in isolation.
    """
    mt = (mime_type or "text/plain").lower().strip()
    raw: str

    if mt == "text/plain":
        try:
            raw = data.decode("utf-8")
        except (UnicodeDecodeError, ValueError):
            raw = data.decode("latin-1", errors="replace")

    elif mt == "application/pdf":
        try:
            import pdfplumber  # lazy import
            pages: list[str] = []
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    pages.append(page_text)
            raw = "\n".join(pages)
        except Exception:
            raw = ""

    elif mt == _DOCX_MIME:
        try:
            import docx  # python-docx — lazy import
            document = docx.Document(io.BytesIO(data))
            raw = "\n".join(p.text for p in document.paragraphs)
        except Exception:
            raw = ""

    elif mt.startswith("image/"):
        raw = ""

    else:
        raw = ""

    return _strip_nulls(raw)


# ---------------------------------------------------------------------------
# RecursiveCharacterTextSplitter  (native implementation — no langchain dep)
# ---------------------------------------------------------------------------

def _recursive_split(
    text: str,
    separators: list[str] | None = None,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """Split *text* recursively on a priority-ordered list of separators.

    Mirrors the behaviour of LangChain's RecursiveCharacterTextSplitter:
    - Tries each separator in *separators* in order.
    - If the text splits into pieces that still exceed *chunk_size*, each
      piece is recursively split using the next separator in the list.
    - Consecutive small splits are merged back together up to *chunk_size*,
      with *chunk_overlap* characters of context carried forward.
    - Falls back to a hard character split when no separator works.

    Returns a list of non-empty strings, each ≤ chunk_size characters
    (except when a single word/token is longer than chunk_size).
    """
    if separators is None:
        separators = _SEPARATORS

    if not text.strip():
        return []

    # ── 1. Find the first separator that actually splits this text ───────────
    chosen_sep: str = separators[-1]  # hard fallback: split character by char
    remaining_seps: list[str] = []

    for i, sep in enumerate(separators):
        if sep == "":
            chosen_sep = sep
            remaining_seps = []
            break
        if sep in text:
            chosen_sep = sep
            remaining_seps = separators[i + 1:]
            break

    # ── 2. Split on the chosen separator ─────────────────────────────────────
    splits = text.split(chosen_sep) if chosen_sep else list(text)

    # ── 3. Recursively refine any split that is still too long ───────────────
    good_splits: list[str] = []
    for piece in splits:
        piece = piece.strip()
        if not piece:
            continue
        if len(piece) <= chunk_size:
            good_splits.append(piece)
        elif remaining_seps:
            good_splits.extend(_recursive_split(piece, remaining_seps, chunk_size, chunk_overlap))
        else:
            # Absolute fallback: hard-cut at chunk_size
            step = chunk_size - chunk_overlap
            for start in range(0, len(piece), step):
                sub = piece[start: start + chunk_size]
                if sub.strip():
                    good_splits.append(sub)

    # ── 4. Merge small consecutive splits up to chunk_size with overlap ───────
    merged: list[str] = []
    current_parts: list[str] = []
    current_len = 0

    for part in good_splits:
        part_len = len(part)
        # +1 for the separator we'll rejoin with
        join_cost = 1 if current_parts else 0
        if current_len + join_cost + part_len > chunk_size and current_parts:
            # Flush the current window
            merged.append((chosen_sep if chosen_sep else " ").join(current_parts).strip())
            # Keep the overlap tail
            overlap_parts: list[str] = []
            overlap_len = 0
            for p in reversed(current_parts):
                if overlap_len + len(p) + 1 > chunk_overlap:
                    break
                overlap_parts.insert(0, p)
                overlap_len += len(p) + 1
            current_parts = overlap_parts
            current_len = overlap_len

        current_parts.append(part)
        current_len += part_len + (1 if len(current_parts) > 1 else 0)

    if current_parts:
        merged.append((chosen_sep if chosen_sep else " ").join(current_parts).strip())

    return [c for c in merged if c.strip()]


def _split_chunks(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """Public alias for the recursive splitter.

    Retained for backwards compatibility with tests that import this name
    directly.  Returns a plain list[str] (no section metadata).
    """
    return _recursive_split(text, chunk_size=chunk_size, chunk_overlap=overlap)


# ---------------------------------------------------------------------------
# DOCX structural chunker
# ---------------------------------------------------------------------------

# Heading style names recognised as section boundaries.
# python-docx reports style names like "Heading 1", "Heading 2", etc.
_HEADING_STYLES: frozenset[str] = frozenset({
    "heading 1",
    "heading 2",
})

# Maximum heading level captured as a section label.
# Headings deeper than this (H3+) are treated as body text.
_MAX_HEADING_LEVEL = 2


def _heading_level(style_name: str | None) -> int | None:
    """Return the heading level (1 or 2) for a recognised heading style, else None."""
    if not style_name:
        return None
    lower = style_name.lower().strip()
    if lower in _HEADING_STYLES:
        # "heading 1" → 1, "heading 2" → 2
        try:
            return int(lower.split()[-1])
        except (ValueError, IndexError):
            return None
    return None


def _chunk_docx(data: bytes) -> list[Chunk]:
    """Parse a DOCX file and produce structure-aware Chunk objects.

    Algorithm:
    1. Walk all paragraphs in document order.
    2. When a Heading 1 or Heading 2 paragraph is encountered, start a new
       section.  The heading text becomes the *section* label.
    3. Body paragraphs (non-headings) are accumulated under the current
       section.
    4. When the section changes (or at end of document), the accumulated
       body text is recursively split into Chunks, each labelled with the
       current section heading.
    5. Paragraphs before the first heading are collected under section=None.

    Returns [] for corrupt / unreadable DOCX files.
    """
    try:
        import docx  # python-docx — lazy import
        document = docx.Document(io.BytesIO(data))
    except Exception:
        return []

    chunks: list[Chunk] = []

    current_section: str | None = None
    current_heading_level: int | None = None
    current_body_parts: list[str] = []

    def _flush(section: str | None, level: int | None, body_parts: list[str]) -> None:
        """Split accumulated body text and append Chunks to *chunks*."""
        body_text = _strip_nulls("\n".join(body_parts).strip())
        if not body_text:
            return
        metadata: dict[str, Any] = {}
        if section:
            metadata["section"] = section
        if level is not None:
            metadata["heading_level"] = level
        for piece in _recursive_split(body_text):
            if piece.strip():
                chunks.append(Chunk(text=piece, section=section, metadata=metadata.copy()))

    for para in document.paragraphs:
        style_name = para.style.name if para.style else None
        level = _heading_level(style_name)
        para_text = _strip_nulls(para.text.strip())

        if level is not None and level <= _MAX_HEADING_LEVEL:
            # Flush body accumulated under the previous section
            _flush(current_section, current_heading_level, current_body_parts)
            current_body_parts = []
            # Start a new section; heading text itself becomes the label
            current_section = para_text or style_name
            current_heading_level = level
        else:
            # Ordinary body paragraph — accumulate under current section
            if para_text:
                current_body_parts.append(para_text)

    # Flush the final section
    _flush(current_section, current_heading_level, current_body_parts)

    return chunks


# ---------------------------------------------------------------------------
# Chunking dispatcher
# ---------------------------------------------------------------------------

def _chunk_document(data: bytes, mime_type: str | None) -> list[Chunk]:
    """Route *data* to the appropriate chunker and return a list of Chunk objects.

    Routing:
      text/plain, application/pdf
          → _extract_text() then _recursive_split() — no structural metadata
      application/vnd…docx
          → _chunk_docx() — structure-aware, section metadata preserved
      image/*
          → [] (stored with 0 chunks)
    """
    mt = (mime_type or "text/plain").lower().strip()

    if mt == _DOCX_MIME:
        return _chunk_docx(data)

    if mt.startswith("image/"):
        return []

    # text/plain, application/pdf — flat recursive split
    text = _extract_text(data, mime_type)
    if not text.strip():
        return []
    return [Chunk(text=piece) for piece in _recursive_split(text)]


# ---------------------------------------------------------------------------
# Processing pipeline
# ---------------------------------------------------------------------------

async def _process_document(
    db: AsyncSession,
    doc: Document,
    job: ProcessingJob,
    data: bytes,
    embedding_provider: EmbeddingProvider,
) -> None:
    """Core processing pipeline: chunk → embed → store (upsert by chunk_hash).

    Mutates *doc* and *job* in place; caller is responsible for commit.

    Re-upload safety: before inserting, existing chunks for this document are
    deleted so the set is always consistent with the current file content.
    Chunk identity is governed by chunk_hash (SHA-256 of chunk text), so if the
    same text reappears across re-uploads it is simply re-inserted — no ghost
    duplicates accumulate.
    """
    # Stage: extracting
    doc.status = "processing"
    doc.processing_stage = "extracting"
    doc.processing_progress = 10
    job.status = "running"
    job.stage = "extracting"
    await db.flush()

    # CPU-bound work: run chunking in a thread pool executor so the async event
    # loop is not blocked while parsing and splitting a large document.
    loop = asyncio.get_event_loop()
    chunks = await loop.run_in_executor(
        None, _chunk_document, data, doc.mime_type
    )

    if not chunks:
        # Empty file or image — still mark ready, just no chunks
        _mark_complete(doc, job, chunk_count=0)
        return

    # Stage: indexing — fetch embeddings
    doc.processing_stage = "indexing"
    doc.processing_progress = 50
    job.stage = "indexing"
    await db.flush()

    # Delete any stale chunks from a previous processing run for this document
    # (handles re-uploads and failed-then-retried jobs without ghost vectors).
    await db.execute(
        delete(DocumentChunk).where(DocumentChunk.document_id == doc.id)
    )
    await db.flush()

    chunk_texts = [c.text for c in chunks]
    vectors = await embedding_provider.embed(chunk_texts)

    # Persist chunks (vectors list may be shorter than chunks if some batches
    # failed — only persist the chunks for which we have a vector).
    persisted = 0
    for i, chunk in enumerate(chunks):
        if i >= len(vectors) or vectors[i] is None:
            # This chunk's embedding failed; skip it rather than aborting all.
            continue
        chunk_hash = hashlib.sha256(chunk.text.encode()).hexdigest()
        db_chunk = DocumentChunk(
            document_id=doc.id,
            chunk_index=i,
            raw_text=chunk.text,
            contextual_text=chunk.text,
            chunk_hash=chunk_hash,
            embedding=vectors[i],
            section=chunk.section,
            metadata_json=chunk.metadata if chunk.metadata else None,
        )
        db.add(db_chunk)
        persisted += 1

    _mark_complete(doc, job, chunk_count=persisted)


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


async def delete_document(
    db: AsyncSession,
    doc: Document,
    storage: StorageInterface | None = None,
) -> None:
    """Delete a document and all associated data.

    - Removes the stored file bytes from the storage backend (best-effort;
      a missing file is not a fatal error).
    - Deletes the Document row; all child rows (DocumentChunk, DocumentPage,
      ProcessingJob, Evidence via chunk FK) cascade via DB foreign keys.
    - Commits the transaction.
    """
    _storage = storage if storage is not None else _storage_module.storage

    # Remove stored file — ignore if not found (already cleaned up or never saved)
    if doc.storage_key:
        try:
            await _storage.delete(doc.storage_key)
        except Exception:
            pass  # Storage deletion is best-effort; DB state is authoritative

    # The Document row deletion cascades to DocumentChunk, DocumentPage,
    # ProcessingJob via ondelete="CASCADE" on their FK columns.
    await db.delete(doc)
    await db.commit()


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

    # ── MIME validation — fail fast before any storage or DB writes ───────────
    normalised_mime = (content_type or "").lower().strip()
    if normalised_mime not in _SUPPORTED_MIME_TYPES:
        raise ValidationError(
            f"Unsupported file type: '{content_type or 'unknown'}'. "
            "Accepted: text/plain, application/pdf, application/vnd."
            "openxmlformats-officedocument.wordprocessingml.document, "
            "image/png, image/jpeg, image/webp."
        )

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
