"""Conversation endpoints — Sprint 4/5.

POST /workspaces/{workspace_id}/conversations           — create a new chat thread (viewer+)
GET  /conversations/{conversation_id}                   — get conversation + messages (viewer+)
POST /conversations/{conversation_id}/messages          — send a user message, get AI reply (viewer+)
POST /conversations/{conversation_id}/messages/stream   — stream AI reply via SSE (Sprint 5)

All endpoints require workspace membership (any role).
Users can only access conversations they own inside workspaces they belong to.
"""
import uuid
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError
from app.core.security import get_current_user
from app.db.models.conversations import Conversation, Message
from app.db.models.users import User
from app.db.session import get_db
from app.providers import EmbeddingProvider, LLMProvider
from app.providers.embeddings import get_embedding_provider as _get_embedder
from app.providers.llm import get_llm_provider as _get_llm
from app.schemas.conversations import ConversationRead, MessageRead
from app.schemas.evidence import EvidenceRead
from app.services.chat import handle_message, stream_message
from app.services.permissions import Role, require_workspace_role

router = APIRouter(tags=["conversations"])


# ---------------------------------------------------------------------------
# FastAPI dependency factories — overridable in tests
# ---------------------------------------------------------------------------

def get_embedder() -> EmbeddingProvider:
    """Embedding provider dependency (overridable in tests)."""
    return _get_embedder()


def get_llm() -> LLMProvider:
    """LLM provider dependency (overridable in tests)."""
    return _get_llm()


# ---------------------------------------------------------------------------
# Response models (Sprint 4 additions)
# ---------------------------------------------------------------------------

class ConversationWithMessages(BaseModel):
    """Conversation plus its full message history."""
    id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    messages: list[MessageRead]

    model_config = {"from_attributes": True}


class SendMessageRequest(BaseModel):
    content: str


class SendMessageResponse(BaseModel):
    user_message: MessageRead
    assistant_message: MessageRead
    evidence: list[EvidenceRead]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/workspaces/{workspace_id}/conversations",
    response_model=ConversationRead,
    status_code=201,
    summary="Create conversation",
    description="Start a new chat thread in a workspace. Requires Viewer+ role.",
)
async def create_conversation(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationRead:
    await require_workspace_role(db, current_user, workspace_id, Role.VIEWER)

    conv = Conversation(
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ConversationRead.model_validate(conv)


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationWithMessages,
    summary="Get conversation",
    description="Returns a conversation and its message history. Caller must own the conversation and be a workspace member.",
)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationWithMessages:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise NotFoundError(f"Conversation {conversation_id} not found.")

    # Verify caller is a member of the conversation's workspace
    await require_workspace_role(db, current_user, conv.workspace_id, Role.VIEWER)

    # Verify caller owns this conversation
    if conv.user_id != current_user.id:
        raise ForbiddenError("You do not have access to this conversation.")

    # Load messages ordered by creation time
    msgs_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = msgs_result.scalars().all()

    return ConversationWithMessages(
        id=conv.id,
        workspace_id=conv.workspace_id,
        user_id=conv.user_id,
        messages=[MessageRead.model_validate(m) for m in messages],
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=SendMessageResponse,
    status_code=201,
    summary="Send message",
    description="Send a user message; the AI response and evidence are returned immediately.",
)
async def send_message(
    conversation_id: uuid.UUID,
    body: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    embedder: EmbeddingProvider = Depends(get_embedder),
    llm: LLMProvider = Depends(get_llm),
) -> SendMessageResponse:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise NotFoundError(f"Conversation {conversation_id} not found.")

    # Verify caller is a workspace member
    await require_workspace_role(db, current_user, conv.workspace_id, Role.VIEWER)

    # Verify caller owns this conversation
    if conv.user_id != current_user.id:
        raise ForbiddenError("You do not have access to this conversation.")

    chat_result = await handle_message(
        db=db,
        conversation=conv,
        user_query=body.content,
        embedder=embedder,
        llm=llm,
    )

    await db.commit()
    await db.refresh(chat_result.assistant_message)
    for ev in chat_result.evidence:
        await db.refresh(ev)

    # Also load the user message for the response
    user_msg_result = await db.execute(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.role == "user",
        )
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    user_msg = user_msg_result.scalar_one()

    return SendMessageResponse(
        user_message=MessageRead.model_validate(user_msg),
        assistant_message=MessageRead.model_validate(chat_result.assistant_message),
        evidence=[EvidenceRead.model_validate(ev) for ev in chat_result.evidence],
    )


@router.post(
    "/conversations/{conversation_id}/messages/stream",
    status_code=200,
    summary="Stream message (SSE)",
    description=(
        "Send a user message and receive the AI reply as a Server-Sent Events stream. "
        "Events: evidence payload first, then text chunks, then a done sentinel. "
        "Database rows are committed after the stream completes."
    ),
)
async def stream_message_endpoint(
    conversation_id: uuid.UUID,
    body: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    embedder: EmbeddingProvider = Depends(get_embedder),
    llm: LLMProvider = Depends(get_llm),
) -> StreamingResponse:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise NotFoundError(f"Conversation {conversation_id} not found.")

    # Verify caller is a workspace member
    await require_workspace_role(db, current_user, conv.workspace_id, Role.VIEWER)

    # Verify caller owns this conversation
    if conv.user_id != current_user.id:
        raise ForbiddenError("You do not have access to this conversation.")

    return StreamingResponse(
        stream_message(
            db=db,
            conversation=conv,
            user_query=body.content,
            embedder=embedder,
            llm=llm,
        ),
        media_type="text/event-stream",
    )
