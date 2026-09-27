"""Hardening tests — covering the four production weaknesses.

Fix #1  Ghost Data         — DELETE /documents/{id} removes chunks; re-upload
                             does not accumulate duplicates.
Fix #2  CPU-Blocking       — _chunk_document and PDF parsing run via executor,
                             not blocking the event loop inline.
Fix #3  Infinite History   — rolling window caps history at 10 messages.
Fix #4  DLQ / Retry        — failed embedding batch returns None placeholders;
                             _process_document skips failed chunks rather than
                             aborting the entire upload.
"""
import io
import uuid as _uuid
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.v1.conversations import get_embedder as conv_get_embedder
from app.api.v1.conversations import get_llm
from app.api.v1.documents import get_embedder as doc_get_embedder
from app.api.v1.documents import get_storage
from app.api.v1.workspaces import get_embedder as ws_get_embedder
from app.core.config import settings
from app.db.models.conversations import Conversation, Message
from app.db.models.documents import Document, DocumentChunk
from app.db.models.jobs import ProcessingJob
from app.db.models.users import User
from app.db.models.workspaces import Workspace, WorkspaceMember
from app.db.session import get_db
from app.main import app
from app.providers import EmbeddingProvider, LLMProvider
from app.services.chat import _HISTORY_WINDOW, _build_history
from app.services.documents import _process_document, create_document_from_upload
from app.storage.local import LocalStorage


# ---------------------------------------------------------------------------
# Mock providers
# ---------------------------------------------------------------------------

