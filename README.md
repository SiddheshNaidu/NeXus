# NEXUS

**AI Evidence Intelligence Workspace**

*Ask what your documents know.*

[![Next.js](https://img.shields.io/badge/Next.js-16.3-black?logo=nextdotjs)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![pgvector](https://img.shields.io/badge/PostgreSQL-pgvector-336791?logo=postgresql)](https://github.com/pgvector/pgvector)
[![Gemini](https://img.shields.io/badge/Google_Gemini-AI-4285F4?logo=google)](https://ai.google.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript)](https://www.typescriptlang.org)

---

## What is NEXUS?

NEXUS is an evidence intelligence platform. Upload documents. Ask questions. Get answers with proof.

The AI assistant, **NEX**, retrieves relevant chunks from your indexed documents, combines information across sources, and returns a grounded answer with clickable citations that trace every claim back to the exact page and passage it came from.

NEXUS does not guess. If the evidence is insufficient or conflicting, it says so. No fabricated citations. No hallucinated page numbers. Every displayed reference originates from backend data.

---

## The Architecture

The system works in two distinct phases, both fully implemented.

**Ingestion** routes each uploaded file through a detection pipeline, selecting the correct processing path based on content type — text extraction for standard PDFs, OCR for scanned documents and images, structured parsing for table-heavy content. Documents move through the states `queued -> detecting -> routing -> extracting -> structuring -> indexing -> ready`. The frontend reflects this asynchronously; the interface never blocks on the pipeline.

**Retrieval** begins when a user submits a query. NEX embeds the question using Google Gemini, performs pgvector cosine-similarity search scoped strictly to the user's workspace, constructs a context block from the top-5 chunks, and streams the answer token-by-token via SSE. Evidence rows are persisted alongside every response so citations are always traceable to a real stored chunk.

```
QUERY
  |
  v
EMBED (Google Gemini Embeddings)
  |
  v
VECTOR SEARCH  <-- pgvector cosine similarity, workspace-scoped
  |
  v
CONTEXT ASSEMBLY  <-- top-5 chunks, source-attributed
  |
  v
LLM GENERATION  <-- Gemini Flash, system-prompted to cite only evidence
  |
  v
SSE STREAM -> evidence event -> text tokens -> done event
  |
  v
DB PERSIST  <-- user message, assistant message, evidence rows
```

---

## The Interface

The workspace is a three-column layout built on `#050505` black, 1px structural grid lines, Geist Sans/Mono typography, and an indigo accent.

**Source Rail** (left column) lists all documents indexed in the current workspace with their processing status. Empty state prompts ingestion.

**Answer Canvas** (center column) renders the conversation thread. NEX answers stream progressively. Citation chips appear once the structured response arrives, not before. Clicking a chip opens the Evidence Inspector inline on desktop or navigates to the full Evidence Viewer on mobile.

**Evidence Inspector** (right column) displays the active citation: document title, page number, section, and the extracted passage rendered in serif italic against an indigo left border. An *Inspect Document* link navigates to the full evidence page for that document.

Edge states are explicit and rendered from backend data:

| State | Trigger |
|---|---|
| `NEXUS Verified Response` | Answered with citations |
| `Insufficient Evidence` | No supporting information found |
| `Evidence Conflict Detected` | Sources disagree; both shown side by side |
| `No Results` | No relevant evidence across indexed sources |
| `Clearance Restricted` | Relevant information exists; user lacks access |
| `Engine Error` | Backend unreachable or failed |

The home page features a WebGL NEX model sequence (Three.js / React Three Fiber), particle contact field, aether flow background, and Lenis smooth scrolling with GSAP and Motion animations.

---

## Tech Stack

### Frontend

| Layer | Technology |
|---|---|
| Framework | Next.js 16.3 (App Router) |
| Language | TypeScript 5 |
| Styling | Tailwind CSS v4 |
| Animation | Motion (Framer Motion), GSAP 3, Anime.js 4, Lenis |
| 3D | Three.js, React Three Fiber, Drei |
| Icons | Phosphor Icons |
| HTTP | Fetch API with SSE streaming |

### Backend

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.115+ (async) |
| Language | Python 3.12+ |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 16 + pgvector |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| AI Provider | Google Gemini (LLM + Embeddings) |
| Testing | pytest, pytest-asyncio, httpx |

---

## Project Structure

```
NeXus/
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── page.tsx                          # Home: knowledge base + 3D hero
│       │   ├── search/page.tsx                   # Three-column workspace
│       │   ├── upload/page.tsx                   # Document ingestion
│       │   └── evidence/[documentId]/page.tsx    # Full evidence viewer
│       ├── components/
│       │   ├── immersive/                        # WebGL scenes (NEXsequence, EvidenceScene)
│       │   └── ui/                               # Navbar, particles, hero, story section
│       ├── services/
│       │   ├── types.ts                          # TypeScript contracts (derived from Pydantic schemas)
│       │   ├── apiClient.ts                      # Fetch + SSE transport layer
│       │   ├── searchService.ts                  # Conversation creation, streaming questions
│       │   ├── documentsService.ts
│       │   └── evidenceService.ts
│       └── hooks/
│           ├── useNexusSession.ts                # Workspace + identity resolution
│           └── useAudioReactive.ts
│
└── backend/
    └── app/
        ├── main.py                               # CORS, error handlers, router mount
        ├── core/
        │   ├── config.py                         # Pydantic settings (DB, LLM keys, storage)
        │   ├── security.py
        │   └── errors.py                         # NexusError + exception handlers
        ├── db/
        │   ├── session.py                        # Async SQLAlchemy engine
        │   └── models/                           # users, workspaces, documents, chunks, evidence
        ├── schemas/                              # Pydantic v2 request/response shapes
        ├── services/
        │   ├── chat.py                           # RAG: embed -> retrieve -> generate -> persist
        │   ├── documents.py
        │   ├── permissions.py
        │   └── evidence.py
        ├── providers/
        │   ├── embeddings.py                     # Gemini embedding abstraction
        │   └── llm.py                            # Gemini LLM abstraction (complete + stream)
        └── api/v1/                               # Route handlers
```

---

## Getting Started

### Prerequisites

- Node.js 20+
- Python 3.12+
- Docker (for the database)
- A Google Gemini API key

### 1. Start the database

```bash
cd backend
docker-compose up -d
```

This starts PostgreSQL 16 with the pgvector extension on port `5432`.

### 2. Configure the backend

```bash
cd backend
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/nexus

LLM_PROVIDER=google
LLM_MODEL=gemini-2.0/3.X-flash-lite
LLM_API_KEY=your_google_api_key_here

EMBEDDING_PROVIDER=google
EMBEDDING_MODEL=gemini-embedding-2
EMBEDDING_API_KEY=your_google_api_key_here
EMBEDDING_DIMENSION=1536

STORAGE_ROOT=./storage
```

### 3. Install and run the backend

```bash
pip install -r requirements.txt
alembic upgrade head
fastapi dev app/main.py
```

API runs at `http://localhost:8000`. Interactive docs at `/docs`.

### 4. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:3000`.

---

## API Reference

Full OpenAPI documentation is available at `http://localhost:8000/docs`.

```
POST   /api/v1/workspaces/
GET    /api/v1/workspaces/{id}/

POST   /api/v1/documents/upload                    Upload document (multipart/form-data)
GET    /api/v1/documents/{id}/status               Processing status + stage + progress
GET    /api/v1/documents/?workspace_id=<id>        List workspace documents

POST   /api/v1/conversations/                      Create conversation
POST   /api/v1/conversations/{id}/messages         Send message (non-streaming)
GET    /api/v1/conversations/{id}/messages/stream  SSE streaming response
GET    /api/v1/conversations/{id}/messages         Conversation history

GET    /api/v1/evidence/{id}/
GET    /api/v1/health
```

**SSE streaming format:**

```
data: {"type": "evidence", "chunks": [...]}

data: {"type": "text", "text": "The reimbursement limit is..."}

data: {"type": "done"}
```

Evidence arrives before the text stream begins. Citation chips render only after the `done` event.

---

## The Evidence Contract

Every evidence object traces back to a stored chunk in the database. The backend never manufactures page numbers, source names, or supporting text. The frontend never infers them.

```typescript
interface EvidenceRead {
  id: string;
  chunk_id: string;
  document_id: string;
  page_number: number | null;
  section: string | null;
  text: string;
  relevance_score: number | null;
}
```

The security boundary is the backend. Permissions are enforced before retrieval, not after. Unauthorized content never enters the LLM context.

---

## Roles and Permissions

| Role | Upload | Search | Manage Access |
|---|---|---|---|
| Viewer | No | Yes | No |
| Contributor | Yes | Yes | No |
| Admin | Yes | Yes | Yes |

Permissions apply to both documents and collections. Access is not controlled by hiding UI elements.

---

## Processing Pipeline

```
QUEUED -> DETECTING -> ROUTING -> EXTRACTING -> STRUCTURING -> INDEXING -> READY
```

| Content Type | Pipeline |
|---|---|
| Standard PDF (selectable text) | Text extraction |
| Scanned PDF | OCR pipeline |
| PNG / JPEG / WebP | Vision / OCR |
| Table-heavy documents | Structured table parsing |

A document reaches `READY` only after indexing succeeds. Any critical failure transitions it to `FAILED` and preserves the error code and message for display.

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL async connection string | `postgresql+asyncpg://...` |
| `STORAGE_ROOT` | Local file storage path | `./storage` |
| `LLM_PROVIDER` | LLM provider identifier | `google` |
| `LLM_MODEL` | Model name | `gemini-2.0-flash-lite` |
| `LLM_API_KEY` | Provider API key | — |
| `EMBEDDING_PROVIDER` | Embedding provider | `google` |
| `EMBEDDING_MODEL` | Embedding model name | `gemini-embedding-2` |
| `EMBEDDING_API_KEY` | Provider API key | — |
| `EMBEDDING_DIMENSION` | Vector dimension | `1536` |
| `DEBUG` | Enable debug mode | `false` |

---

## Running Tests

```bash
cd backend
pytest
```

Test suites cover health checks, permissions enforcement, document upload and processing, search pipeline, and streaming evidence. Fixtures span five sprint configurations in `tests/conftest_sprint*.py`.

---

*Built for HackStreak Third-Year Problem Statement.*

*Ask NEX. Get the answer. See the proof.*