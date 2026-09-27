# NEXUS AI Evidence Intelligence Workspace — Technical Specification

> **Document status:** As-built, Sprint 0–5 complete  
> **Authors:** NEXUS Engineering  
> **Last updated:** Sprint 5 closeout

---

## Table of Contents

- [1. Introduction](#1-introduction)
  - [1.1 Problem Description](#11-problem-description)
  - [1.2 Goals](#12-goals)
  - [1.3 Assumptions](#13-assumptions)
- [2. Existing Solution](#2-existing-solution)
  - [2.1 Pros](#21-pros)
  - [2.2 Cons](#22-cons)
- [3. Proposed Solution](#3-proposed-solution)
  - [3.1 Pros](#31-pros)
  - [3.2 Cons](#32-cons)
  - [3.3 External Components](#33-external-components)
- [4. Architecture](#4-architecture)
- [5. Performance](#5-performance)
- [6. Test Plan](#6-test-plan)
- [7. Monitoring and Alerting](#7-monitoring-and-alerting)
  - [7.1 Tools](#71-tools)
  - [7.2 Plan and Strategy](#72-plan-and-strategy)
- [8. Cost](#8-cost)
  - [8.1 Development Cost](#81-development-cost)
  - [8.2 Infrastructure Cost](#82-infrastructure-cost)
  - [8.3 External Dependencies Cost](#83-external-dependencies-cost)
  - [8.4 Total Running Cost/Month](#84-total-running-costmonth)
- [9. Security and Privacy](#9-security-and-privacy)
  - [9.1 Potential Threats](#91-potential-threats)
  - [9.2 Mitigation Strategies](#92-mitigation-strategies)
- [10. Work](#10-work)
  - [10.1 Timelines](#101-timelines)
  - [10.2 Prioritization](#102-prioritization)
  - [10.3 Milestones](#103-milestones)
  - [10.4 Future Work](#104-future-work)
- [11. Related Works](#11-related-works)
- [12. Acknowledgements](#12-acknowledgements)

---

## 1. Introduction

### 1.1 Problem Description

Knowledge workers — researchers, analysts, lawyers, and engineers — accumulate large corpora of documents (PDFs, Word files, plain-text reports) across multiple projects or workspaces. Locating a specific fact, reconciling conflicting claims across sources, or surfacing relevant evidence for a new question currently requires manual reading and keyword search. These tools neither understand semantic meaning nor cite the exact passage that justifies an answer, forcing users to re-read entire documents to validate any AI-produced summary.

Additionally, raw binary document formats (DOCX, PDF) contain encoding artefacts — including null bytes (`\x00`) — that crash conventional database write paths when naively inserted as text, creating an invisible failure mode that is difficult to diagnose without deep knowledge of the PostgreSQL UTF-8 encoding contract.

### 1.2 Goals

| # | Goal | Success criterion |
|---|------|-------------------|
| G1 | **RAG-based AI chat** — users ask natural-language questions and receive answers grounded strictly in their uploaded documents | Every AI response is accompanied by Evidence rows linking the answer to the exact `document_chunk` (document name, chunk index, relevance score) that justified it |
| G2 | **Multi-format document ingestion** — users upload PDF, DOCX, plain-text, or image files and the system extracts and indexes their content automatically | `POST /workspaces/{id}/documents` accepts all supported MIME types; unsupported types are rejected with HTTP 422 before any DB write |
| G3 | **Workspace-scoped multi-tenancy** — users belong to one or more workspaces; documents, conversations, and search results are strictly isolated per workspace | Cosine similarity search SQL JOINs `document_chunks → documents` on `workspace_id`; no cross-tenant row is ever returned |
| G4 | **Role-based access control** — three roles (viewer, contributor, admin) govern who can read, upload, and manage workspace resources | Permission service `require_workspace_role()` is the single enforcement point; all 91 automated tests pass |
| G5 | **Streaming AI responses** — the assistant reply is streamed to the client as Server-Sent Events (SSE) so the UI remains responsive for long answers | SSE stream yields `evidence` → `text` chunks → `done` sentinel; DB rows committed before `done` is sent |
| G6 | **Client-side upload safety** — batch uploads of up to 10 files are validated for MIME type and size before any API call is made | Frontend rejects: > 10 files per batch, docs > 15 MB, images > 5 MB, and all unsupported MIME types |

### 1.3 Assumptions

- **Development-only authentication:** The current sprint cycle uses a header-based dev auth mechanism (`X-Dev-User-ID: <uuid>`). It is explicitly designed to make permission logic testable end-to-end without building OAuth. Production OAuth/JWT is deferred.
- **Local file storage:** Document bytes are persisted to the local filesystem under a configurable `STORAGE_ROOT`. Cloud object storage (S3, GCS) is an infrastructure swap that does not require application-logic changes.
- **Single-server deployment:** The FastAPI backend runs as a single uvicorn process. Horizontal scaling and job-queue separation (Celery, ARQ) are post-MVP concerns.
- **Google Gemini API availability:** Embedding generation (`gemini-embedding-2`, 1536 dimensions) and LLM completion (`gemini-2.0-flash-lite`) rely on the Google Cloud Gemini API. All tests inject mock providers to eliminate this dependency from the test suite.
- **PostgreSQL with pgvector:** The database is PostgreSQL ≥ 15 with the `pgvector` extension loaded. The extension is available on port 5434 via a Docker container in the development environment.
- **Python 3.12+ / Node 20+** are the minimum runtime versions.

---

## 2. Existing Solution

Before NEXUS, the team relied on manual document review, keyword search (Ctrl+F), and general-purpose AI chat assistants that had no access to private document corpora.

### 2.1 Pros

- No deployment cost or infrastructure overhead.
- No risk of data leaving internal systems via a third-party AI pipeline.
- Familiar tools (PDF readers, Word) with no learning curve.

### 2.2 Cons

- **No semantic retrieval:** keyword search misses synonyms, paraphrases, and cross-document relationships.
- **No citation trail:** AI assistants (ChatGPT, etc.) hallucinate sources; there is no way to verify which passage in which document justified a response.
- **No workspace isolation:** documents shared over email or file shares have no access control layer.
- **No multi-format normalisation:** each analyst manually copies text out of PDFs or Word files before analysis, which is error-prone and time-consuming.
- **Null-byte failures:** inserting raw binary document bytes directly into a database without format-aware parsing crashes PostgreSQL with `invalid byte sequence for encoding "UTF8": 0x00`, as was experienced with DOCX uploads.

---

## 3. Proposed Solution

NEXUS is a Retrieval-Augmented Generation (RAG) workspace that connects a FastAPI backend to a Next.js frontend. Documents are uploaded, parsed into chunks, embedded into 1536-dimensional vectors via Google Gemini, and stored in PostgreSQL with the `pgvector` extension. When a user asks a question, the query is embedded using the `RETRIEVAL_QUERY` task type, cosine similarity search retrieves the most relevant chunks from the user's workspace, and a system prompt injecting those chunks is sent to the Gemini LLM. The response is streamed back to the frontend as SSE.

### 3.1 Pros

- **Grounded answers:** every AI response is backed by Evidence rows pointing to the exact chunk and document that informed it — hallucination is structurally constrained.
- **Multi-format ingestion:** format-aware parsers (`pdfplumber` for PDF, `python-docx` for DOCX, UTF-8/latin-1 decode for plain text) normalise content before chunking; null bytes are stripped unconditionally.
- **Strong tenant isolation:** all search and retrieval SQL is workspace-scoped; the permission service is the single enforcement point called by every protected route.
- **Streaming UX:** SSE streaming means the user sees the first text tokens within seconds rather than waiting for the full LLM response.
- **Fully testable without external APIs:** every provider is injected via FastAPI `Depends()`; tests substitute mock providers with zero real API calls.
- **Client-side pre-validation:** the frontend validates file count, MIME type, and size limits before any HTTP request is made, preventing backend load from invalid uploads.

### 3.2 Cons

- **Synchronous SDK bridging:** the `google-genai` Python SDK is synchronous. It is currently bridged to the async FastAPI event loop via `asyncio.run_in_executor(None, _call)`. This adds a thread-pool context switch on every embedding or LLM call.
- **In-process document processing:** parsing, chunking, and embedding happen synchronously inside the upload request handler. For large files this increases the HTTP response latency and ties up the event loop thread pool.
- **Fixed chunk size:** chunks are split at a fixed 512-character boundary with 64-character overlap. This is a reasonable default but does not respect sentence or paragraph boundaries, which can degrade retrieval quality on structured documents.
- **Dev-only authentication:** the `X-Dev-User-ID` header mechanism provides no cryptographic guarantees. It must be replaced before any production deployment.
- **Local storage only:** the `LocalStorage` backend writes to a local directory. It is not suitable for multi-node deployments or persistent cloud infrastructure.

### 3.3 External Components

| Component | Package | Version | Purpose |
|---|---|---|---|
| **Google Gemini Embeddings** | `google-genai` | `>=1.0.0` | Generates 1536-dimensional embedding vectors for document chunks (`RETRIEVAL_DOCUMENT` task type) and search queries (`RETRIEVAL_QUERY` task type) using the `gemini-embedding-2` model |
| **Google Gemini LLM** | `google-genai` | `>=1.0.0` | Generates AI chat responses using `gemini-2.0-flash-lite`; supports both one-shot completion (`complete()`) and streaming (`stream_complete()` via `generate_content_stream` in a background thread) |
| **pdfplumber** | `pdfplumber` | `>=0.11.0` | Extracts text from PDF files page-by-page via `pdfplumber.open(io.BytesIO(data))`; corrupt or non-PDF binary returns empty string rather than crashing the pipeline |
| **python-docx** | `python-docx` | `>=1.1.0` | Extracts text from DOCX files paragraph-by-paragraph via `docx.Document(io.BytesIO(data))`; corrupt binary returns empty string |
| **pgvector** | `pgvector` | `>=0.3.0` | PostgreSQL extension and SQLAlchemy type (`Vector(1536)`) enabling cosine similarity search using the `<=>` operator on `document_chunks.embedding` |
| **FastAPI** | `fastapi[standard]` | `>=0.115.0` | Async Python web framework; provides dependency injection, OpenAPI schema generation, SSE via `StreamingResponse` |
| **SQLAlchemy (async)** | `sqlalchemy[asyncio]` | `>=2.0.0` | ORM and async session management; all DB access uses `AsyncSession` with `asyncpg` |
| **Alembic** | `alembic` | `>=1.13.0` | Database migration management; two migrations applied: initial schema (11 tables) and pgvector column addition |
| **Next.js** | `next` | `16.3.6` | React-based frontend framework; App Router with server components for layout, client components for all interactive UI |
| **Framer Motion / Motion** | `framer-motion`, `motion` | `>=13.4.4` | UI animations for upload transitions, modal entrance/exit, hero sequence |
| **@react-three/fiber + drei** | — | `^9`, `^10` | 3D robot model rendering in the homepage hero (`NEXsequence`) using Three.js |
| **@phosphor-icons/react** | — | `^2.1.10` | Icon set used throughout the UI |

---

## 4. Architecture

### Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        Browser (Next.js 16)                      │
│                                                                  │
│  pages: / · /upload · /search · /evidence/[id]                   │
│  state: useNexusSession (localStorage, re-bootstrap on login)    │
│  auth:  X-Dev-User-ID stored in localStorage, attached to every  │
│         fetch via apiClient.ts request() interceptor             │
│  upload: validateFiles() → Promise.allSettled() batch uploads    │
└────────────────────────┬─────────────────────────────────────────┘
                         │ HTTPS / HTTP  (api/v1/*)
                         │ SSE stream for /messages/stream
┌────────────────────────▼─────────────────────────────────────────┐
│                  FastAPI backend (uvicorn)                        │
│                                                                  │
│  GET  /api/v1/health                                             │
│  GET  /api/v1/me                                                 │
│  GET  /api/v1/workspaces[/{id}[/collections|/search]]            │
│  POST /api/v1/workspaces/{id}/documents          (201)           │
│  GET  /api/v1/documents/{id}[/status]                            │
│  POST /api/v1/workspaces/{id}/conversations      (201)           │
│  GET  /api/v1/conversations/{id}                                 │
│  POST /api/v1/conversations/{id}/messages        (201)           │
│  POST /api/v1/conversations/{id}/messages/stream (SSE)           │
│                                                                  │
│  Auth:   get_current_user() — X-Dev-User-ID → User row lookup    │
│  Perms:  require_workspace_role() — single enforcement point     │
│  Errors: NexusError hierarchy → structured JSON {"error":{...}}  │
└────┬──────────────────┬────────────────────────────────────┬─────┘
     │                  │                                    │
┌────▼────┐    ┌────────▼──────────┐              ┌─────────▼──────┐
│ Local   │    │  PostgreSQL 15 +  │              │  Google Gemini │
│ Storage │    │  pgvector         │              │  API           │
│         │    │                   │              │                │
│workspac │    │ users             │              │ gemini-        │
│es/{ws}/ │    │ workspaces        │              │ embedding-2    │
│docs/{id}│    │ workspace_members │              │ (1536-d)       │
│/{file}  │    │ collections       │              │                │
│         │    │ documents         │              │ gemini-2.0-    │
│         │    │ document_pages    │              │ flash-lite     │
│         │    │ document_chunks   │              │ (LLM)          │
│         │    │   .embedding      │              │                │
│         │    │   VECTOR(1536)    │              │ SDK bridged to │
│         │    │ processing_jobs   │              │ async via      │
│         │    │ conversations     │              │ run_in_executor│
│         │    │ messages          │              └────────────────┘
└─────────┘    │ evidence          │
               └───────────────────┘
```

### Backend layers

| Layer | Location | Responsibility |
|---|---|---|
| **API routes** | `app/api/v1/` | HTTP routing, request parsing, dependency injection, response serialisation |
| **Security** | `app/core/security.py` | `get_current_user()` FastAPI dependency: validates `X-Dev-User-ID` header, resolves UUID to a `User` row, raises `UnauthorizedError` on failure |
| **Permission service** | `app/services/permissions.py` | `require_workspace_role(db, user, workspace_id, minimum_role)` — workspace existence check, membership check, role hierarchy enforcement. Called from both routes and service functions |
| **Document service** | `app/services/documents.py` | MIME validation → SHA-256 hash → disk save → DB insert → pipeline: `_extract_text()` → `_split_chunks()` → `embedding_provider.embed()` → `DocumentChunk` persist |
| **Chat service** | `app/services/chat.py` | RAG pipeline: `embedder.embed(query)` → cosine search → system prompt with context → `llm.complete()` or `llm.stream_complete()` → persist `Message` + `Evidence` rows |
| **Providers** | `app/providers/` | Abstract `EmbeddingProvider` and `LLMProvider` interfaces; `GeminiEmbeddingProvider` and `GeminiLLMProvider` implementations; both bridge the synchronous `google-genai` SDK to asyncio via `run_in_executor` |
| **Storage** | `app/storage/` | Abstract `StorageInterface`; `LocalStorage` implementation writes bytes to `STORAGE_ROOT/workspaces/{ws}/docs/{doc}/{filename}` with path-traversal protection |
| **ORM models** | `app/db/models/` | SQLAlchemy 2.0 mapped-column models for all 11 database tables |
| **Configuration** | `app/core/config.py` | Pydantic `BaseSettings` reading from `.env`; all credentials and provider settings are environment variables |

### Frontend layers

| Layer | Location | Responsibility |
|---|---|---|
| **API client** | `src/services/apiClient.ts` | Centralized `fetch` wrapper; reads `nexus_dev_user_id` from `localStorage`, attaches `X-Dev-User-ID` header to every outgoing request; `streamRequest()` for SSE consumption |
| **Session hook** | `src/hooks/useNexusSession.ts` | `useNexusSession()` React hook; bootstraps session on mount by calling `GET /me`; exposes `login(uuid)` to save credentials and re-bootstrap, `logout()` to clear and reset |
| **Navbar / Dev Auth** | `src/components/ui/navbar.tsx` | Dev Login modal: quick-select from three hardcoded test users (fixed UUIDs matching the seed), manual UUID input with regex validation, authenticated state banner showing user name / workspace / role, Sign Out |
| **Upload page** | `src/app/upload/page.tsx` | Multi-file dropzone (up to 10 files); `validateFiles()` enforces MIME allowlist and per-type size limits client-side; `Promise.allSettled()` batch uploads; per-file `BatchItemRow` with `StatusBadge` and `MiniPipeline` tracker |
| **Services** | `src/services/` | `documentsService`, `identityService`, `searchService`, `evidenceService` — thin wrappers around `apiClient.ts` |

### Database schema (11 tables)

```
users (id PK, name, email UNIQUE, auth_subject UNIQUE, created_at)
workspaces (id PK, name, mode ENUM[personal|organization], organization_id, created_at)
workspace_members (workspace_id FK, user_id FK, role ENUM[viewer|contributor|admin]) — composite PK
collections (id PK, workspace_id FK, name, created_at)
documents (id PK, workspace_id FK, collection_id FK, name, mime_type, size_bytes,
           status ENUM[queued|processing|ready|failed], processing_stage, processing_progress,
           storage_key, document_hash INDEX, uploaded_by FK, error_message, created_at, updated_at)
document_pages (id PK, document_id FK, page_number, page_text, ocr_text, preview_key)
document_chunks (id PK, document_id FK, page_id FK, chunk_index, raw_text, contextual_text,
                 chunk_hash INDEX, embedding VECTOR(1536), created_at)
processing_jobs (id PK, document_id FK, status ENUM[queued|running|completed|failed],
                 stage, attempt, progress, message, started_at, finished_at)
conversations (id PK, workspace_id FK, user_id FK, created_at, updated_at)
messages (id PK, conversation_id FK, role ENUM[user|assistant], content, result_json, created_at)
evidence (id PK, chunk_id FK, document_id FK, text, relevance_score, created_at)
```

Vector index (added in migration `a1b2c3d4e5f6`):
```sql
CREATE INDEX ix_document_chunks_embedding
    ON document_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

### Document processing pipeline (as-built)

```
POST /workspaces/{id}/documents
        │
        ▼
1. MIME validation ─── unsupported type? → raise ValidationError (422), no DB write
        │
        ▼
2. SHA-256(data) + _safe_filename()
        │
        ▼
3. LocalStorage.save(storage_key, data)
        │
        ▼
4. INSERT Document (status=queued)
5. INSERT ProcessingJob (status=queued)
        │
        ▼
6. _extract_text(data, mime_type)
        │
        ├─ text/plain  → data.decode("utf-8") | latin-1 fallback
        ├─ application/pdf → pdfplumber.open() page-by-page
        ├─ application/vnd…docx → docx.Document() paragraph join
        └─ image/*     → "" (stored, 0 chunks)
        │
        ▼
7. .replace('\x00', '')   ← Postgres null-byte safeguard (unconditional)
        │
        ▼
8. _split_chunks(text, size=512, overlap=64)
        │
        ▼
9. GeminiEmbeddingProvider.embed(chunks)
        │  └─ batches of ≤100, run_in_executor(None, _call)
        │     task_type=RETRIEVAL_DOCUMENT
        ▼
10. INSERT DocumentChunk rows with embedding vectors
        │
        ▼
11. Document.status = "ready", ProcessingJob.status = "completed"
```

### RAG chat pipeline (as-built)

```
POST /conversations/{id}/messages
        │
        ▼
1. embedder.embed([user_query])  ← task_type=RETRIEVAL_QUERY
        │
        ▼
2. SELECT ... FROM document_chunks dc
   JOIN documents d ON d.id = dc.document_id
   WHERE d.workspace_id = :workspace_id
   ORDER BY dc.embedding <=> CAST(:vec AS vector)
   LIMIT 5
        │
        ▼
3. Build system prompt: _SYSTEM_PROMPT.format(context=retrieved_chunks)
        │
        ▼
4. llm.complete([ system_prompt, ...history, user_message ])
        │         └─ run_in_executor for synchronous SDK call
        ▼
5. INSERT Message(role=user), INSERT Message(role=assistant)
6. INSERT Evidence rows (chunk_id, document_id, relevance_score) × 5
        │
        ▼
7. Return { user_message, assistant_message, evidence[] }
```

For the streaming variant (`/messages/stream`), step 4 uses `llm.stream_complete()` which runs `generate_content_stream` in a background thread via a `Queue`, yields text chunks as SSE `{"type":"text","text":"..."}` events, and commits DB rows only after all chunks have been yielded.

---

## 5. Performance

### Batch upload limits (client-side enforcement)

All limits are enforced in `validateFiles()` in `src/app/upload/page.tsx` before any HTTP request is made:

| Constraint | Value | Rationale |
|---|---|---|
| Maximum files per batch | **10** | Prevents accidental mass upload; keeps concurrent `Promise.allSettled()` fan-out manageable |
| Maximum size — document (PDF, TXT, DOCX) | **15 MB** | Keeps embedding batch count reasonable; a 15 MB text file produces ~30 000 512-character chunks which would strain a single embedding API call |
| Maximum size — image (PNG, JPEG, WEBP) | **5 MB** | Images produce 0 chunks (no text extraction); the limit caps storage consumption |

Rejected files are surfaced in an amber validation banner immediately — no round trip.

### Async event loop design

The `google-genai` Python SDK (`_client.models.embed_content`, `_client.models.generate_content`) is **synchronous**. Running it directly on the FastAPI async event loop would block all other coroutines for the duration of the network call. The solution in `GeminiEmbeddingProvider._embed_batch()` and `GeminiLLMProvider`:

```python
loop = asyncio.get_event_loop()
return await loop.run_in_executor(None, _call)
```

`run_in_executor(None, _call)` dispatches `_call` to the default `ThreadPoolExecutor`, returning an awaitable. The event loop is free to serve other requests while the SDK call is in flight. The thread pool is sized by Python's default (`min(32, os.cpu_count() + 4)`).

### Embedding batching

`GeminiEmbeddingProvider.embed()` splits its input list into batches of ≤ 100 texts (the Gemini API maximum per call) and submits them concurrently via `asyncio.gather`:

```python
batch_results = await asyncio.gather(
    *[self._embed_batch(batch) for batch in batches]
)
```

For a 512-character chunk size with 64-character overlap applied to a 15 MB plain-text file (~30 000 chunks), this means 300 concurrent embedding batches — each running in the thread pool. In practice, the Gemini API rate limit will be the binding constraint before the thread pool is.

### Chunking parameters (as-built)

| Parameter | Value | Location |
|---|---|---|
| `CHUNK_SIZE` | 512 characters | `app/services/documents.py` |
| `CHUNK_OVERLAP` | 64 characters | `app/services/documents.py` |
| `_TOP_K` | 5 chunks per query | `app/services/chat.py` |
| Embedding dimension | 1536 | `settings.embedding_dimension` |
| Embedding batch size | 100 | `_BATCH_SIZE` in `app/providers/embeddings.py` |

### Polling interval (frontend)

The upload page polls `GET /documents/{id}/status` every **1500 ms** per file using a per-batch `setInterval`. All polled files in a batch execute concurrently inside `Promise.allSettled()` per tick. Polling stops automatically when all files reach `"READY"` or `"FAILED"`.

---

## 6. Test Plan

### Test suite structure

The backend uses `pytest` with `pytest-asyncio` in `auto` mode. Each sprint owns its own fixture file (`conftest_sprintN.py`) that injects a per-test `NullPool` database engine and overrides all FastAPI dependencies (`get_db`, `get_storage`, `get_embedder`, `get_llm`) to prevent cross-test state and real API calls.

| Test file | Sprint | Tests | Scope |
|---|---|---|---|
| `tests/test_health.py` | 0 | 4 | Health endpoint, DB connectivity, OpenAPI schema |
| `tests/test_permissions.py` | 1 | 23 | Role hierarchy, workspace isolation, permission service unit tests |
| `tests/test_upload.py` | 2 | 8 | File upload, disk persistence, DB records, viewer/non-member rejection |
| `tests/test_sprint3.py` | 3 | 15 | pgvector column, embedding pipeline, vector search, cross-tenant isolation |
| `tests/test_sprint4.py` | 4 | 21 | Conversation creation, RAG pipeline, message persistence, evidence rows, cross-tenant |
| `tests/test_sprint5.py` | 5 | 16 | SSE streaming, event sequence, DB persistence after stream, cross-tenant isolation |
| `tests/test_document_parser.py` | 3+ | 19 | `_extract_text()` unit tests (all MIME paths), null-byte stripping, HTTP integration for MIME gating and 422 rejection |
| **Total** | — | **106** | — |

**Current state:** 91 backend tests pass (Sprints 0–5 original suite). The new `test_document_parser.py` adds 19 tests (11 unit + 7 integration + 1 skipped for missing `reportlab`).

### Key testing patterns

**No real API calls:** `MockEmbeddingProvider` returns deterministic unit vectors keyed by `hash(text[:64]) % 1536`. `MockLLMProvider` returns a fixed canned string. `MockStreamingLLMProvider` yields the canned string word-by-word. All three are injected via FastAPI dependency overrides — production singletons are never instantiated during test runs.

**Null-byte stripping test:** Since `python-docx` / `lxml` rejects `\x00` at write time, the test uses `unittest.mock.patch("docx.Document", return_value=mock_doc)` where `mock_doc.paragraphs[0].text = "before\x00after"` to prove the strip executes on the output of a parsed document, not just on construction.

**MIME gating test — no DB record after 422:**
```python
# test_unsupported_mime_leaves_no_db_record
rows = await db_session.execute(
    text("SELECT COUNT(*) FROM documents WHERE workspace_id = :ws AND name = 'archive.zip'"),
    {"ws": seed3.workspace_a.id},
)
assert rows.scalar() == 0
```
This verifies that `ValidationError` is raised before any `INSERT` statement executes.

### Frontend validation

The `validateFiles()` function in `upload/page.tsx` is exercised via the HTTP integration tests for MIME gating. Direct unit tests for the TypeScript function are a gap in the current coverage and are noted under Future Work.

---

## 7. Monitoring and Alerting

*NEXUS is currently a local development system with no production deployment. The baseline described here documents what is in place today and what would be required for a production rollout.*

### 7.1 Tools

| Category | Current (local dev) | Production target |
|---|---|---|
| **Application logging** | `uvicorn` stdout with INFO-level access logs; `print()` statements in document service pipeline stages | Structured JSON logging (e.g., `structlog`) shipped to a log aggregator (Datadog, Grafana Loki, or AWS CloudWatch) |
| **Error tracking** | `unhandled_exception_handler` catches all exceptions and returns structured `{"error": {...}}` JSON — stack traces are suppressed from responses | Sentry SDK with `before_send` hook to strip PII; alerts on new error fingerprints |
| **Uptime monitoring** | `GET /api/v1/health` returns `{"status": "ok", "database": "ok"}` — suitable for a simple HTTP health check | Pingdom / AWS Route 53 health check polling `/health` every 60 s; PagerDuty alert on 3 consecutive failures |
| **Performance metrics** | None | Prometheus metrics via `prometheus-fastapi-instrumentator`; track `http_request_duration_seconds` by route and embedding/LLM call latency via custom counters |

### 7.2 Plan and Strategy

**Health endpoint contract (`GET /api/v1/health`):**  
The endpoint verifies database connectivity on every call (`SELECT 1`). A `"database": "degraded"` response would indicate the PostgreSQL connection pool is exhausted or the DB is unreachable. This endpoint should be the primary target for both uptime monitoring and load-balancer health checks.

**Processing pipeline observability:**  
The `ProcessingJob` table is a built-in audit log. Every document processing attempt persists `status`, `stage`, `progress`, `started_at`, `finished_at`, and `error_message`. A background monitoring query against `processing_jobs WHERE status = 'failed'` and `WHERE finished_at IS NULL AND started_at < NOW() - INTERVAL '10 minutes'` would surface stuck or failed jobs without requiring additional infrastructure.

**Embedding / LLM call monitoring:**  
`GeminiEmbeddingProvider` and `GeminiLLMProvider` make synchronous calls via `run_in_executor`. In production, these calls should be wrapped with timing instrumentation so p95 latency for embedding and generation is tracked separately. Latency spikes here directly degrade upload and chat response times.

**Alerting thresholds (production targets):**

| Signal | Warning | Critical |
|---|---|---|
| `GET /health` failure rate | > 1% over 5 min | Any failure × 3 consecutive |
| Document processing `failed` count | > 5 in 10 min | > 20 in 10 min |
| Embedding call p95 latency | > 3 s | > 10 s |
| LLM call p95 latency | > 8 s | > 30 s |
| PostgreSQL connection pool saturation | > 80% | > 95% |

---

## 8. Cost

*All figures are estimates for a minimal production deployment (single region, low traffic). Development environment costs are zero beyond existing hardware.*

### 8.1 Development Cost

The system was built across 5 sprints using in-house engineering resources. No external contractors were engaged. Development infrastructure (local PostgreSQL Docker container, local file storage) incurs no cloud cost.

### 8.2 Infrastructure Cost

| Component | Spec | Estimated monthly cost |
|---|---|---|
| **PostgreSQL + pgvector** | AWS RDS `db.t3.medium` (2 vCPU, 4 GB RAM), `gp3` 50 GB storage with `pgvector` extension | ~$50/month |
| **FastAPI backend** | AWS ECS Fargate, 1 task × 1 vCPU / 2 GB, `spot` pricing | ~$12/month |
| **Next.js frontend** | Vercel Hobby (free tier) or AWS Amplify | $0–$20/month |
| **Local file storage** | AWS S3 standard, 50 GB, 10 K GET/PUT requests | ~$2/month |
| **Networking** | ALB, data transfer out 10 GB/month | ~$18/month |
| **Total infrastructure** | | **~$82–$102/month** |

### 8.3 External Dependencies Cost

| Dependency | Pricing model | Estimated monthly usage | Estimated cost |
|---|---|---|---|
| **Google Gemini Embedding API** (`gemini-embedding-2`) | $0.00004 per 1K characters (approximate) | 10 documents/day × 50 KB avg × 30 days = 15 MB text = 15 M characters | ~$0.60/month |
| **Google Gemini LLM** (`gemini-2.0-flash-lite`) | $0.075 per 1M input tokens, $0.30 per 1M output tokens (approximate) | 50 queries/day × 2K input tokens × 30 days = 3M input tokens | ~$0.23/month |
| **Total external API** | | | **~$0.83/month** |

*Note: Gemini API pricing is subject to change. Consult the Google Cloud pricing page for current rates. These estimates assume a low-traffic development/demo deployment.*

### 8.4 Total Running Cost/Month

| Category | Cost |
|---|---|
| Infrastructure | ~$82–$102 |
| External APIs | ~$1 |
| **Total** | **~$83–$103/month** |

---

## 9. Security and Privacy

### 9.1 Potential Threats

| # | Threat | Surface |
|---|---|---|
| T1 | **Unauthenticated access** — any caller that omits `X-Dev-User-ID` or supplies an unknown UUID gains no access, but the header mechanism provides zero cryptographic guarantee | All API endpoints |
| T2 | **Cross-tenant data leakage** — a workspace member constructing a crafted query could retrieve document chunks from a workspace they do not belong to if tenant isolation is incomplete | `GET /workspaces/{id}/search`, RAG chat pipeline |
| T3 | **Privilege escalation** — a viewer-role user attempts a contributor-only operation (upload, delete) | `POST /workspaces/{id}/documents` |
| T4 | **Path traversal via filename** — a malicious filename like `../../../etc/passwd` in a file upload could escape the storage root | `LocalStorage.save()` |
| T5 | **Null-byte injection** — raw binary document bytes containing `\x00` inserted into a PostgreSQL `TEXT` column causes `invalid byte sequence for encoding "UTF8": 0x00` | Document text extraction → `document_chunks.raw_text` |
| T6 | **Oversized or malformed upload** — a 1 GB binary disguised as a PDF could exhaust storage and memory during parsing | `POST /workspaces/{id}/documents` |
| T7 | **CORS misconfiguration** — current CORS policy is `allow_origins=["*"]`, permitting any origin to make credentialed requests in production | All endpoints |
| T8 | **Conversation ownership bypass** — a workspace member who knows a conversation UUID could read or post to another user's conversation | `GET /conversations/{id}`, `POST /conversations/{id}/messages` |
| T9 | **Stack trace exposure** — unhandled exceptions could leak internal paths and library versions | All endpoints |

### 9.2 Mitigation Strategies

**T1 — Dev auth header contract:**  
`get_current_user()` in `app/core/security.py` validates that `X-Dev-User-ID` is present, parses it as a UUID (rejects non-UUID strings with `ValueError` → 401), and queries the `users` table. An unknown UUID returns `scalar_one_or_none() = None` → `UnauthorizedError(401)`. No user data is accessible without a valid, database-backed UUID. This mechanism is explicitly marked for replacement with OAuth/JWT before production (`# Replace this module in a future sprint`).

**Deterministic UUID seeding strategy:**  
`seed_test_data.py` uses fixed UUIDs (`00000000-0000-0000-0000-00000000000{1,2,3}`) so the frontend dev login modal and the backend database stay in sync across developer machines. The seed script uses `INSERT … ON CONFLICT (email) DO UPDATE SET id = EXCLUDED.id` to atomically repair stale random-UUID rows from earlier seed runs, sidestepping the `ix_users_email` unique index trap. The `--reset` flag deletes by `id IN (…) OR email IN (…)` to also purge orphaned rows.

**T2 — Workspace-scoped SQL JOINs for tenant isolation:**  
Every vector search query (both `GET /workspaces/{id}/search` and the RAG pipeline in `chat.py`) uses:
```sql
JOIN documents d ON d.id = dc.document_id
WHERE d.workspace_id = :workspace_id
```
`workspace_id` is always derived from the authenticated, permission-checked workspace, never from user-supplied request body parameters. `require_workspace_role()` is called before any data access; a non-member receives `ForbiddenError(403)` before the SQL executes. This is verified by `TestCrossTenantIsolation` across Sprints 3, 4, and 5.

**T3 — Role enforcement at the permission service:**  
`require_workspace_role(db, user, workspace_id, Role.CONTRIBUTOR)` is the single enforcement point, called on every write operation. The `role_at_least()` function implements a rank-ordered comparison (`viewer=0`, `contributor=1`, `admin=2`); a role that does not satisfy the minimum returns `ForbiddenError(403)`.

**T4 — Path traversal protection:**  
`_safe_filename()` in `documents.py` uses `PurePosixPath(name).name` to strip all directory components, then applies `re.sub(r"[^\w.\-]", "_", basename)` to replace non-safe characters. `LocalStorage` further joins all paths using `Path(self.root) / storage_key` and verifies the resolved path starts with the storage root before writing.

**T5 — Null-byte sanitisation:**  
`_extract_text()` in `app/services/documents.py` applies `.replace('\x00', '')` unconditionally as the final step of every parse path, regardless of MIME type or parser used:
```python
return raw.replace("\x00", "")
```
This runs after UTF-8 decode, pdfplumber extraction, python-docx paragraph join, and the image empty-string path. PostgreSQL's `TEXT` type rejects `\x00` with `invalid byte sequence for encoding "UTF8": 0x00`; this single line is the database-level safeguard. Tested directly in `TestExtractTextUnit` and via the HTTP integration test `test_null_bytes_in_plain_text_do_not_crash_db`.

**T6 — Client-side upload size limits:**  
`validateFiles()` in `upload/page.tsx` rejects files exceeding 15 MB (documents) or 5 MB (images) before issuing any HTTP request. Server-side, MIME type is validated before any DB write via `_SUPPORTED_MIME_TYPES` check in `create_document_from_upload()`.

**T7 — CORS (deferred):**  
`allow_origins=["*"]` is an explicit development convenience noted in the source code comment: `# CORS — open for local development; tighten per environment in production`. Production deployment must restrict this to the known frontend origin.

**T8 — Conversation ownership:**  
`conversations.py` enforces both workspace membership (`require_workspace_role`) and direct ownership (`conv.user_id != current_user.id → ForbiddenError`) before serving or accepting conversation data.

**T9 — Stack trace suppression:**  
`unhandled_exception_handler` in `app/core/errors.py` is registered as a catch-all on the FastAPI app. It returns `{"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred."}}` — no stack trace, no internal path, no library version is ever serialised into an HTTP response.

---

## 10. Work

### 10.1 Timelines

| Sprint | Scope | Status |
|---|---|---|
| Sprint 0 | Repository, DB schema, ORM models, health endpoint, Alembic migrations | ✅ Complete |
| Sprint 1 | Dev auth, permission service, workspace/identity endpoints | ✅ Complete |
| Sprint 2 | File upload, local storage, document/job DB records, status polling | ✅ Complete |
| Sprint 3 | Gemini embeddings, pgvector column + IVFFlat index, vector search endpoint | ✅ Complete |
| Sprint 4 | RAG chat pipeline, conversation/message endpoints, evidence rows | ✅ Complete |
| Sprint 5 | SSE streaming chat, `stream_complete()` provider method, DB persistence after stream | ✅ Complete |
| Sprint 0 (FE) | Auth storage fix (`localStorage`), `useNexusSession` login/logout, Dev Auth modal in Navbar | ✅ Complete |
| Sprint 0.1 (FE) | Fixed UUID seed alignment (frontend ↔ backend) | ✅ Complete |
| Sprint 0.1a (FE) | Idempotent seed fix (email conflict `ON CONFLICT DO UPDATE`) | ✅ Complete |
| Sprint 1 (FE) | Multi-file batch upload, client-side validation, `BatchItemRow` tracker | ✅ Complete |
| Parser fix | MIME-routed extraction, null-byte strip, `ValidationError` 422 guard, `test_document_parser.py` | ✅ Complete |

### 10.2 Prioritization

| Priority | Item | Rationale |
|---|---|---|
| P0 | Replace `X-Dev-User-ID` with OAuth 2.0 / JWT | Blocker for any public or multi-user deployment |
| P0 | Tighten CORS `allow_origins` to known frontend domain | Security prerequisite for production |
| P1 | Move document processing to a background job queue (Celery / ARQ) | Large files currently block the upload HTTP response; a queue decouples ingestion latency from the user request |
| P1 | Cloud object storage (S3/GCS) | Required for horizontal scaling and persistence across deployments |
| P2 | Sentence-boundary-aware chunking | Improves retrieval quality on structured documents |
| P2 | Frontend unit tests for `validateFiles()` | Currently only covered by HTTP integration tests |
| P3 | Structured logging + Sentry integration | Required for production observability |
| P3 | Admin workspace management endpoints | Invite members, set roles, remove documents |

### 10.3 Milestones

| Milestone | Criteria |
|---|---|
| **M1 — Backend API complete** | All 91 Sprint 0–5 tests pass; health, identity, documents, search, conversations, streaming all functional ✅ |
| **M2 — Frontend functional** | Dev Auth modal working, batch upload with validation, per-file progress tracker, session persists across refreshes ✅ |
| **M3 — End-to-end dev loop** | `./dev.sh` auto-seeds DB, starts both servers, frontend login → upload → search → chat works without manual steps ✅ |
| **M4 — Production auth** | OAuth 2.0 / JWT replaces `X-Dev-User-ID`; CORS locked to frontend origin — **pending** |
| **M5 — Production deployment** | Containerised, cloud-hosted, background job queue, cloud storage, structured logging — **pending** |

### 10.4 Future Work

The following items are explicitly out of scope for the current sprint cycle and are deferred to future work:

1. **Production authentication (OAuth 2.0 / JWT):** `app/core/security.py` contains the comment `Replace this module in a future sprint when real authentication is wired`. The `auth_subject` column exists on the `users` table to hold the OAuth subject claim when this is implemented.

2. **Background job queue:** Document processing (parse → chunk → embed) currently runs synchronously inside the HTTP request handler. A task queue (Celery + Redis, or ARQ) would move this work off the request thread, returning a `202 Accepted` immediately and allowing the client to poll status — which the `ProcessingJob` table already supports.

3. **Cloud object storage:** `LocalStorage` must be replaced with an `S3Storage` or `GCSStorage` implementation of the `StorageInterface` abstract class. The interface is already designed for this swap.

4. **Production container orchestration:** Docker Compose for local development exists in `backend/docker-compose.yml`. Kubernetes manifests or ECS task definitions for production are not yet written.

5. **OCR pipeline for scanned PDFs:** The `document_pages.ocr_text` column and `"ocr"` processing stage are already modelled in the schema but not yet implemented. `pdfplumber` extracts embedded text only; scanned PDFs would require Tesseract or a cloud OCR API.

6. **Sentence-boundary chunking:** The current 512-character fixed-size chunker respects no semantic boundaries. A sentence-aware splitter (e.g., using `spaCy` or NLTK sentence tokenization) would improve retrieval precision.

7. **Frontend unit and E2E tests:** `@playwright/test` is listed in `devDependencies` but no test files exist yet. The `validateFiles()` function in `upload/page.tsx` has no direct TypeScript unit test coverage.

8. **Admin workspace management:** The `admin` role exists in the permission hierarchy but no admin-only endpoints (invite user, remove member, delete workspace, manage collections) have been built yet.

9. **Rate limiting:** The API has no per-user or per-IP rate limiting. This is acceptable in a development context but is a prerequisite for production.

---

## 11. Related Works

- **LangChain / LlamaIndex** — general-purpose RAG orchestration frameworks. NEXUS implements a bespoke RAG pipeline (`app/services/chat.py`) to maintain full visibility into each step and avoid framework abstractions that obscure the retrieval-generation boundary.
- **Pinecone / Weaviate / Qdrant** — dedicated vector databases. NEXUS uses PostgreSQL with the `pgvector` extension to avoid introducing a second database engine while maintaining the ability to JOIN vector search results with relational workspace and permission data in a single SQL query.
- **OpenAI Assistants API** — managed RAG service. NEXUS keeps the RAG logic in-house (no managed API) so document contents never leave the operator's infrastructure (except for embedding and LLM API calls to Google Gemini).
- **Notion AI / Guru** — commercial document intelligence products. These do not support private deployment, custom permission models, or structured evidence citation trails.

---

## 12. Acknowledgements

- [A practical guide to writing technical specs](https://stackoverflow.blog/2020/04/06/a-practical-guide-to-writing-technical-specs) by Zara Cooper
- NEXUS backend sprint engineering documented in `backend/BUILD_STATE.md`
- NEXUS frontend sprint engineering documented in `frontend/FRONTEND_BUILD_STATE.md`
- Template structure: *Technical Specification Document Template* by James Olinya (`tsd_template.md`)
