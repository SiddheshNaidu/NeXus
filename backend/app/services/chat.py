"""Chat service — Sprint 4/5.

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

Sprint 5 adds stream_message() — an async generator that yields SSE-formatted
events for evidence and text chunks, then commits DB rows after the stream ends.

The service is pure business logic — no FastAPI dependencies here.
Providers are passed as arguments so tests can inject mocks.
"""
import json
import uuid
from collections.abc import AsyncIterator
from typing import NamedTuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.db.models.conversations import Conversation, Message
from app.db.models.evidence import Evidence
from app.providers import EmbeddingProvider, LLMProvider

# Candidate pool size for vector retrieval (pre-adaptive filter).
_TOP_K = 3

# Absolute minimum cosine similarity (1 - distance).  Filters weak semantic
# matches while still admitting moderately relevant hits in smaller corpora.
_MIN_COSINE_SIMILARITY = 0.45

# If a later candidate's score falls more than this below the preceding kept
# chunk, stop taking further results (aggressive score-gap drop-off).
_SCORE_GAP = 0.12

# Rolling window: number of most-recent message pairs (user + assistant) to
# include in the LLM context.  Prevents the accumulated token count from
# growing without bound and crashing the model's context window.
_HISTORY_WINDOW_PAIRS = 5
_HISTORY_WINDOW = _HISTORY_WINDOW_PAIRS * 2  # messages (user + assistant each)

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


def _adaptive_filter(
    chunks: list[RetrievedChunk],
    *,
    min_score: float = _MIN_COSINE_SIMILARITY,
    score_gap: float = _SCORE_GAP,
) -> list[RetrievedChunk]:
    """Dynamic Top-K with score-gap fallback.

    Candidates must already be ordered best→worst by cosine similarity.
    Keeps a chunk when:
      1. score >= min_score (absolute floor for sparse workspaces), and
      2. the drop from the previously kept chunk is <= score_gap
         (large cliff ⇒ remaining neighbors are a different topic).
    Returns [] when even the best hit fails the floor.
    """
    kept: list[RetrievedChunk] = []
    for chunk in chunks:
        if chunk.score < min_score:
            break
        if kept and (kept[-1].score - chunk.score) > score_gap:
            break
        kept.append(chunk)
    return kept


async def _retrieve_chunks(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    query_vector: list[float],
    top_k: int = _TOP_K,
) -> list[RetrievedChunk]:
    """Fetch a top-k candidate pool, then apply adaptive score-gap filtering.

    SQL returns the nearest neighbors with no rigid distance cutoff.  Python
    then applies the absolute floor + score-gap drop-off so sparse workspaces
    still surface their best evidence while out-of-scope queries return [].
    """
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
    candidates = [
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
    return _adaptive_filter(candidates)


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
    """Load the last _HISTORY_WINDOW messages for a conversation.

    Applies a rolling window so long conversations never exceed the LLM's
    context limit.  Only the most recent _HISTORY_WINDOW_PAIRS pairs
    (user + assistant) are included; older messages are silently dropped.
    """
    from sqlalchemy import select
    from app.db.models.conversations import Message

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    all_messages = result.scalars().all()
    # Apply rolling window — keep only the tail
    windowed = all_messages[-_HISTORY_WINDOW:] if len(all_messages) > _HISTORY_WINDOW else all_messages
    return [
        {"role": msg.role, "content": msg.content}
        for msg in windowed
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


async def stream_message(
    db: AsyncSession,
    conversation: Conversation,
    user_query: str,
    embedder: EmbeddingProvider,
    llm: LLMProvider,
) -> AsyncIterator[str]:
    """Streaming RAG pipeline — yields SSE-formatted events then persists to DB.

    Event sequence:
      1. ``data: {"type": "evidence", "chunks": [...]}\\n\\n``
      2. One or more ``data: {"type": "text", "text": "<chunk>"}\\n\\n``
      3. ``data: {"type": "done"}\\n\\n``

    After the "done" event the user message, aggregated assistant message,
    and all evidence rows are committed to the database.
    """
    workspace_id = conversation.workspace_id

    # 1. Embed the query
    query_vectors = await embedder.embed([user_query])
    query_vector = query_vectors[0]

    # 2. Retrieve relevant chunks
    chunks = await _retrieve_chunks(db, workspace_id, query_vector)

    # 3. Yield evidence payload first
    evidence_payload = [
        {
            "chunk_id": str(c.chunk_id),
            "document_id": str(c.document_id),
            "document_name": c.document_name,
            "chunk_index": c.chunk_index,
            "text": c.text,
            "score": c.score,
        }
        for c in chunks
    ]
    yield f"data: {json.dumps({'type': 'evidence', 'chunks': evidence_payload})}\n\n"

    # 4. Build conversation history + system prompt (rolling window)
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
    )
    all_msgs = result.scalars().all()
    windowed = all_msgs[-_HISTORY_WINDOW:] if len(all_msgs) > _HISTORY_WINDOW else all_msgs
    history = [
        {"role": msg.role, "content": msg.content}
        for msg in windowed
    ]
    context = _build_context(chunks)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT.format(context=context)},
        *history,
        {"role": "user", "content": user_query},
    ]

    # 5. Stream text chunks from LLM
    full_reply_parts: list[str] = []
    async for chunk_text in llm.stream_complete(messages):
        full_reply_parts.append(chunk_text)
        yield f"data: {json.dumps({'type': 'text', 'text': chunk_text})}\n\n"

    # 6. Persist user message, aggregated assistant message, and evidence
    answer_text = "".join(full_reply_parts)

    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=user_query,
    )
    db.add(user_msg)

    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer_text,
    )
    db.add(assistant_msg)

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

    await db.commit()

    # 7. Signal completion
    yield f"data: {json.dumps({'type': 'done'})}\n\n"
