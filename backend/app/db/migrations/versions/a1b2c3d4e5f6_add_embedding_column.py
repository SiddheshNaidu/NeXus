"""add_embedding_column

Resolves BLOCKER-001: adds VECTOR(1536) embedding column to document_chunks.

Revision ID: a1b2c3d4e5f6
Revises: 59dc9cb221ca
Create Date: 2026-09-27 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '59dc9cb221ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable the vector extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Add the embedding column (nullable — filled once chunks are embedded)
    op.add_column(
        'document_chunks',
        sa.Column('embedding', Vector(1536), nullable=True),
    )

    # IVFFlat index for approximate nearest-neighbour cosine search.
    # lists=100 is a sensible default for moderate data volumes.
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding "
        "ON document_chunks USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding")
    op.drop_column('document_chunks', 'embedding')
