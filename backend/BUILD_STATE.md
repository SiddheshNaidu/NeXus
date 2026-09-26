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

## Sprint 1 — Workspace, Identity, Permissions ✅ COMPLETE

### What was built

| Module | Path | Description |
|--------|------|-------------|
| Dev auth dependency | `app/core/security.py` | `get_current_user` via `X-Dev-User-ID` header |
| Permission service | `app/services/permissions.py` | `Role` enum, `role_at_least()`, `require_workspace_role()`, `list_user_workspaces()` — fully decoupled, callable from services and routes |
| FastAPI auth deps | `app/api/deps.py` | `require_viewer()`, `require_contributor()`, `require_admin()` factory deps |
| Workspace schemas | `app/schemas/workspaces.py` | Extended with `WorkspaceWithRole`, `MembershipRead` |
| User schemas | `app/schemas/users.py` | Extended with `MeResponse` |
| Identity endpoint | `app/api/v1/identity.py` | `GET /api/v1/me` |
| Workspace endpoints | `app/api/v1/workspaces.py` | `GET /workspaces`, `GET /workspaces/{id}`, `GET /workspaces/{id}/collections` |
| Sprint 1 fixtures | `tests/conftest_sprint1.py` | NullPool per-test engine, commit+cleanup seed pattern |
| Sprint 1 tests | `tests/test_permissions.py` | 23 tests covering all acceptance criteria |

### Acceptance criteria

| Criterion | Result |
|-----------|--------|
| Viewer / Contributor / Admin permissions enforce correct access | ✅ 8 unit tests + 5 service-layer tests |
| User A cannot access User B's workspace | ✅ `test_get_workspace_non_member_forbidden` + `test_list_workspaces_only_own` |
| Permission checks reusable from services | ✅ Service-layer tests call `require_workspace_role()` directly, no HTTP needed |
| All 27 tests pass (Sprint 0 + Sprint 1) | ✅ 27 passed, 0 failed |

### Notes

- `DATABASE_URL` now points to port `5434` (pgvector container) per externally updated `.env`. Migrations re-run against 5434 successfully.
- NullPool pattern discovered for asyncpg test isolation: added to AGENTS.md.

---

## Sprint 2 — Upload and Processing Jobs ✅ COMPLETE

### What was built

| Module | Path | Description |
|--------|------|-------------|
| Local disk storage | `app/storage/local.py` | `LocalStorage` — saves bytes under `STORAGE_ROOT`, path-traversal safe |
| `get_storage` dependency | `app/api/v1/documents.py` | FastAPI dep returning the active storage backend; overridable in tests |
| Document service | `app/services/documents.py` | SHA-256 hash, safe filename, save to disk, insert `Document` + `ProcessingJob`, mock worker |
| Document schemas | `app/schemas/documents.py` | `DocumentUploadResponse`, `ProcessingJobRead`, added `storage_key` + `document_hash` to `DocumentRead` |
| Upload endpoint | `POST /api/v1/workspaces/{id}/documents` | Contributor+ only; returns 201 with document + job_id immediately |
| Status endpoint | `GET /api/v1/documents/{id}/status` | Viewer+ access; returns live processing state |
| Document GET | `GET /api/v1/documents/{id}` | Viewer+ access |
| Sprint 2 fixtures | `tests/conftest_sprint2.py` | Injects temp `LocalStorage` via `get_storage` dependency override; `tmp_path` is shared with tests |
| Sprint 2 tests | `tests/test_upload.py` | 8 tests covering all acceptance criteria |
| `tests/conftest.py` | Removed shadowing `client` fixture; base conftest now only defines `db_session` |
| `tests/test_health.py` | Self-contained `client` fixture (no conftest dependency) |

### Acceptance criteria

| Criterion | Result |
|-----------|--------|
| File upload saves bytes on disk | ✅ `test_upload_saves_file_on_disk` — verifies exact bytes at `tmp_path/storage/<key>` |
| `Document` DB record created with correct fields | ✅ `test_upload_creates_document_db_record` |
| `ProcessingJob` DB record created, mock worker marks completed | ✅ `test_upload_creates_processing_job_db_record` |
| Viewer blocked from upload (403) | ✅ `test_viewer_blocked_from_upload` |
| All 35 tests pass (Sprint 0 + 1 + 2) | ✅ 35 passed, 0 failed |

### Key engineering note (AGENTS.md Rule 12)

The root cause of the test isolation failures was `conftest.py` defining a `client` fixture that shadowed the sprint-specific `client` from `conftest_sprint2.py`, and also called `dependency_overrides.clear()` which wiped the `get_storage` override. Resolution: base `conftest.py` must never define a `client` fixture; each sprint owns its `client` in `conftest_sprintN.py`.

---

## Sprint 3 — AI / Embeddings / Vector Search — PENDING
