"""Sprint 2 acceptance tests — Upload and Processing Jobs.

Acceptance criteria:
  ✓ A file can be uploaded → file saved on disk.
  ✓ Correct Document and ProcessingJob DB records are created.
  ✓ Viewer is strictly blocked from uploading (HTTP 403).
"""
import io
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.documents import Document
from app.db.models.jobs import ProcessingJob

pytest_plugins = ("tests.conftest_sprint2",)

_FAKE_PDF = b"%PDF-1.4 fake content for testing"
_FAKE_TXT = b"Hello, NEXUS."


# ---------------------------------------------------------------------------
# Upload success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contributor_can_upload(client: AsyncClient, seed2, tmp_path):
    """Contributor uploads a file → 201 with document + job IDs."""
    resp = await client.post(
        f"/api/v1/workspaces/{seed2.workspace_a.id}/documents",
        headers={"X-Dev-User-ID": str(seed2.user_c.id)},
        files={"file": ("test.pdf", io.BytesIO(_FAKE_PDF), "application/pdf")},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "document" in body
    assert "job_id" in body
    assert body["document"]["status"] == "ready"
    assert body["document"]["name"] == "test.pdf"
    assert body["document"]["mime_type"] == "application/pdf"
    assert body["document"]["workspace_id"] == str(seed2.workspace_a.id)


@pytest.mark.asyncio
async def test_upload_saves_file_on_disk(client: AsyncClient, seed2, tmp_path: Path):
    """The raw file bytes must be persisted under the temp storage root.

    The client fixture creates a LocalStorage rooted at tmp_path/storage and
    injects it via the get_storage dependency override. We verify by checking
    the filesystem directly via tmp_path.
    """
    resp = await client.post(
        f"/api/v1/workspaces/{seed2.workspace_a.id}/documents",
        headers={"X-Dev-User-ID": str(seed2.user_c.id)},
        files={"file": ("report.txt", io.BytesIO(_FAKE_TXT), "text/plain")},
    )
    assert resp.status_code == 201
    storage_key = resp.json()["document"]["storage_key"]
    # The client fixture roots LocalStorage at tmp_path/storage
    expected_path = tmp_path / "storage" / storage_key
    assert expected_path.exists(), f"Expected file at {expected_path}"
    assert expected_path.read_bytes() == _FAKE_TXT


@pytest.mark.asyncio
async def test_upload_creates_document_db_record(
    client: AsyncClient, seed2, db_session: AsyncSession
):
    """A Document row must exist in the DB after upload."""
    resp = await client.post(
        f"/api/v1/workspaces/{seed2.workspace_a.id}/documents",
        headers={"X-Dev-User-ID": str(seed2.user_c.id)},
        files={"file": ("doc.pdf", io.BytesIO(_FAKE_PDF), "application/pdf")},
    )
    assert resp.status_code == 201
    doc_id = uuid.UUID(resp.json()["document"]["id"])

    result = await db_session.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    assert doc is not None
    assert doc.workspace_id == seed2.workspace_a.id
    assert doc.uploaded_by == seed2.user_c.id
    assert doc.size_bytes == len(_FAKE_PDF)
    assert doc.document_hash is not None  # SHA-256 was computed


@pytest.mark.asyncio
async def test_upload_creates_processing_job_db_record(
    client: AsyncClient, seed2, db_session: AsyncSession
):
    """A ProcessingJob row must exist in the DB after upload."""
    resp = await client.post(
        f"/api/v1/workspaces/{seed2.workspace_a.id}/documents",
        headers={"X-Dev-User-ID": str(seed2.user_c.id)},
        files={"file": ("doc2.pdf", io.BytesIO(_FAKE_PDF), "application/pdf")},
    )
    assert resp.status_code == 201
    job_id = uuid.UUID(resp.json()["job_id"])
    doc_id = uuid.UUID(resp.json()["document"]["id"])

    result = await db_session.execute(
        select(ProcessingJob).where(ProcessingJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    assert job is not None
    assert job.document_id == doc_id
    assert job.status == "completed"   # mock worker ran
    assert job.attempt == 1


# ---------------------------------------------------------------------------
# Permission enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_viewer_blocked_from_upload(client: AsyncClient, seed2):
    """Critical: Viewer must receive 403 — never allowed to upload."""
    resp = await client.post(
        f"/api/v1/workspaces/{seed2.workspace_a.id}/documents",
        headers={"X-Dev-User-ID": str(seed2.user_v.id)},
        files={"file": ("secret.pdf", io.BytesIO(_FAKE_PDF), "application/pdf")},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_unauthenticated_upload_blocked(client: AsyncClient, seed2):
    """No X-Dev-User-ID header → 401."""
    resp = await client.post(
        f"/api/v1/workspaces/{seed2.workspace_a.id}/documents",
        files={"file": ("x.pdf", io.BytesIO(_FAKE_PDF), "application/pdf")},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_nonmember_upload_blocked(client: AsyncClient, seed2, db_session: AsyncSession):
    """A user with no membership in the workspace must be blocked (403)."""
    stranger = __import__("app.db.models.users", fromlist=["User"]).User(
        id=uuid.uuid4(), name="Stranger", email=f"stranger+{uuid.uuid4()}@test.local"
    )
    db_session.add(stranger)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/workspaces/{seed2.workspace_a.id}/documents",
        headers={"X-Dev-User-ID": str(stranger.id)},
        files={"file": ("x.pdf", io.BytesIO(_FAKE_PDF), "application/pdf")},
    )
    assert resp.status_code == 403

    # cleanup
    from sqlalchemy import delete as _delete
    from app.db.models.users import User as _User
    await db_session.execute(_delete(_User).where(_User.id == stranger.id))
    await db_session.commit()


# ---------------------------------------------------------------------------
# Status endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_endpoint_returns_document_state(client: AsyncClient, seed2):
    """GET /documents/{id}/status returns processing state for a viewer."""
    # Upload as contributor
    upload_resp = await client.post(
        f"/api/v1/workspaces/{seed2.workspace_a.id}/documents",
        headers={"X-Dev-User-ID": str(seed2.user_c.id)},
        files={"file": ("status_test.pdf", io.BytesIO(_FAKE_PDF), "application/pdf")},
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["document"]["id"]

    # Poll status as viewer
    status_resp = await client.get(
        f"/api/v1/documents/{doc_id}/status",
        headers={"X-Dev-User-ID": str(seed2.user_v.id)},
    )
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["document_id"] == doc_id
    assert body["status"] == "ready"
    assert body["stage"] == "ready"
    assert body["progress"] == 100
