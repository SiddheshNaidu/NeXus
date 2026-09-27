"""Document endpoints — Sprint 3 (upgraded from Sprint 2).

POST   /workspaces/{workspace_id}/documents  — upload a file (contributor+ only)
DELETE /documents/{document_id}              — delete document + cascade chunks (admin only)
GET    /documents/{document_id}/status       — poll processing state (viewer+)
GET    /documents/{document_id}              — fetch document record (viewer+)
"""
import uuid

from fastapi import APIRouter, Depends, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.storage.local as _storage_module
from app.core.errors import NotFoundError
from app.core.security import get_current_user
from app.db.models.documents import Document
from app.db.models.jobs import ProcessingJob
from app.db.models.users import User
from app.db.session import get_db
from app.providers import EmbeddingProvider
from app.providers.embeddings import get_embedding_provider as _get_provider
from app.schemas.documents import (
    DocumentRead,
    DocumentStatusResponse,
    DocumentUploadResponse,
    ProcessingJobRead,
)
from app.services.documents import create_document_from_upload, delete_document
from app.services.permissions import Role, require_workspace_role
from app.storage import StorageInterface

router = APIRouter(tags=["documents"])


def get_storage() -> StorageInterface:
    """FastAPI dependency — returns the active storage backend.

    Tests override this to inject a temp-dir storage instance.
    """
    return _storage_module.storage


def get_embedder() -> EmbeddingProvider:
    """FastAPI dependency — returns the active embedding provider.

    Tests override this to inject a mock that avoids real API calls.
    """
    return _get_provider()


@router.post(
    "/workspaces/{workspace_id}/documents",
    response_model=DocumentUploadResponse,
    status_code=201,
    summary="Upload document",
    description="Upload a file to a workspace. Requires Contributor or Admin role.",
)
async def upload_document(
    workspace_id: uuid.UUID,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: StorageInterface = Depends(get_storage),
    embedder: EmbeddingProvider = Depends(get_embedder),
) -> DocumentUploadResponse:
    # Permission check — contributor minimum
    await require_workspace_role(db, current_user, workspace_id, Role.CONTRIBUTOR)

    data = await file.read()
    doc, job = await create_document_from_upload(
        db=db,
        uploader=current_user,
        workspace_id=workspace_id,
        filename=file.filename or "upload",
        content_type=file.content_type,
        data=data,
        storage=storage,
        embedding_provider=embedder,
    )

    return DocumentUploadResponse(
        document=DocumentRead.model_validate(doc),
        job_id=job.id,
    )


@router.delete(
    "/documents/{document_id}",
    status_code=204,
    summary="Delete document",
    description=(
        "Permanently deletes a document and all its chunks, pages, and "
        "processing jobs. Cascades via DB foreign key. Requires Admin role."
    ),
)
async def delete_document_endpoint(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: StorageInterface = Depends(get_storage),
) -> Response:
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise NotFoundError(f"Document {document_id} not found.")

    # Only admins may delete documents
    await require_workspace_role(db, current_user, doc.workspace_id, Role.ADMIN)

    await delete_document(db, doc, storage)
    return Response(status_code=204)


@router.get(
    "/documents/{document_id}/status",
    response_model=DocumentStatusResponse,
    summary="Document processing status",
    description="Returns the current processing state. Requires Viewer role in the document's workspace.",
)
async def get_document_status(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentStatusResponse:
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise NotFoundError(f"Document {document_id} not found.")

    # Verify the caller can see this document's workspace
    await require_workspace_role(db, current_user, doc.workspace_id, Role.VIEWER)

    # Get the latest job for a human-readable message
    job_result = await db.execute(
        select(ProcessingJob)
        .where(ProcessingJob.document_id == document_id)
        .order_by(ProcessingJob.created_at.desc())
    )
    latest_job = job_result.scalars().first()

    return DocumentStatusResponse(
        document_id=doc.id,
        status=doc.status,
        stage=doc.processing_stage,
        progress=doc.processing_progress,
        message=latest_job.message if latest_job else None,
    )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentRead,
    summary="Get document",
    description="Returns the document record. Requires Viewer role in the document's workspace.",
)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentRead:
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise NotFoundError(f"Document {document_id} not found.")

    await require_workspace_role(db, current_user, doc.workspace_id, Role.VIEWER)
    return DocumentRead.model_validate(doc)
