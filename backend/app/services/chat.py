"""Chat service — Sprint 4.

RAG orchestration pipeline for a single user message:
  1. Embed the query (reuse Sprint 3 embedding provider).
  2. Cosine-similarity search for the top-k most relevant document_chunks
     scoped to the workspace (same SQL as the search endpoint).
  3. Build a system prompt that injects the retrieved chunks as context.
  4. Call the LLM provider with the full conversation history.
  5. Persist:
       - User Message row  (role="user")
       - Assistant Message row (role="assistant")
       - Evidence rows, one per retrieved chunk, linked to the chunk_id
         and document_id with the similarity score.
  6. Return the assistant message and evidence list to the caller.

The service is pure business logic — no FastAPI dependencies here.
Providers are passed as arguments so tests can inject mocks.
"""
import uuid
from typing import NamedTuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.conversations import Conversation, Message
from app.db.models.evidence import Evidence
from app.providers import EmbeddingProvider, LLMProvider

# Number of chunks to retrieve per query
_TOP_K = 5

# System prompt template — {context} is replaced with retrieved chunks
_SYSTEM_PROMPT = """You are NEX, an AI research assistant inside the NEXUS Evidence Intelligence Workspace.

Your job is to answer questions using ONLY the evidence provided below.
If the answer cannot be found in the evidence, say so explicitly — do not fabricate information.

=== EVIDENCE ===
{context}
=== END EVIDENCE ===

Cite the document name and chunk index when referencing specific evidence.
Be concise, factual, and grounded."""


class RetrievedChunk(NamedTuple):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    chunk_index: int
    text: str
    score: float


async def _retrieve_chunks(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    query_vector: list[float],
    top_k: int = _TOP_K,
) -> list[RetrievedChunk]:
    """Run the cosine similarity search and return the top-k chunks."""
    sql = text("""
        SELECT
            dc.id            AS chunk_id,
            dc.document_id,
            dc.chunk_index,
            dc.raw_text,
            d.name           AS document_name,
            1 - (dc.embedding <=> CAST(:vec AS vector)) AS score
        FROM document_chunks dc
        JOIN documents d ON d.id = dc.document_id
        WHERE d.workspace_id = :workspace_id
          AND dc.embedding IS NOT NULL
        ORDER BY dc.embedding <=> CAST(:vec AS vector)
        LIMIT :limit
    """)

    vec_str = "[" + ",".join(str(v) for v in query_vector) + "]"
    result = await db.execute(
        sql,
        {"vec": vec_str, "workspace_id": workspace_id, "limit": top_k},
    )
    return [
        RetrievedChunk(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            document_name=row.document_name,
            chunk_index=row.chunk_index,
            text=row.raw_text,
            score=float(row.score),
        )
        for row in result.fetchall()
    ]


def _build_context(chunks: list[RetrievedChunk]) -> str:
    """Format retrieved chunks into a readable context block."""
    if not chunks:
        return "(No relevant documents found in this workspace.)"
    parts = []
    for c in chunks:
        parts.append(
            f"[Source: {c.document_name}, chunk {c.chunk_index}]\n{c.text}"
        )
    return "\n\n---\n\n".join(parts)


async def _build_history(
    db: AsyncSession, conversation_id: uuid.UUID
) -> list[dict]:
    """Load existing messages for a conversation as a list of role/content dicts."""
    from sqlalchemy import select
    from app.db.models.conversations import Message

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    return [
        {"role": msg.role, "content": msg.content}
        for msg in result.scalars().all()
    ]


class ChatResult(NamedTuple):
    assistant_message: Message
    evidence: list[Evidence]
    retrieved_chunks: list[RetrievedChunk]


async def handle_message(
    db: AsyncSession,
    conversation: Conversation,
    user_query: str,
    embedder: EmbeddingProvider,
    llm: LLMProvider,
) -> ChatResult:
    """Process one user turn: retrieve → generate → persist.

    Returns a ChatResult with the saved assistant Message and Evidence rows.
    The caller is responsible for committing the session.
    """
    workspace_id = conversation.workspace_id

    # 1. Embed the query
    query_vectors = await embedder.embed([user_query])
    query_vector = query_vectors[0]

    # 2. Retrieve relevant chunks
    chunks = await _retrieve_chunks(db, workspace_id, query_vector)

    # 3. Persist the user message
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=user_query,
    )
    db.add(user_msg)
    await db.flush()

    # 4. Build conversation history + system prompt
    history = await _build_history(db, conversation.id)
    context = _build_context(chunks)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT.format(context=context)},
        *history,
    ]

    # 5. Call the LLM
    answer_text = await llm.complete(messages)

    # 6. Persist the assistant message
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer_text,
    )
    db.add(assistant_msg)
    await db.flush()

    # 7. Persist evidence rows (one per retrieved chunk)
    evidence_rows: list[Evidence] = []
    for chunk in chunks:
        ev = Evidence(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            text=chunk.text,
            relevance_score=chunk.score,
        )
        db.add(ev)
        evidence_rows.append(ev)

    await db.flush()

    return ChatResult(
        assistant_message=assistant_msg,
        evidence=evidence_rows,
        retrieved_chunks=chunks,
    )
