# BUILD_BLOCKERS.md — NEXUS Backend Blockers

---

## Open Blockers

### BLOCKER-001 — pgvector extension not installed on local Postgres

**Sprint affected:** Sprint 3 (Embeddings + Vector Search)

**Description:**
The local PostgreSQL instance does not have the `pgvector` extension installed.
`CREATE EXTENSION IF NOT EXISTS vector;` fails with:
`ERROR: extension "vector" is not available`.

**Impact:**
The `document_chunks.embedding` column (type `VECTOR(n)`) cannot be created until this is resolved.
The Sprint 0 migration deliberately omits this column.

**Resolution options:**
1. Install the pgvector system package and rebuild: `pacman -S postgresql-pgvector` (Arch) or equivalent.
2. Run Postgres inside a container using `pgvector/pgvector:pg16` (preferred for reproducibility).
3. Use a managed Postgres service with pgvector support (e.g. Supabase, Neon, AWS RDS with pgvector).

**Blocker since:** Sprint 0

---

## Resolved Blockers

_None yet._
