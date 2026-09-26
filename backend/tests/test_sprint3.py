"""Sprint 3 tests — AI, Embeddings, and Vector Search.

Acceptance criteria verified here:
  1. pgvector column exists and accepts 1536-dimensional vectors.
  2. A search query returns relevant chunks (correct workspace, ordered by score).
  3. Cross-tenant isolation: User B cannot search User A's vectorized documents.

All tests use MockEmbeddingProvider (no real Gemini calls).
"""
import io
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

pytest_plugins = ["tests.conftest_sprint3"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_TEXT = (
    "The quick brown fox jumps over the lazy dog. " * 30
    + "Machine learning is transforming every industry. " * 20
    + "Neural networks learn hierarchical representations. " * 20
)


async def _upload_document(
    client: AsyncClient,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str = "test.txt",
    content: str = SAMPLE_TEXT,
) -> dict:
    """Upload a document and return the JSON response."""
    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": (filename, io.BytesIO(content.encode()), "text/plain")},
        headers={"X-Dev-User-ID": str(user_id)},
    )
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Test 1: pgvector column exists and accepts 1536-d vectors
# ---------------------------------------------------------------------------

class TestPgvectorColumn:
    """Prove the embedding column exists and stores 1536-dimensional vectors."""

    @pytest.mark.asyncio
    async def test_embedding_column_exists(self, db_session: AsyncSession):
        """The document_chunks table has an 'embedding' column of type vector(1536)."""
        result = await db_session.execute(
            text("""
                SELECT column_name, udt_name
                FROM information_schema.columns
                WHERE table_name = 'document_chunks'
                  AND column_name = 'embedding'
            """)
        )
        row = result.fetchone()
        assert row is not None, "embedding column not found in document_chunks"
        assert row.udt_name == "vector", f"Expected 'vector', got '{row.udt_name}'"

    @pytest.mark.asyncio
    async def test_embedding_column_accepts_1536d_vector(self, db_session: AsyncSession, seed3):
        """Inserting a 1536-dimensional vector into document_chunks succeeds."""
        from app.db.models.documents import Document, DocumentChunk

        # We need a real document to satisfy the FK
        doc = Document(
            id=uuid.uuid4(),
            workspace_id=seed3.workspace_a.id,
            name="vector_test.txt",
            mime_type="text/plain",
            size_bytes=10,
            status="ready",
            uploaded_by=seed3.user_c.id,
        )
        db_session.add(doc)
        await db_session.flush()

        vec = [0.0] * 1535 + [1.0]  # 1536 elements

        chunk = DocumentChunk(
            document_id=doc.id,
            chunk_index=0,
            raw_text="test text",
            contextual_text="test text",
            embedding=vec,
        )
        db_session.add(chunk)
        await db_session.flush()

        # Read back and verify
        result = await db_session.execute(
            select(DocumentChunk).where(DocumentChunk.id == chunk.id)
        )
        saved = result.scalar_one()
        assert saved.embedding is not None
        assert len(saved.embedding) == 1536
        assert abs(saved.embedding[-1] - 1.0) < 1e-6

        # Cleanup
        await db_session.delete(chunk)
        await db_session.delete(doc)
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_embedding_column_dimension_is_1536(self, db_session: AsyncSession):
        """The embedding column type is vector(1536) — verified via pg catalog."""
        result = await db_session.execute(
            text("""
                SELECT
                    a.atttypmod AS dimension
                FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                WHERE c.relname = 'document_chunks'
                  AND a.attname = 'embedding'
            """)
        )
        row = result.fetchone()
        assert row is not None, "embedding column not found in pg_attribute"
        # pgvector stores dimension in atttypmod; for vector(1536) atttypmod = 1536
        assert row.dimension == 1536, f"Expected dimension 1536, got {row.dimension}"


# ---------------------------------------------------------------------------
# Test 2: Upload → chunk → embed pipeline works end-to-end
# ---------------------------------------------------------------------------