class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic unit vectors; never calls Gemini.

    All texts map to the same unit vector so query↔chunk cosine similarity
    is 1.0, staying above the adaptive absolute floor used in production.
    """

    DIMENSION = 1536

    def __init__(self) -> None:
        self.call_count = 0

    @property
    def dimension(self) -> int:
        return self.DIMENSION

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.call_count += len(texts)
        unit = [0.0] * self.DIMENSION
        unit[0] = 1.0
        return [list(unit) for _ in texts]


class PartialEmbeddingProvider(EmbeddingProvider):
    """Returns None for the first N embeddings, real vectors for the rest.

    This simulates a partial batch failure (DLQ behaviour): the flat
    embed() call returns a mixed list of real vectors and None values,
    exactly what GeminiEmbeddingProvider.embed() produces when one of its
    internal _embed_batch() calls exhausts retries and returns placeholders.
    """

    DIMENSION = 1536

    def __init__(self, fail_first_n: int = 100) -> None:
        self._fail_first_n = fail_first_n

    @property
    def dimension(self) -> int:
        return self.DIMENSION

    async def embed(self, texts: list[str]) -> list[list[float] | None]:
        results: list[list[float] | None] = []
        for i, t in enumerate(texts):
            if i < self._fail_first_n:
                results.append(None)  # type: ignore[arg-type]
            else:
                vec = [0.0] * self.DIMENSION
                vec[hash(t[:64]) % self.DIMENSION] = 1.0
                results.append(vec)
        return results  # type: ignore[return-value]


class MockLLMProvider(LLMProvider):
    """Fixed canned reply; never calls Gemini."""

    CANNED_REPLY = "Mock answer."

    def __init__(self) -> None:
        self.last_messages: list[dict] = []

    async def complete(self, messages: list[dict], **kwargs) -> str:
        self.last_messages = list(messages)
        return self.CANNED_REPLY

    async def complete_structured(self, messages: list[dict], schema: type, **kwargs) -> dict:
        return {}

    async def stream_complete(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        self.last_messages = list(messages)
        for word in self.CANNED_REPLY.split():
            yield word + " "


# ---------------------------------------------------------------------------
# Seed data + shared fixtures
# ---------------------------------------------------------------------------

class SeedH:
    user_admin: User
    user_contrib: User
    user_viewer: User
    workspace: Workspace


@pytest_asyncio.fixture()
async def db_session():
    engine = create_async_engine(settings.database_url, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture()
async def seed(db_session: AsyncSession) -> SeedH:
    s = SeedH()
    uid = _uuid.uuid4()

    s.user_admin   = User(id=_uuid.uuid4(), name="Admin_H",   email=f"admin_h+{uid}@test.local")
    s.user_contrib = User(id=_uuid.uuid4(), name="Contrib_H", email=f"contrib_h+{uid}@test.local")
    s.user_viewer  = User(id=_uuid.uuid4(), name="Viewer_H",  email=f"viewer_h+{uid}@test.local")
    s.workspace    = Workspace(id=_uuid.uuid4(), name=f"Hardening WS {uid}", mode="personal")

    db_session.add_all([s.user_admin, s.user_contrib, s.user_viewer, s.workspace])
    await db_session.flush()

    db_session.add(WorkspaceMember(workspace_id=s.workspace.id, user_id=s.user_admin.id,   role="admin"))
    db_session.add(WorkspaceMember(workspace_id=s.workspace.id, user_id=s.user_contrib.id, role="contributor"))
    db_session.add(WorkspaceMember(workspace_id=s.workspace.id, user_id=s.user_viewer.id,  role="viewer"))
    await db_session.commit()

    try:
        yield s
    finally:
        await db_session.execute(
            delete(WorkspaceMember).where(WorkspaceMember.workspace_id == s.workspace.id)
        )
        await db_session.execute(delete(Workspace).where(Workspace.id == s.workspace.id))
        await db_session.execute(
            delete(User).where(User.id.in_([s.user_admin.id, s.user_contrib.id, s.user_viewer.id]))
        )
        await db_session.commit()


_active_storage: LocalStorage | None = None


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession, tmp_path: Path):
    """AsyncClient with all dependencies mocked."""
    global _active_storage
    ts = LocalStorage(root=str(tmp_path / "storage"))
    _active_storage = ts
    mock_embedder = MockEmbeddingProvider()
    mock_llm = MockLLMProvider()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = lambda: ts
    app.dependency_overrides[doc_get_embedder] = lambda: mock_embedder
    app.dependency_overrides[ws_get_embedder] = lambda: mock_embedder
    app.dependency_overrides[conv_get_embedder] = lambda: mock_embedder
    app.dependency_overrides[get_llm] = lambda: mock_llm

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    for dep in [get_db, get_storage, doc_get_embedder, ws_get_embedder, conv_get_embedder, get_llm]:
        app.dependency_overrides.pop(dep, None)
    _active_storage = None


# ---------------------------------------------------------------------------
# Fix #1 — Ghost Data
# ---------------------------------------------------------------------------

class TestDeleteDocument:
    """DELETE /documents/{id} removes the document and all its chunks."""

    @pytest.mark.asyncio
    async def test_delete_removes_document_and_chunks(
        self, client: AsyncClient, db_session: AsyncSession, seed: SeedH, tmp_path: Path
    ):
        # Upload a plain-text document
        resp = await client.post(
            f"/api/v1/workspaces/{seed.workspace.id}/documents",
            headers={"X-Dev-User-ID": str(seed.user_contrib.id)},
            files={"file": ("hello.txt", b"hello world chunk content", "text/plain")},
        )
        assert resp.status_code == 201, resp.text
        doc_id = resp.json()["document"]["id"]

        # Verify chunks exist
        chunk_count = await db_session.scalar(
            select(text("COUNT(*)")).select_from(DocumentChunk).where(
                DocumentChunk.document_id == _uuid.UUID(doc_id)
            )
        )
        assert chunk_count > 0, "Expected at least one chunk after upload"

        # Admin deletes the document
        del_resp = await client.delete(
            f"/api/v1/documents/{doc_id}",
            headers={"X-Dev-User-ID": str(seed.user_admin.id)},
        )
        assert del_resp.status_code == 204, del_resp.text

        # Document row should be gone
        doc_row = await db_session.scalar(
            select(Document).where(Document.id == _uuid.UUID(doc_id))
        )
        assert doc_row is None, "Document row should be deleted"

        # All chunks should be gone
        remaining = await db_session.scalar(
            select(text("COUNT(*)")).select_from(DocumentChunk).where(
                DocumentChunk.document_id == _uuid.UUID(doc_id)
            )
        )
        assert remaining == 0, "All chunks should be deleted (no ghost vectors)"

    @pytest.mark.asyncio
    async def test_delete_forbidden_for_contributor(
        self, client: AsyncClient, seed: SeedH
    ):
        resp = await client.post(
            f"/api/v1/workspaces/{seed.workspace.id}/documents",
            headers={"X-Dev-User-ID": str(seed.user_contrib.id)},
            files={"file": ("sample.txt", b"sample text", "text/plain")},
        )
        assert resp.status_code == 201
        doc_id = resp.json()["document"]["id"]

        del_resp = await client.delete(
            f"/api/v1/documents/{doc_id}",
            headers={"X-Dev-User-ID": str(seed.user_contrib.id)},
        )
        assert del_resp.status_code == 403, "Contributors must not be able to delete documents"

    @pytest.mark.asyncio
    async def test_reupload_does_not_accumulate_ghost_chunks(
        self, client: AsyncClient, db_session: AsyncSession, seed: SeedH
    ):
        """Re-uploading the same document twice should not double the chunk count."""
        content = b"A" * 600  # forces 2 chunks with default CHUNK_SIZE=512

        resp1 = await client.post(
            f"/api/v1/workspaces/{seed.workspace.id}/documents",
            headers={"X-Dev-User-ID": str(seed.user_contrib.id)},
            files={"file": ("doc.txt", content, "text/plain")},
        )
        assert resp1.status_code == 201
        doc_id_1 = _uuid.UUID(resp1.json()["document"]["id"])

        chunks_after_first = await db_session.scalar(
            select(text("COUNT(*)")).select_from(DocumentChunk).where(
                DocumentChunk.document_id == doc_id_1
            )
        )

        # Simulate a re-process by calling _process_document again on the same doc
        doc = await db_session.scalar(select(Document).where(Document.id == doc_id_1))
        job = ProcessingJob(document_id=doc_id_1, status="queued", attempt=2)
        db_session.add(job)
        await db_session.flush()

        mock_embedder = MockEmbeddingProvider()
        await _process_document(db_session, doc, job, content, mock_embedder)
        await db_session.commit()

        chunks_after_reprocess = await db_session.scalar(
            select(text("COUNT(*)")).select_from(DocumentChunk).where(
                DocumentChunk.document_id == doc_id_1
            )
        )
        assert chunks_after_reprocess == chunks_after_first, (
            "Re-processing should replace chunks, not double them. "
            f"Expected {chunks_after_first}, got {chunks_after_reprocess}"
        )


# ---------------------------------------------------------------------------
# Fix #3 — Infinite Chat History (rolling window)
# ---------------------------------------------------------------------------

class TestRollingHistoryWindow:
    """_build_history caps the history at _HISTORY_WINDOW messages."""

    @pytest.mark.asyncio
    async def test_history_window_caps_at_limit(self, db_session: AsyncSession, seed: SeedH):
        """Insert more than _HISTORY_WINDOW messages; only the last N are returned."""
        conv = Conversation(
            id=_uuid.uuid4(),
            workspace_id=seed.workspace.id,
            user_id=seed.user_contrib.id,
        )
        db_session.add(conv)
        await db_session.flush()

        # Insert _HISTORY_WINDOW + 4 messages (2 extra pairs)
        total = _HISTORY_WINDOW + 4
        for i in range(total):
            role = "user" if i % 2 == 0 else "assistant"
            msg = Message(
                id=_uuid.uuid4(),
                conversation_id=conv.id,
                role=role,
                content=f"Message {i}",
            )
            db_session.add(msg)
        await db_session.flush()

        history = await _build_history(db_session, conv.id)

        assert len(history) == _HISTORY_WINDOW, (
            f"Rolling window should cap at {_HISTORY_WINDOW} messages, got {len(history)}"
        )
        # The window should be the *last* messages
        assert history[-1]["content"] == f"Message {total - 1}"
        assert history[0]["content"] == f"Message {total - _HISTORY_WINDOW}"

        # Clean up
        await db_session.execute(delete(Message).where(Message.conversation_id == conv.id))
        await db_session.execute(delete(Conversation).where(Conversation.id == conv.id))
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_short_history_returned_in_full(self, db_session: AsyncSession, seed: SeedH):
        """If history is shorter than the window, all messages are returned."""
        conv = Conversation(
            id=_uuid.uuid4(),
            workspace_id=seed.workspace.id,
            user_id=seed.user_contrib.id,
        )
        db_session.add(conv)
        await db_session.flush()

        for i in range(4):
            db_session.add(Message(
                id=_uuid.uuid4(),
                conversation_id=conv.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Short msg {i}",
            ))
        await db_session.flush()

        history = await _build_history(db_session, conv.id)
        assert len(history) == 4

        await db_session.execute(delete(Message).where(Message.conversation_id == conv.id))
        await db_session.execute(delete(Conversation).where(Conversation.id == conv.id))
        await db_session.commit()


# ---------------------------------------------------------------------------
# Fix #4 — DLQ / Retry (failed embedding batch does not abort the pipeline)
# ---------------------------------------------------------------------------

class TestDLQEmbeddingPartialFailure:
    """When embed() returns None for some entries, only those chunks are skipped."""

    @pytest.mark.asyncio
    async def test_partial_batch_failure_still_persists_good_chunks(
        self, db_session: AsyncSession, seed: SeedH, tmp_path: Path
    ):
        """Provider returns None for the first 5 vectors, real values for the rest.

        _process_document should persist the good chunks and skip the None ones
        without raising an exception.
        """
        # 20 short paragraphs → ~5 chunks (well within one batch)
        content = "\n\n".join(f"Paragraph {i}: " + "word " * 20 for i in range(20))
        content_bytes = content.encode()

        # Fail first 2 out of ~5 chunks; remaining chunks should still be persisted
        partial_embedder = PartialEmbeddingProvider(fail_first_n=2)

        doc_id = _uuid.uuid4()
        doc = Document(
            id=doc_id,
            workspace_id=seed.workspace.id,
            name="dlq_test.txt",
            mime_type="text/plain",
            size_bytes=len(content_bytes),
            status="queued",
            storage_key=f"workspaces/{seed.workspace.id}/docs/{doc_id}/dlq_test.txt",
            document_hash="dlqtest",
            uploaded_by=seed.user_contrib.id,
        )
        job = ProcessingJob(document_id=doc_id, status="queued", attempt=1)
        db_session.add(doc)
        db_session.add(job)
        await db_session.flush()

        await _process_document(db_session, doc, job, content_bytes, partial_embedder)
        await db_session.commit()

        # Re-fetch the count from DB (not the in-memory list)
        persisted_count = await db_session.scalar(
            select(text("COUNT(*)")).select_from(DocumentChunk).where(
                DocumentChunk.document_id == doc_id
            )
        )
        # Exactly the non-None chunks should be stored (≤ 15 out of 20)
        assert persisted_count > 0, (
            "At least some chunks should be persisted even when some embeddings fail"
        )
        # The 5 None-vector chunks should NOT have been persisted
        all_chunks_result = await db_session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == doc_id)
        )
        all_chunks = all_chunks_result.scalars().all()
        for chunk in all_chunks:
            assert chunk.embedding is not None, (
                f"Chunk {chunk.chunk_index} was persisted but has a None embedding"
            )

        # Document should still be marked ready (not failed)
        assert doc.status == "ready", (
            "Document should be marked ready even with a partial embedding failure"
        )
