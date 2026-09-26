"""Sprint 4 tests — Chat, RAG, and Conversations.

Acceptance criteria verified here:
  1. A user can create a conversation and send a message.
  2. Sending a message triggers mock embedder + mock LLM and saves:
       - User Message row
       - Assistant Message row
       - Evidence rows (one per retrieved chunk)
  3. Users get 403 Forbidden when accessing conversations in workspaces
     they do not belong to.
  4. No real API calls are made (MockEmbeddingProvider + MockLLMProvider).
"""
import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

import tests.conftest_sprint4 as cs4

pytest_plugins = ["tests.conftest_sprint4"]

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


async def _create_conversation(client: AsyncClient, workspace_id: uuid.UUID, user_id: uuid.UUID) -> dict:
    resp = await client.post(
        f"/api/v1/workspaces/{workspace_id}/conversations",
        headers={"X-Dev-User-ID": str(user_id)},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _send_message(
    client: AsyncClient,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    content: str = "What is artificial intelligence?",
) -> dict:
    resp = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": content},
        headers={"X-Dev-User-ID": str(user_id)},
    )
    return resp


# ---------------------------------------------------------------------------
# Test 1: Create conversation
# ---------------------------------------------------------------------------

class TestCreateConversation:

    @pytest.mark.asyncio
    async def test_member_can_create_conversation(self, client: AsyncClient, seed4):
        """Any workspace member can create a conversation."""
        resp = await client.post(
            f"/api/v1/workspaces/{seed4.workspace_a.id}/conversations",
            headers={"X-Dev-User-ID": str(seed4.user_a.id)},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["workspace_id"] == str(seed4.workspace_a.id)
        assert data["user_id"] == str(seed4.user_a.id)
        assert "id" in data

    @pytest.mark.asyncio
    async def test_viewer_can_create_conversation(self, client: AsyncClient, seed4):
        """Viewer role is sufficient to create a conversation."""
        resp = await client.post(
            f"/api/v1/workspaces/{seed4.workspace_a.id}/conversations",
            headers={"X-Dev-User-ID": str(seed4.user_v.id)},
        )
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_non_member_cannot_create_conversation(self, client: AsyncClient, seed4):
        """Non-member gets 403 when creating a conversation."""
        resp = await client.post(
            f"/api/v1/workspaces/{seed4.workspace_a.id}/conversations",
            headers={"X-Dev-User-ID": str(seed4.user_b.id)},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_request_rejected(self, client: AsyncClient, seed4):
        """Missing auth header returns 401."""
        resp = await client.post(
            f"/api/v1/workspaces/{seed4.workspace_a.id}/conversations"
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test 2: Send message — RAG pipeline triggered, rows persisted
# ---------------------------------------------------------------------------

class TestSendMessage:

    @pytest.mark.asyncio
    async def test_send_message_returns_201(self, client: AsyncClient, seed4):
        """Sending a message returns 201 with user + assistant messages."""
        await _upload_doc(client, seed4.workspace_a.id, seed4.user_a.id)
        conv = await _create_conversation(client, seed4.workspace_a.id, seed4.user_a.id)

        resp = await _send_message(client, uuid.UUID(conv["id"]), seed4.user_a.id)
        assert resp.status_code == 201, resp.text

    @pytest.mark.asyncio
    async def test_send_message_response_shape(self, client: AsyncClient, seed4):
        """Response contains user_message, assistant_message, and evidence list."""
        await _upload_doc(client, seed4.workspace_a.id, seed4.user_a.id)
        conv = await _create_conversation(client, seed4.workspace_a.id, seed4.user_a.id)

        resp = await _send_message(client, uuid.UUID(conv["id"]), seed4.user_a.id)
        assert resp.status_code == 201
        data = resp.json()

        assert "user_message" in data
        assert "assistant_message" in data
        assert "evidence" in data

        assert data["user_message"]["role"] == "user"
        assert data["assistant_message"]["role"] == "assistant"
        assert isinstance(data["evidence"], list)

    @pytest.mark.asyncio
    async def test_assistant_message_is_mock_reply(self, client: AsyncClient, seed4):
        """The assistant reply is the canned mock response."""
        await _upload_doc(client, seed4.workspace_a.id, seed4.user_a.id)
        conv = await _create_conversation(client, seed4.workspace_a.id, seed4.user_a.id)

        resp = await _send_message(client, uuid.UUID(conv["id"]), seed4.user_a.id)
        assert resp.status_code == 201
        data = resp.json()
        assert data["assistant_message"]["content"] == cs4.MockLLMProvider.CANNED_REPLY

    @pytest.mark.asyncio
    async def test_mock_embedder_was_called(self, client: AsyncClient, seed4):
        """The MockEmbeddingProvider.embed() was called during message processing."""
        await _upload_doc(client, seed4.workspace_a.id, seed4.user_a.id)
        conv = await _create_conversation(client, seed4.workspace_a.id, seed4.user_a.id)

        before = cs4._mock_embedder.call_count if cs4._mock_embedder else 0
        resp = await _send_message(client, uuid.UUID(conv["id"]), seed4.user_a.id)
        assert resp.status_code == 201
        assert cs4._mock_embedder is not None
        assert cs4._mock_embedder.call_count > before

    @pytest.mark.asyncio
    async def test_mock_llm_was_called(self, client: AsyncClient, seed4):
        """The MockLLMProvider.complete() was called during message processing."""
        await _upload_doc(client, seed4.workspace_a.id, seed4.user_a.id)
        conv = await _create_conversation(client, seed4.workspace_a.id, seed4.user_a.id)

        resp = await _send_message(client, uuid.UUID(conv["id"]), seed4.user_a.id)
        assert resp.status_code == 201
        assert cs4._mock_llm is not None
        assert cs4._mock_llm.call_count >= 1

    @pytest.mark.asyncio
    async def test_user_message_saved_to_db(self, client: AsyncClient, db_session: AsyncSession, seed4):
        """A Message row with role='user' is created in the database."""
        from app.db.models.conversations import Message

        await _upload_doc(client, seed4.workspace_a.id, seed4.user_a.id)
        conv = await _create_conversation(client, seed4.workspace_a.id, seed4.user_a.id)
        conv_id = uuid.UUID(conv["id"])

        resp = await _send_message(
            client, conv_id, seed4.user_a.id, content="Tell me about AI."
        )
        assert resp.status_code == 201

        result = await db_session.execute(
            select(Message).where(
                Message.conversation_id == conv_id,
                Message.role == "user",
            )
        )
        user_msgs = result.scalars().all()
        assert len(user_msgs) == 1
        assert user_msgs[0].content == "Tell me about AI."

    @pytest.mark.asyncio
    async def test_assistant_message_saved_to_db(self, client: AsyncClient, db_session: AsyncSession, seed4):
        """A Message row with role='assistant' is created in the database."""
        from app.db.models.conversations import Message

        await _upload_doc(client, seed4.workspace_a.id, seed4.user_a.id)
        conv = await _create_conversation(client, seed4.workspace_a.id, seed4.user_a.id)
        conv_id = uuid.UUID(conv["id"])

        resp = await _send_message(client, conv_id, seed4.user_a.id)
        assert resp.status_code == 201

        result = await db_session.execute(
            select(Message).where(
                Message.conversation_id == conv_id,
                Message.role == "assistant",
            )
        )
        assistant_msgs = result.scalars().all()
        assert len(assistant_msgs) == 1
        assert assistant_msgs[0].content == cs4.MockLLMProvider.CANNED_REPLY

    @pytest.mark.asyncio
    async def test_evidence_saved_to_db(self, client: AsyncClient, db_session: AsyncSession, seed4):
        """Evidence rows are created in the database when chunks are retrieved."""
        await _upload_doc(client, seed4.workspace_a.id, seed4.user_a.id)
        conv = await _create_conversation(client, seed4.workspace_a.id, seed4.user_a.id)
        conv_id = uuid.UUID(conv["id"])

        resp = await _send_message(client, conv_id, seed4.user_a.id)
        assert resp.status_code == 201

        # Evidence rows are linked to document_chunks of workspace_a
        rows = await db_session.execute(
            text("""
                SELECT COUNT(*) FROM evidence ev
                JOIN document_chunks dc ON dc.id = ev.chunk_id
                JOIN documents d ON d.id = dc.document_id
                WHERE d.workspace_id = :ws_id
            """),
            {"ws_id": seed4.workspace_a.id},
        )
        count = rows.scalar()
        assert count > 0, "Expected at least one evidence row after sending a message"

    @pytest.mark.asyncio
    async def test_send_message_no_docs_still_works(self, client: AsyncClient, seed4):
        """Sending a message in a workspace with no documents returns a valid response."""
        conv = await _create_conversation(client, seed4.workspace_a.id, seed4.user_a.id)
        resp = await _send_message(client, uuid.UUID(conv["id"]), seed4.user_a.id)
        assert resp.status_code == 201
        data = resp.json()
        assert data["assistant_message"]["content"] == cs4.MockLLMProvider.CANNED_REPLY
        # No chunks → no evidence
        assert data["evidence"] == []


# ---------------------------------------------------------------------------
# Test 3: Get conversation history
# ---------------------------------------------------------------------------

class TestGetConversation:

    @pytest.mark.asyncio
    async def test_get_empty_conversation(self, client: AsyncClient, seed4):
        """A newly created conversation has an empty message list."""
        conv = await _create_conversation(client, seed4.workspace_a.id, seed4.user_a.id)
        resp = await client.get(
            f"/api/v1/conversations/{conv['id']}",
            headers={"X-Dev-User-ID": str(seed4.user_a.id)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == conv["id"]
        assert data["messages"] == []

    @pytest.mark.asyncio
    async def test_get_conversation_includes_messages(self, client: AsyncClient, seed4):
        """After sending a message, GET includes both user and assistant messages."""
        conv = await _create_conversation(client, seed4.workspace_a.id, seed4.user_a.id)
        await _send_message(client, uuid.UUID(conv["id"]), seed4.user_a.id)

        resp = await client.get(
            f"/api/v1/conversations/{conv['id']}",
            headers={"X-Dev-User-ID": str(seed4.user_a.id)},
        )
        assert resp.status_code == 200
        messages = resp.json()["messages"]
        assert len(messages) == 2
        roles = [m["role"] for m in messages]
        assert "user" in roles
        assert "assistant" in roles

    @pytest.mark.asyncio
    async def test_get_nonexistent_conversation_returns_404(self, client: AsyncClient, seed4):
        """Getting a non-existent conversation returns 404."""
        resp = await client.get(
            f"/api/v1/conversations/{uuid.uuid4()}",
            headers={"X-Dev-User-ID": str(seed4.user_a.id)},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test 4: Cross-tenant isolation
# ---------------------------------------------------------------------------

class TestCrossTenantIsolation:

    @pytest.mark.asyncio
    async def test_non_member_cannot_read_conversation(self, client: AsyncClient, seed4):
        """user_b (member of workspace_b) cannot read user_a's conversation."""
        conv = await _create_conversation(client, seed4.workspace_a.id, seed4.user_a.id)

        resp = await client.get(
            f"/api/v1/conversations/{conv['id']}",
            headers={"X-Dev-User-ID": str(seed4.user_b.id)},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_non_member_cannot_send_message(self, client: AsyncClient, seed4):
        """user_b cannot send a message to user_a's conversation."""
        conv = await _create_conversation(client, seed4.workspace_a.id, seed4.user_a.id)

        resp = await client.post(
            f"/api/v1/conversations/{conv['id']}/messages",
            json={"content": "trying to infiltrate"},
            headers={"X-Dev-User-ID": str(seed4.user_b.id)},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_non_member_cannot_create_conversation_in_other_workspace(
        self, client: AsyncClient, seed4
    ):
        """user_b cannot create a conversation in workspace_a."""
        resp = await client.post(
            f"/api/v1/workspaces/{seed4.workspace_a.id}/conversations",
            headers={"X-Dev-User-ID": str(seed4.user_b.id)},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_in_workspace_cannot_read_other_users_conversation(
        self, client: AsyncClient, seed4
    ):
        """user_v (viewer in workspace_a) cannot read user_a's conversation."""
        conv = await _create_conversation(client, seed4.workspace_a.id, seed4.user_a.id)

        # user_v is a viewer in workspace_a but does NOT own the conversation
        resp = await client.get(
            f"/api/v1/conversations/{conv['id']}",
            headers={"X-Dev-User-ID": str(seed4.user_v.id)},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_in_workspace_cannot_message_other_users_conversation(
        self, client: AsyncClient, seed4
    ):
        """user_v cannot post to user_a's conversation even though both are in workspace_a."""
        conv = await _create_conversation(client, seed4.workspace_a.id, seed4.user_a.id)

        resp = await client.post(
            f"/api/v1/conversations/{conv['id']}/messages",
            json={"content": "sneaky message"},
            headers={"X-Dev-User-ID": str(seed4.user_v.id)},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_rag_pipeline_never_retrieves_cross_tenant_chunks(
        self, client: AsyncClient, seed4
    ):
        """User A's conversation in Workspace A must never retrieve User B's documents as evidence."""
        # 1. Upload doc to workspace B as user B
        doc_b_resp = await _upload_doc(client, seed4.workspace_b.id, seed4.user_b.id)
        doc_b_id = doc_b_resp["document"]["id"]

        # 2. Upload doc to workspace A as user A
        await _upload_doc(client, seed4.workspace_a.id, seed4.user_a.id)

        # 3. User A creates a conversation in workspace A
        conv_a = await _create_conversation(client, seed4.workspace_a.id, seed4.user_a.id)

        # 4. User A sends a message
        resp = await _send_message(client, uuid.UUID(conv_a["id"]), seed4.user_a.id)
        assert resp.status_code == 201
        data = resp.json()

        # 5. Verify NO evidence comes from Workspace B's document
        evidence_doc_ids = [e["document_id"] for e in data.get("evidence", [])]
        assert doc_b_id not in evidence_doc_ids, "CRITICAL LEAK: Workspace B document retrieved as evidence in Workspace A!"
