# BUILD_STATE.md — NEXUS Backend Sprint Log

---

## Sprint 0 — Repository and Contract Foundation ✅ COMPLETE

**Date:** Sprint 0 build complete.

### What was built

| Module | Path | Status |
|--------|------|--------|
| FastAPI application | `app/main.py` | ✅ |
| Configuration | `app/core/config.py` | ✅ |
| Error model + handlers | `app/core/errors.py` | ✅ |
| Database session (asyncpg) | `app/db/session.py` | ✅ |
| SQLAlchemy declarative base | `app/db/base.py` | ✅ |
| ORM: users | `app/db/models/users.py` | ✅ |
| ORM: workspaces, workspace_members, collections | `app/db/models/workspaces.py` | ✅ |
| ORM: documents, document_pages, document_chunks | `app/db/models/documents.py` | ✅ |
| ORM: processing_jobs | `app/db/models/jobs.py` | ✅ |
| ORM: conversations, messages | `app/db/models/conversations.py` | ✅ |
| ORM: evidence | `app/db/models/evidence.py` | ✅ |
| Pydantic schemas | `app/schemas/` (health, common, users, workspaces, documents, conversations, search, evidence) | ✅ |
| Provider interfaces (stub) | `app/providers/__init__.py` | ✅ |
| Storage interface (stub) | `app/storage/__init__.py` | ✅ |
| API router | `app/api/v1/__init__.py` | ✅ |
| Health endpoint | `app/api/v1/health.py` | ✅ |
| Alembic migrations | `app/db/migrations/` | ✅ |
| Initial schema migration | `app/db/migrations/versions/59dc9cb221ca_initial_schema.py` | ✅ |
| Health tests | `tests/test_health.py` | ✅ (4/4 pass) |
| Test configuration | `tests/conftest.py`, `pytest.ini` | ✅ |

### Acceptance criteria

| Criterion | Result |
|-----------|--------|
| `GET /api/v1/health` → 200 | ✅ Verified by test |
| Database connects successfully | ✅ Verified by test (`database: "ok"`) |
| Migrations run without errors | ✅ `alembic upgrade head` applied 11 tables |
| FastAPI app starts cleanly | ✅ No startup errors |
| OpenAPI docs load | ✅ `/openapi.json` returns 200, verified by test |
| Tests run | ✅ 4 passed, 0 failed |

### Database tables created

`users`, `workspaces`, `workspace_members`, `collections`, `documents`, `document_pages`,
`document_chunks`, `processing_jobs`, `conversations`, `messages`, `evidence`

### Known deferred items

- `document_chunks.embedding` (pgvector column) — deferred to Sprint 3; local Postgres does not have the `vector` extension installed.
- `app/core/security.py` — deferred to Sprint 1 (authentication).
- All `services/`, `processing/`, `retrieval/`, `generation/`, `workers/` directories — not yet created per sprint boundary enforcement.

---

## Sprint 1 — Workspace, Identity, Permissions — PENDING

## Sprint 2 — Upload and Processing Jobs — PENDING

## Sprint 3 — AI / Embeddings / Vector Search — PENDING
