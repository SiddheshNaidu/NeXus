<div align="center">

# Ｎ Ｅ Ｘ Ｕ Ｓ

**AI EVIDENCE INTELLIGENCE WORKSPACE**

*Ask what your documents know. Get answers with absolute proof.*

[![Next.js](https://img.shields.io/badge/Next.js-16.3-black?logo=nextdotjs)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![pgvector](https://img.shields.io/badge/PostgreSQL-pgvector-336791?logo=postgresql)](https://github.com/pgvector/pgvector)
[![Gemini](https://img.shields.io/badge/Google_Gemini-AI-4285F4?logo=google)](https://ai.google.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript)](https://www.typescriptlang.org)

</div>

---

## ⮞ SYSTEM OVERVIEW

NEXUS is a next-generation Retrieval-Augmented Generation (RAG) platform designed for precision knowledge extraction. Upload heterogeneous documents (PDF, DOCX, TXT). Ask natural-language questions. Receive grounded answers with exact, clickable citations tracing back to the original source. 

NEXUS does not guess. If evidence is insufficient or conflicting, the engine explicitly reports the anomaly rather than hallucinating an answer.

---

## ⮞ CORE ARCHITECTURE

The system operates across a decoupled, asynchronous pipeline, strictly isolating tenant data while bridging synchronous AI SDKs into a high-performance async event loop.

```mermaid
graph TD
    classDef core fill:#050505,stroke:#4f46e5,stroke-width:1px,color:#f4f4f5;
    classDef ext fill:#0a0a0a,stroke:#3f3f46,stroke-width:1px,color:#a1a1aa;

    U[User Query]:::core --> E[Gemini Embedding Matrix]:::ext
    E --> V[pgvector Similarity Search]:::core
    V --> C[Context Assembly & RBAC]:::core
    C --> L[Gemini Flash LLM]:::ext
    L --> S[SSE Telemetry Stream]:::core
    S --> UI[NEXUS Canvas]:::core
```

### The Ingestion Matrix
Documents pass through a format-aware detection pipeline:
`QUEUED` → `DETECTING` → `ROUTING` → `EXTRACTING` → `STRUCTURING` → `INDEXING` → `READY`

- **Extraction:** Native parsing via `pdfplumber` and `python-docx`.
- **Sanitization:** Unconditional null-byte (`\x00`) stripping ensures raw binary encoding artefacts never crash the PostgreSQL `TEXT` columns.
- **Vectorization:** Text is chunked (512 chars, 64 overlap) and mapped into 1536-dimensional space using `gemini-embedding-2`.

### The Retrieval Engine
Search is completely deterministic and workspace-scoped:
- **Tenant Isolation:** Cosine similarity (`<=>`) is strictly bound via SQL JOINs (`documents d ON d.id = dc.document_id WHERE d.workspace_id = :ws`). Cross-tenant leakage is mathematically impossible.
- **Asynchronous Bridging:** Synchronous AI SDKs are dispatched to the thread pool via `run_in_executor(None, _call)`, preventing event-loop blocking during embedding or generation.

---

## ⮞ THE INTERFACE

A cinematic, three-column cybernetic workspace built on `#050505` black backgrounds, 1px structural grid lines, and Geist typography.

*   **Source Rail (Left):** Real-time telemetry on indexed workspace documents.
*   **Answer Canvas (Center):** Server-Sent Events (SSE) stream the AI response progressively. Citation chips materialize only after the final structured payload is validated.
*   **Evidence Inspector (Right):** Select a citation to inspect the raw extracted passage, complete with document metadata, page numbers, and exact phrasing. 

The landing sequence features a WebGL `NEX` model (Three.js / React Three Fiber), particle contact fields, and an Aether Flow background driven by GSAP and Framer Motion.

---

## ⮞ TECH STACK

### 1. Frontend Terminal
*   **Core:** Next.js 16.3 (App Router), TypeScript 5, Tailwind CSS v4
*   **Motion & 3D:** Motion (Framer), GSAP 3, Anime.js, Lenis, Three.js, React Three Fiber
*   **Networking:** Fetch API with native SSE parsing

### 2. Backend Core
*   **Core:** FastAPI 0.115+ (Async), Python 3.12+
*   **Data Persistence:** PostgreSQL 16 + pgvector, SQLAlchemy 2.0 (Async), Alembic
*   **AI Providers:** Google Gemini API (`gemini-2.0-flash-lite`, `gemini-embedding-2`)
*   **Validation:** Pydantic v2

---

## ⮞ INITIALIZATION SEQUENCE

### Prerequisites
*   Node.js 20+
*   Python 3.12+
*   Docker (for PostgreSQL/pgvector)
*   Google Gemini API Key

### Step 1: Ignite the Database
```bash
cd backend
docker-compose up -d
```
*Engages PostgreSQL 16 with pgvector on port `5432`.*

### Step 2: Configure Environment
```bash
cd backend
cp .env.example .env
```
Inject your credentials into `.env`:
```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/nexus
LLM_PROVIDER=google
LLM_MODEL=gemini-2.0-flash-lite
LLM_API_KEY=your_gemini_key
EMBEDDING_PROVIDER=google
EMBEDDING_MODEL=gemini-embedding-2
EMBEDDING_API_KEY=your_gemini_key
STORAGE_ROOT=./storage
```

### Step 3: Boot Backend Engine
```bash
pip install -r requirements.txt
alembic upgrade head
fastapi dev app/main.py
```
*API active at `http://localhost:8000`. OpenAPI schema at `/docs`.*

### Step 4: Launch Frontend Interface
```bash
cd frontend
npm install
npm run dev
```
*Terminal active at `http://localhost:3000`.*

---

## ⮞ SECURITY & ACCESS CONTROL (RBAC)

NEXUS enforces a strict Role-Based Access Control matrix (`VIEWER`, `CONTRIBUTOR`, `ADMIN`).

1.  **Client-Side Guardrails:** Batch uploads (max 10 files) are validated for MIME type and size (15MB docs, 5MB images) before network transmission.
2.  **API Verification:** The `require_workspace_role()` permission service is the single enforcement point for all protected endpoints.
3.  **Data Escapement Prevention:** Unauthorized content never enters the LLM context window. Access restriction errors (`403`) are surfaced gracefully in the UI.

---

## ⮞ API TELEMETRY

| Method | Endpoint | Function |
| :--- | :--- | :--- |
| `POST` | `/api/v1/workspaces/` | Initialize workspace |
| `POST` | `/api/v1/documents/upload` | Ingest multi-format documents |
| `GET`  | `/api/v1/documents/{id}/status`| Poll processing matrix |
| `POST` | `/api/v1/conversations/` | Open communication channel |
| `GET`  | `/api/v1/conversations/{id}/messages/stream`| Stream SSE response |

---
*Built for HackStreak Third-Year Problem Statement.*
*NEXUS Engineering // "Truth through evidence."*