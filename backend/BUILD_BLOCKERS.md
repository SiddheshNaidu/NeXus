# BUILD_BLOCKERS.md — NEXUS Backend Blockers

---

## Open Blockers

_None._

---

## Resolved Blockers

### BLOCKER-001 — pgvector extension not installed on local Postgres ✅ RESOLVED

**Sprint affected:** Sprint 3 (Embeddings + Vector Search)

**Description:**
The local PostgreSQL instance did not have the `pgvector` extension installed.

**Resolution:**
The pgvector-enabled Docker container (`pgvector/pgvector:pg16`) is running on port `5434`.
`CREATE EXTENSION IF NOT EXISTS vector;` now succeeds.

The Sprint 3 migration (`a1b2c3d4e5f6_add_embedding_column.py`) runs this statement
idempotently and adds the `VECTOR(1536)` column to `document_chunks`.

**Resolved in:** Sprint 3
