"""Document service — Sprint 2.

Handles the full upload transaction:
  1. Compute SHA-256 of the raw file bytes.
  2. Build a safe storage key and persist the file via the storage backend.
  3. Insert a Document row (status = queued).
  4. Insert a ProcessingJob row (status = queued).
  5. Run the mock worker synchronously — marks the job completed and the
     document ready. Real async processing is wired in Sprint 3.

All storage and DB work happens inside a single async function that can be
called from any route that has already verified permissions.
"""
import hashlib
import re
import uuid as _uuid
from datetime import datetime, timezone
from pathlib import PurePosixPath

from sqlalchemy.ext.asyncio import AsyncSession

import app.storage.local as _storage_module
from app.db.models.documents import Document
from app.db.models.jobs import ProcessingJob
from app.db.models.users import User
from app.storage import StorageInterface


def _safe_filename(name: str) -> str:
    """Strip path components and replace non-safe characters."""
    basename = PurePosixPath(name).name  # drop any directory prefix
    safe = re.sub(r"[^\w.\-]", "_", basename)
    return safe or "upload"


def _storage_key(workspace_id: _uuid.UUID, doc_id: _uuid.UUID, filename: str) -> str:
    return f"workspaces/{workspace_id}/docs/{doc_id}/{_safe_filename(filename)}"


async def create_document_from_upload(
    db: AsyncSession,
    uploader: User,
    workspace_id: _uuid.UUID,
    filename: str,
    content_type: str | None,
    data: bytes,
    storage: StorageInterface | None = None,
) -> tuple[Document, ProcessingJob]:
    """Save a file, create a Document + ProcessingJob, run the mock worker.

    Returns (document, job) after the mock worker has completed both records.

    *storage* defaults to the module-level singleton; pass a different instance
    in tests to redirect I/O to a temp directory.
    """
    _storage = storage if storage is not None else _storage_module.storage
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
    await db.flush()  # gives doc.created_at from the server default

    # 3. Insert ProcessingJob (queued)
    job = ProcessingJob(
        document_id=doc_id,
        status="queued",
        attempt=1,
    )
    db.add(job)
    await db.flush()

    # 4. Mock worker — synchronously marks job completed + document ready
    #    Real background processing is introduced in Sprint 3.
    now = datetime.now(tz=timezone.utc)
    job.status = "completed"
    job.stage = "ready"
    job.progress = 100
    job.message = "Mock worker: file stored, processing deferred to Sprint 3."
    job.started_at = now
    job.finished_at = now

    doc.status = "ready"
    doc.processing_stage = "ready"
    doc.processing_progress = 100

    await db.commit()
    await db.refresh(doc)
    await db.refresh(job)

    return doc, job