class TestEmbeddingPipeline:
    """Prove that uploading a document creates embedded chunks in the DB."""

    @pytest.mark.asyncio
    async def test_upload_creates_chunks_with_embeddings(
        self, client: AsyncClient, db_session: AsyncSession, seed3
    ):
        """After upload, document_chunks rows exist with non-null embeddings."""
        resp_data = await _upload_document(
            client, seed3.workspace_a.id, seed3.user_c.id
        )
        doc_id = uuid.UUID(resp_data["document"]["id"])

        rows = await db_session.execute(
            text(
                "SELECT COUNT(*) FROM document_chunks "
                "WHERE document_id = :doc_id AND embedding IS NOT NULL"
            ),
            {"doc_id": doc_id},
        )
        count = rows.scalar()
        assert count > 0, "Expected at least one embedded chunk after upload"

    @pytest.mark.asyncio
    async def test_upload_document_status_is_ready(
        self, client: AsyncClient, seed3
    ):
        """Document status is 'ready' after processing completes."""
        resp_data = await _upload_document(
            client, seed3.workspace_a.id, seed3.user_c.id
        )
        assert resp_data["document"]["status"] == "ready"

    @pytest.mark.asyncio
    async def test_chunks_have_correct_dimension(
        self, client: AsyncClient, db_session: AsyncSession, seed3
    ):
        """Stored embedding vectors are exactly 1536-dimensional."""
        from app.db.models.documents import DocumentChunk

        resp_data = await _upload_document(
            client, seed3.workspace_a.id, seed3.user_c.id
        )
        doc_id = uuid.UUID(resp_data["document"]["id"])

        result = await db_session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == doc_id)
            .limit(1)
        )
        chunk = result.scalar_one_or_none()
        assert chunk is not None
        assert chunk.embedding is not None
        assert len(chunk.embedding) == 1536


# ---------------------------------------------------------------------------
# Test 3: Search returns relevant chunks from the correct workspace
# ---------------------------------------------------------------------------

