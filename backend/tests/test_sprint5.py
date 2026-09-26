"""Sprint 5 tests — Streaming AI Chat Responses.

Acceptance criteria verified here:
  1. The streaming endpoint returns HTTP 200 with a streaming body.
  2. The stream yields the evidence payload (first event) followed by
     multiple text chunk events and a final done event.
  3. After the stream is fully consumed, the database contains:
       - The full user message (role="user")
       - The complete aggregated assistant message (role="assistant")
       - Evidence rows linked to the workspace's document chunks
  4. Cross-tenant isolation: 403 if a user accesses another user's conversation
     via the streaming endpoint.
"""
import io
import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

import tests.conftest_sprint5 as cs5

pytest_plugins = ["tests.conftest_sprint5"]

SAMPLE_CONTENT = (
    "Artificial intelligence is transforming industries worldwide. " * 30
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _upload_doc(client: AsyncClient, workspace_id: uuid.UUID, user_id: uuid.UUID) -> dict:
    resp = await client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("doc.txt", io.BytesIO(SAMPLE_CONTENT.encode()), "text/plain")},
        headers={"X-Dev-User-ID": str(user_id)},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_conversation(
    client: AsyncClient, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> dict:
    resp = await client.post(
        f"/api/v1/workspaces/{workspace_id}/conversations",
        headers={"X-Dev-User-ID": str(user_id)},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _stream_message(
    client: AsyncClient,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    content: str = "What is artificial intelligence?",
):
    """POST to the streaming endpoint and return the raw response."""
    return await client.post(
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        json={"content": content},
        headers={"X-Dev-User-ID": str(user_id)},
    )


def _parse_sse_events(body: str) -> list[dict]:
    """Parse a raw SSE body (``data: <json>\\n\\n`` lines) into a list of dicts."""
    events = []
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("data: "):
            payload = line[len("data: "):]
            events.append(json.loads(payload))
    return events


# ---------------------------------------------------------------------------
# Test 1: HTTP 200 + streaming body
# ---------------------------------------------------------------------------

class TestStreamingEndpointBasic:

    @pytest.mark.asyncio
    async def test_stream_returns_200(self, client: AsyncClient, seed5):
        """The streaming endpoint returns HTTP 200."""
        conv = await _create_conversation(client, seed5.workspace_a.id, seed5.user_a.id)
        resp = await _stream_message(client, uuid.UUID(conv["id"]), seed5.user_a.id)
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_stream_content_type_is_event_stream(self, client: AsyncClient, seed5):
        """Response Content-Type contains text/event-stream."""
        conv = await _create_conversation(client, seed5.workspace_a.id, seed5.user_a.id)
        resp = await _stream_message(client, uuid.UUID(conv["id"]), seed5.user_a.id)
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_stream_body_is_not_empty(self, client: AsyncClient, seed5):
        """The response body is non-empty (stream produced at least one event)."""
        conv = await _create_conversation(client, seed5.workspace_a.id, seed5.user_a.id)
        resp = await _stream_message(client, uuid.UUID(conv["id"]), seed5.user_a.id)
        assert resp.status_code == 200
        assert len(resp.content) > 0


# ---------------------------------------------------------------------------
# Test 2: Event sequence — evidence first, then text chunks, then done
# ---------------------------------------------------------------------------

class TestStreamEventSequence:

    @pytest.mark.asyncio
    async def test_first_event_is_evidence(self, client: AsyncClient, seed5):
        """The first SSE event has type='evidence'."""
        await _upload_doc(client, seed5.workspace_a.id, seed5.user_a.id)
        conv = await _create_conversation(client, seed5.workspace_a.id, seed5.user_a.id)
        resp = await _stream_message(client, uuid.UUID(conv["id"]), seed5.user_a.id)
        assert resp.status_code == 200

        events = _parse_sse_events(resp.text)
        assert len(events) >= 1, "No SSE events found"
        assert events[0]["type"] == "evidence", f"First event type was: {events[0]['type']}"

    @pytest.mark.asyncio
    async def test_evidence_event_has_chunks_key(self, client: AsyncClient, seed5):
        """The evidence event contains a 'chunks' list."""
        await _upload_doc(client, seed5.workspace_a.id, seed5.user_a.id)
        conv = await _create_conversation(client, seed5.workspace_a.id, seed5.user_a.id)
        resp = await _stream_message(client, uuid.UUID(conv["id"]), seed5.user_a.id)
        assert resp.status_code == 200

        events = _parse_sse_events(resp.text)
        assert events[0]["type"] == "evidence"
        assert "chunks" in events[0]
        assert isinstance(events[0]["chunks"], list)

    @pytest.mark.asyncio
    async def test_stream_contains_multiple_text_chunks(self, client: AsyncClient, seed5):
        """The stream yields more than one text chunk event (word-by-word mock)."""
        conv = await _create_conversation(client, seed5.workspace_a.id, seed5.user_a.id)
        resp = await _stream_message(client, uuid.UUID(conv["id"]), seed5.user_a.id)
        assert resp.status_code == 200

        events = _parse_sse_events(resp.text)
        text_events = [e for e in events if e.get("type") == "text"]
        assert len(text_events) > 1, (
            f"Expected multiple text events, got {len(text_events)}: {text_events}"
        )

    @pytest.mark.asyncio
    async def test_last_event_is_done(self, client: AsyncClient, seed5):
        """The final SSE event has type='done'."""
        conv = await _create_conversation(client, seed5.workspace_a.id, seed5.user_a.id)
        resp = await _stream_message(client, uuid.UUID(conv["id"]), seed5.user_a.id)
        assert resp.status_code == 200

        events = _parse_sse_events(resp.text)
        assert len(events) >= 1
        assert events[-1]["type"] == "done", f"Last event type was: {events[-1]['type']}"

    @pytest.mark.asyncio
    async def test_aggregated_text_matches_canned_reply(self, client: AsyncClient, seed5):
        """Concatenating all text chunks reconstructs the full canned reply."""
        conv = await _create_conversation(client, seed5.workspace_a.id, seed5.user_a.id)
        resp = await _stream_message(client, uuid.UUID(conv["id"]), seed5.user_a.id)
        assert resp.status_code == 200

        events = _parse_sse_events(resp.text)
        text_events = [e for e in events if e.get("type") == "text"]
        aggregated = "".join(e["text"] for e in text_events).strip()
        assert aggregated == cs5.MockStreamingLLMProvider.CANNED_REPLY, (
            f"Aggregated text did not match canned reply.\nGot: {aggregated!r}"
        )

    @pytest.mark.asyncio
    async def test_evidence_chunks_have_expected_fields(self, client: AsyncClient, seed5):
        """Each chunk in the evidence event contains required fields."""
        await _upload_doc(client, seed5.workspace_a.id, seed5.user_a.id)
        conv = await _create_conversation(client, seed5.workspace_a.id, seed5.user_a.id)
        resp = await _stream_message(client, uuid.UUID(conv["id"]), seed5.user_a.id)
        assert resp.status_code == 200

        events = _parse_sse_events(resp.text)
        evidence_event = events[0]
        assert evidence_event["type"] == "evidence"
        if evidence_event["chunks"]:
            chunk = evidence_event["chunks"][0]
            for field in ("chunk_id", "document_id", "document_name", "chunk_index", "text", "score"):
                assert field in chunk, f"Missing field '{field}' in evidence chunk"


# ---------------------------------------------------------------------------
# Test 3: Database persistence after stream
# ---------------------------------------------------------------------------

class TestDatabasePersistenceAfterStream:

    @pytest.mark.asyncio
    async def test_user_message_saved_to_db(
        self, client: AsyncClient, db_session: AsyncSession, seed5
    ):
        """A Message row with role='user' is committed to the DB after the stream."""
        from app.db.models.conversations import Message

        conv = await _create_conversation(client, seed5.workspace_a.id, seed5.user_a.id)
        conv_id = uuid.UUID(conv["id"])

        resp = await _stream_message(
            client, conv_id, seed5.user_a.id, content="Streaming question about AI."
        )
        assert resp.status_code == 200
        # Consume the full stream (resp.text) to ensure DB commit has happened
        _ = resp.text

        result = await db_session.execute(
            select(Message).where(
                Message.conversation_id == conv_id,
                Message.role == "user",
            )
        )
        user_msgs = result.scalars().all()
        assert len(user_msgs) == 1, f"Expected 1 user message, found {len(user_msgs)}"
        assert user_msgs[0].content == "Streaming question about AI."

    @pytest.mark.asyncio
    async def test_assistant_message_saved_to_db(
        self, client: AsyncClient, db_session: AsyncSession, seed5
    ):
        """A Message row with role='assistant' is committed after the stream finishes."""
        from app.db.models.conversations import Message

        conv = await _create_conversation(client, seed5.workspace_a.id, seed5.user_a.id)
        conv_id = uuid.UUID(conv["id"])

        resp = await _stream_message(client, conv_id, seed5.user_a.id)
        assert resp.status_code == 200
        _ = resp.text  # ensure stream fully consumed

        result = await db_session.execute(
            select(Message).where(
                Message.conversation_id == conv_id,
                Message.role == "assistant",
            )
        )
        assistant_msgs = result.scalars().all()
        assert len(assistant_msgs) == 1, f"Expected 1 assistant message, found {len(assistant_msgs)}"
        assert assistant_msgs[0].content == cs5.MockStreamingLLMProvider.CANNED_REPLY

    @pytest.mark.asyncio
    async def test_evidence_saved_to_db_after_stream(
        self, client: AsyncClient, db_session: AsyncSession, seed5
    ):
        """Evidence rows are committed to the DB after the stream completes."""
        await _upload_doc(client, seed5.workspace_a.id, seed5.user_a.id)
        conv = await _create_conversation(client, seed5.workspace_a.id, seed5.user_a.id)
        conv_id = uuid.UUID(conv["id"])

        resp = await _stream_message(client, conv_id, seed5.user_a.id)
        assert resp.status_code == 200
        _ = resp.text  # ensure stream fully consumed

        rows = await db_session.execute(
            text("""
                SELECT COUNT(*) FROM evidence ev
                JOIN document_chunks dc ON dc.id = ev.chunk_id
                JOIN documents d ON d.id = dc.document_id
                WHERE d.workspace_id = :ws_id
            """),
            {"ws_id": seed5.workspace_a.id},
        )
        count = rows.scalar()
        assert count > 0, "Expected at least one evidence row after streaming message"

    @pytest.mark.asyncio
    async def test_no_db_rows_without_docs_still_completes(
        self, client: AsyncClient, db_session: AsyncSession, seed5
    ):
        """Streaming works and DB is consistent even when no docs exist in workspace."""
        from app.db.models.conversations import Message

        conv = await _create_conversation(client, seed5.workspace_a.id, seed5.user_a.id)
        conv_id = uuid.UUID(conv["id"])

        resp = await _stream_message(client, conv_id, seed5.user_a.id)
        assert resp.status_code == 200
        _ = resp.text

        # Both user + assistant messages should be persisted
        result = await db_session.execute(
            select(Message).where(Message.conversation_id == conv_id)
        )
        all_msgs = result.scalars().all()
        roles = {m.role for m in all_msgs}
        assert "user" in roles
        assert "assistant" in roles

    @pytest.mark.asyncio
    async def test_full_aggregated_text_is_stored(
        self, client: AsyncClient, db_session: AsyncSession, seed5
    ):
        """The assistant message stored in DB is the fully aggregated text, not partial chunks."""
        from app.db.models.conversations import Message

        conv = await _create_conversation(client, seed5.workspace_a.id, seed5.user_a.id)
        conv_id = uuid.UUID(conv["id"])

        resp = await _stream_message(client, conv_id, seed5.user_a.id)
        assert resp.status_code == 200
        _ = resp.text

        result = await db_session.execute(
            select(Message).where(
                Message.conversation_id == conv_id,
                Message.role == "assistant",
            )
        )
        assistant_msg = result.scalar_one()
        assert assistant_msg.content == cs5.MockStreamingLLMProvider.CANNED_REPLY


# ---------------------------------------------------------------------------
# Test 4: Cross-tenant isolation
# ---------------------------------------------------------------------------

class TestStreamingCrossTenantIsolation:

    @pytest.mark.asyncio
    async def test_non_member_cannot_stream_other_workspace_conversation(
        self, client: AsyncClient, seed5
    ):
        """user_b cannot stream messages to user_a's conversation (403)."""
        conv = await _create_conversation(client, seed5.workspace_a.id, seed5.user_a.id)

        resp = await client.post(
            f"/api/v1/conversations/{conv['id']}/messages/stream",
            json={"content": "trying to infiltrate via stream"},
            headers={"X-Dev-User-ID": str(seed5.user_b.id)},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_same_workspace_cannot_stream_other_users_conversation(
        self, client: AsyncClient, seed5
    ):
        """user_v (viewer in workspace_a) cannot stream user_a's conversation (403)."""
        conv = await _create_conversation(client, seed5.workspace_a.id, seed5.user_a.id)

        resp = await client.post(
            f"/api/v1/conversations/{conv['id']}/messages/stream",
            json={"content": "sneaky stream"},
            headers={"X-Dev-User-ID": str(seed5.user_v.id)},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_stream_request_rejected(self, client: AsyncClient, seed5):
        """Missing auth header on stream endpoint returns 401."""
        conv = await _create_conversation(client, seed5.workspace_a.id, seed5.user_a.id)

        resp = await client.post(
            f"/api/v1/conversations/{conv['id']}/messages/stream",
            json={"content": "no auth"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_stream_evidence_never_leaks_cross_tenant_chunks(
        self, client: AsyncClient, seed5
    ):
        """User A's stream must never yield User B's document in the evidence event."""
        # Upload doc to workspace_b as user_b
        doc_b_resp = await _upload_doc(client, seed5.workspace_b.id, seed5.user_b.id)
        doc_b_id = doc_b_resp["document"]["id"]

        # Upload doc to workspace_a as user_a
        await _upload_doc(client, seed5.workspace_a.id, seed5.user_a.id)

        # user_a streams a message in workspace_a
        conv_a = await _create_conversation(client, seed5.workspace_a.id, seed5.user_a.id)
        resp = await _stream_message(client, uuid.UUID(conv_a["id"]), seed5.user_a.id)
        assert resp.status_code == 200

        events = _parse_sse_events(resp.text)
        evidence_event = next((e for e in events if e.get("type") == "evidence"), None)
        assert evidence_event is not None, "No evidence event found in stream"

        evidence_doc_ids = [c["document_id"] for c in evidence_event["chunks"]]
        assert doc_b_id not in evidence_doc_ids, (
            "CRITICAL LEAK: Workspace B document appeared in Workspace A's streaming evidence!"
        )


# ---------------------------------------------------------------------------
# Test 5: Non-streaming endpoint still works (Sprint 4 regression)
# ---------------------------------------------------------------------------

class TestSprintFourRegressionCheck:

    @pytest.mark.asyncio
    async def test_synchronous_send_message_still_returns_201(
        self, client: AsyncClient, seed5
    ):
        """POST /messages (non-streaming Sprint 4 endpoint) still works after Sprint 5."""
        conv = await _create_conversation(client, seed5.workspace_a.id, seed5.user_a.id)

        resp = await client.post(
            f"/api/v1/conversations/{conv['id']}/messages",
            json={"content": "backward compat check"},
            headers={"X-Dev-User-ID": str(seed5.user_a.id)},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert "user_message" in data
        assert "assistant_message" in data
