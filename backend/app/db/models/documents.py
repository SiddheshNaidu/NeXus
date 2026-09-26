import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collections.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        SAEnum("queued", "processing", "ready", "failed", name="document_status"),
        nullable=False,
        default="queued",
        index=True,
    )
    processing_stage: Mapped[str | None] = mapped_column(
        SAEnum(
            "detecting", "routing", "extracting", "ocr",
            "structuring", "indexing", "ready",
            name="document_stage",
        ),
        nullable=True,
    )
    processing_progress: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processing_route: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    document_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="documents")
    collection: Mapped["Collection"] = relationship("Collection", back_populates="documents")
    pages: Mapped[list["DocumentPage"]] = relationship(
        "DocumentPage", back_populates="document", lazy="select", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="document", lazy="select", cascade="all, delete-orphan"
    )
    processing_jobs: Mapped[list] = relationship(
        "ProcessingJob", back_populates="document", lazy="select", cascade="all, delete-orphan"
    )


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    page_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    preview_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped["Document"] = relationship("Document", back_populates="pages")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="page", lazy="select"
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_pages.id", ondelete="SET NULL"), nullable=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    contextual_text: Mapped[str] = mapped_column(Text, nullable=False)
    section: Mapped[str | None] = mapped_column(String(512), nullable=True)
    heading: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chunk_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # embedding column added by pgvector migration in Sprint 3
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
    page: Mapped["DocumentPage"] = relationship("DocumentPage", back_populates="chunks")
    evidence: Mapped[list] = relationship(
        "Evidence", back_populates="chunk", lazy="select"
    )


# Avoid circular import
from app.db.models.workspaces import Collection, Workspace  # noqa: E402, F401