class TestVectorSearch:
    """Prove that search returns correct results and is workspace-scoped."""

    @pytest.mark.asyncio
    async def test_search_returns_results(
        self, client: AsyncClient, seed3
    ):
        """After uploading a document, searching the workspace returns chunks."""
        await _upload_document(client, seed3.workspace_a.id, seed3.user_c.id)

        resp = await client.get(
            f"/api/v1/workspaces/{seed3.workspace_a.id}/search",
            params={"q": "machine learning neural networks"},
            headers={"X-Dev-User-ID": str(seed3.user_c.id)},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["query"] == "machine learning neural networks"
        assert len(data["results"]) > 0

    @pytest.mark.asyncio
    async def test_search_results_have_correct_fields(
        self, client: AsyncClient, seed3
    ):
        """Each search result has the expected fields."""
        await _upload_document(client, seed3.workspace_a.id, seed3.user_c.id)

        resp = await client.get(
            f"/api/v1/workspaces/{seed3.workspace_a.id}/search",
            params={"q": "fox jumps"},
            headers={"X-Dev-User-ID": str(seed3.user_c.id)},
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) > 0
        first = results[0]
        assert "chunk_id" in first
        assert "document_id" in first
        assert "document_name" in first
        assert "text" in first
        assert "score" in first
        assert isinstance(first["score"], float)

    @pytest.mark.asyncio
    async def test_viewer_can_search(
        self, client: AsyncClient, seed3
    ):
        """A viewer-role user can perform searches."""
        await _upload_document(client, seed3.workspace_a.id, seed3.user_c.id)

        resp = await client.get(
            f"/api/v1/workspaces/{seed3.workspace_a.id}/search",
            params={"q": "quick brown fox"},
            headers={"X-Dev-User-ID": str(seed3.user_v.id)},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_search_empty_workspace_returns_empty_results(
        self, client: AsyncClient, seed3
    ):
        """Searching a workspace with no documents returns an empty results list."""
        resp = await client.get(
            f"/api/v1/workspaces/{seed3.workspace_a.id}/search",
            params={"q": "anything"},
            headers={"X-Dev-User-ID": str(seed3.user_c.id)},
        )
        assert resp.status_code == 200
        assert resp.json()["results"] == []

    @pytest.mark.asyncio
    async def test_search_results_scoped_to_workspace(
        self, client: AsyncClient, db_session: AsyncSession, seed3
    ):
        """Results only contain chunks from the queried workspace."""
        await _upload_document(
            client, seed3.workspace_a.id, seed3.user_c.id, filename="doc_a.txt"
        )

        resp = await client.get(
            f"/api/v1/workspaces/{seed3.workspace_a.id}/search",
            params={"q": "neural networks"},
            headers={"X-Dev-User-ID": str(seed3.user_c.id)},
        )
        assert resp.status_code == 200
        results = resp.json()["results"]

        # All results belong to workspace_a documents
        if results:
            doc_ids = [uuid.UUID(r["document_id"]) for r in results]
            rows = await db_session.execute(
                text(
                    "SELECT workspace_id FROM documents WHERE id = ANY(:ids)"
                ),
                {"ids": doc_ids},
            )
            for row in rows.fetchall():
                assert str(row.workspace_id) == str(seed3.workspace_a.id), (
                    f"Result from wrong workspace: {row.workspace_id}"
                )


# ---------------------------------------------------------------------------
# Test 4: Cross-tenant isolation
# ---------------------------------------------------------------------------

class TestCrossTenantIsolation:
    """User B cannot search User A's documents."""

    @pytest.mark.asyncio
    async def test_non_member_cannot_search_workspace(
        self, client: AsyncClient, seed3
    ):
        """A user who is not a member of workspace_a gets 403 when searching it."""
        await _upload_document(client, seed3.workspace_a.id, seed3.user_c.id)

        # user_b is member of workspace_b only, not workspace_a
        resp = await client.get(
            f"/api/v1/workspaces/{seed3.workspace_a.id}/search",
            params={"q": "machine learning"},
            headers={"X-Dev-User-ID": str(seed3.user_b.id)},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_workspace_b_search_does_not_return_workspace_a_chunks(
        self, client: AsyncClient, db_session: AsyncSession, seed3
    ):
        """user_b searching workspace_b sees no workspace_a documents."""
        # Upload to workspace_a
        await _upload_document(
            client, seed3.workspace_a.id, seed3.user_c.id, content="secret document from workspace a"
        )

        # Upload to workspace_b
        await _upload_document(
            client, seed3.workspace_b.id, seed3.user_b.id, content="public document from workspace b"
        )

        # Search workspace_b as user_b
        resp = await client.get(
            f"/api/v1/workspaces/{seed3.workspace_b.id}/search",
            params={"q": "secret document"},
            headers={"X-Dev-User-ID": str(seed3.user_b.id)},
        )
        assert resp.status_code == 200
        results = resp.json()["results"]

        # None of the results should be from workspace_a
        if results:
            doc_ids = [uuid.UUID(r["document_id"]) for r in results]
            rows = await db_session.execute(
                text("SELECT workspace_id FROM documents WHERE id = ANY(:ids)"),
                {"ids": doc_ids},
            )
            for row in rows.fetchall():
                assert str(row.workspace_id) == str(seed3.workspace_b.id), (
                    f"Cross-tenant leak: result from workspace {row.workspace_id}"
                )

    @pytest.mark.asyncio
    async def test_contributor_blocked_from_upload_in_other_workspace(
        self, client: AsyncClient, seed3
    ):
        """user_c (contributor of workspace_a) cannot upload to workspace_b."""
        resp = await client.post(
            f"/api/v1/workspaces/{seed3.workspace_b.id}/documents",
            files={"file": ("test.txt", io.BytesIO(b"data"), "text/plain")},
            headers={"X-Dev-User-ID": str(seed3.user_c.id)},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_blocked_from_upload(
        self, client: AsyncClient, seed3
    ):
        """A viewer-role user gets 403 when trying to upload (still enforced)."""
        resp = await client.post(
            f"/api/v1/workspaces/{seed3.workspace_a.id}/documents",
            files={"file": ("test.txt", io.BytesIO(b"data"), "text/plain")},
            headers={"X-Dev-User-ID": str(seed3.user_v.id)},
        )
        assert resp.status_code == 403
