# NEXUS — Backend PRD
## AI Evidence Intelligence Workspace
### HackStreak Third-Year PS
### Aider Sprint Execution Specification

---

## 0. Purpose

This document is the implementation contract for the NEXUS backend.

The goal is not to build a generic enterprise RAG platform. The goal is to build the smallest technically real backend that satisfies the Third-Year problem statement and drives the approved NEXUS frontend end-to-end.

The PS requires:

- heterogeneous document support
- intelligent document processing and routing
- OCR and noisy-document handling
- semantic and contextual retrieval across documents
- multi-source reasoning
- conversational follow-up context
- source/page/section evidence
- explicit handling of conflicting or insufficient information without fabrication

The frontend contract already expects:

`UPLOAD → PROCESS → READY → SEARCH → ANSWER → CITATION → EVIDENCE → FOLLOW-UP`

The backend must make these states real.

---

# 1. Core Product Principle

NEXUS is not:

`PDF upload → chatbot`

NEXUS is:

`DOCUMENTS → UNDERSTAND → INDEX → RETRIEVE → COMBINE → ANSWER → PROVE`

The backend must make every step above traceable to real state.

Primary product promise:

> Ask NEX. Get the answer. See the proof.

Reliability promise:

> If the available evidence is insufficient or conflicting, NEX must say so rather than invent an answer.

---

# 2. Source Authority

This PRD is based on:

1. The HackStreak Third-Year problem statement.
2. The approved NEXUS frontend PRD.
3. The supplied ingestion/chunking/RAG material.

The problem statement is authoritative for required product behavior.

The frontend PRD is authoritative for API-facing UI states and response shapes.

The ingestion/chunking material informs implementation choices around parsing, structure, chunking, metadata, deduplication, failure handling, and retrieval quality.

Implementation technology choices in this document are recommendations, not requirements of the PS.

---

# 3. Backend Engineering Rules

## Rule 1 — Build the vertical slice first

The first objective is:

`upload → process → index → search → answer → evidence`

Do not spend the first half of the project building infrastructure.

## Rule 2 — Backend is the source of truth

The backend owns:

- document status
- processing stage
- access permissions
- retrieval results
- citations
- evidence
- conversation context
- reliability status

The frontend must not infer or fabricate them.

## Rule 3 — No fabricated evidence

Never invent:

- document names
- page numbers
- sections
- supporting text
- citations
- confidence
- processing progress

## Rule 4 — Permissions before retrieval

Unauthorized content must never enter the retrieval context sent to the LLM.

## Rule 5 — Retrieval is more than vector search

NEXUS must implement:

- semantic retrieval
- contextual query resolution
- structural/metadata context
- lexical retrieval where useful
- source-aware selection
- multi-source context assembly

## Rule 6 — Evidence is first-class

Every supported factual answer should be traceable:

`claim → evidence → chunk → page → document`

## Rule 7 — Keep architecture simple

Preferred:

- one API application
- one database
- one background worker
- one object-storage abstraction
- one LLM/embedding abstraction

Do not introduce microservices unless a real implementation blocker requires them.

---

# 4. Recommended Reference Stack

This is the recommended implementation stack for the hackathon, not a PS requirement.

### API
Python + FastAPI

### Database
PostgreSQL + pgvector

### Background processing
A lightweight database-backed worker/job queue

### Storage
Local persistent storage behind a storage interface; S3-compatible storage can be substituted later

### AI
Provider-abstracted:

- embedding model
- structured-output capable LLM
- optional vision model

### Parsing / processing
Use mature existing libraries rather than implementing PDF/OCR parsing from scratch.

---

# 5. High-Level Architecture

```text
                        FRONTEND
                           |
                           v
                    FASTAPI / API
                           |
          +----------------+----------------+
          |                |                |
          v                v                v
     PostgreSQL         Storage          AI APIs
      + pgvector
          ^
          |
          |
      WORKER
          |
          v
  DETECT → ROUTE → EXTRACT/OCR
          → STRUCTURE
          → CONTEXTUALIZE
          → CHUNK
          → HASH
          → EMBED
          → INDEX
```

Search path:

```text
USER QUERY
    |
    v
AUTHENTICATE
    |
    v
WORKSPACE + PERMISSION RESOLUTION
    |
    v
CONVERSATION CONTEXT
    |
    v
QUERY UNDERSTANDING / REWRITE
    |
    v
SEMANTIC + LEXICAL RETRIEVAL
    |
    v
RERANK / SOURCE-AWARE SELECTION
    |
    v
MULTI-SOURCE CONTEXT
    |
    v
CONFLICT / SUFFICIENCY ANALYSIS
    |
    v
GROUNDED GENERATION
    |
    v
CLAIM/EVIDENCE VALIDATION
    |
    v
STRUCTURED RESPONSE
```

---

# 6. Repository Structure

Recommended:

```text
backend/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── auth.py
│   │   ├── workspaces.py
│   │   ├── documents.py
│   │   ├── search.py
│   │   ├── conversations.py
│   │   └── evidence.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   └── errors.py
│   │
│   ├── db/
│   │   ├── session.py
│   │   ├── models/
│   │   └── migrations/
│   │
│   ├── schemas/
│   │   ├── users.py
│   │   ├── workspaces.py
│   │   ├── documents.py
│   │   ├── search.py
│   │   ├── conversations.py
│   │   └── evidence.py
│   │
│   ├── services/
│   │   ├── permissions.py
│   │   ├── documents.py
│   │   ├── search.py
│   │   ├── conversations.py
│   │   └── evidence.py
│   │
│   ├── processing/
│   │   ├── detector.py
│   │   ├── router.py
│   │   ├── pdf_pipeline.py
│   │   ├── ocr_pipeline.py
│   │   ├── image_pipeline.py
│   │   ├── table_pipeline.py
│   │   ├── structure.py
│   │   ├── contextualize.py
│   │   ├── chunker.py
│   │   ├── hashing.py
│   │   └── indexer.py
│   │
│   ├── retrieval/
│   │   ├── query.py
│   │   ├── embeddings.py
│   │   ├── vector_search.py
│   │   ├── keyword_search.py
│   │   ├── reranker.py
│   │   ├── source_selection.py
│   │   └── context.py
│   │
│   ├── generation/
│   │   ├── prompts.py
│   │   ├── planner.py
│   │   ├── answerer.py
│   │   ├── conflict.py
│   │   └── validator.py
│   │
│   ├── storage/
│   │   ├── interface.py
│   │   └── local.py
│   │
│   └── workers/
│       └── document_worker.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── eval/
│   ├── questions.json
│   └── run_eval.py
│
├── scripts/
│   ├── seed_demo.py
│   └── reset_demo.py
│
├── .env.example
├── README.md
└── AGENTS.md
```

Do not create modules before they are needed by a sprint.

---

# 7. Core Data Model

## 7.1 Users

```text
users
-----
id
name
email
auth_subject
created_at
```

Authentication implementation is environment-dependent.

---

## 7.2 Workspaces

```text
workspaces
----------
id
name
mode                  personal | organization
organization_id
created_at
```

---

## 7.3 Workspace memberships

```text
workspace_members
-----------------
workspace_id
user_id
role                  viewer | contributor | admin
created_at
```

---

## 7.4 Collections

```text
collections
-----------
id
workspace_id
name
created_at
```

---

## 7.5 Documents

```text
documents
---------
id
workspace_id
collection_id
name
mime_type
size_bytes
page_count
status
processing_stage
processing_progress
processing_route
storage_key
document_hash
metadata_json
uploaded_by
created_at
updated_at
error_code
error_message
```

Status:

```text
queued
processing
ready
failed
```

Stage:

```text
detecting
routing
extracting
ocr
structuring
indexing
ready
```

---

## 7.6 Document pages

```text
document_pages
--------------
id
document_id
page_number
page_text
ocr_text
metadata_json
preview_key
width
height
created_at
```

Page identity must be preserved.

---

## 7.7 Document chunks

```text
document_chunks
---------------
id
document_id
page_id
chunk_index
raw_text
contextual_text
section
heading
content_type
chunk_hash
metadata_json
embedding
created_at
```

Important:

- `raw_text` = evidence shown to the user
- `contextual_text` = retrieval representation
- `embedding` = embedding of contextualized text

---

## 7.8 Processing jobs

```text
processing_jobs
---------------
id
document_id
status
stage
attempt
progress
message
error_code
error_message
started_at
finished_at
created_at
```

Failures are persisted.

---

## 7.9 Conversations

```text
conversations
-------------
id
workspace_id
user_id
created_at
updated_at
```

---

## 7.10 Messages

```text
messages
--------
id
conversation_id
role
content
result_json
created_at
```

For assistant messages, preserve the structured search result used to generate the answer.

---

## 7.11 Evidence

```text
evidence
--------
id
chunk_id
document_id
page_number
section
text
relevance_score
metadata_json
created_at
```

Every evidence object must resolve to a stored chunk.

---

# 8. Permission Model

Permissions are small and explicit.

## Viewer

Can:

- view permitted documents
- search permitted documents
- ask questions
- view conversations
- view evidence
- open cited pages

Cannot:

- upload
- delete
- change access

## Contributor

Viewer plus:

- upload documents
- view processing status
- manage permitted documents
- retry failed processing

## Admin

Contributor plus:

- manage collections
- manage users/roles
- manage document/collection access
- inspect processing health

Do not implement a more complex IAM model unless necessary.

---

# 9. Permission Enforcement

Every protected operation follows:

```text
authenticate user
    ↓
resolve workspace
    ↓
check membership
    ↓
resolve permitted documents
    ↓
perform operation
```

Protected operations:

- document retrieval
- document listing
- semantic search
- lexical search
- evidence retrieval
- page preview
- download
- conversation retrieval

Critical rule:

```text
PERMISSIONS → RETRIEVAL
```

not:

```text
RETRIEVAL → LLM → REMOVE UNAUTHORIZED RESULTS
```

Unauthorized content must never enter the LLM context.

---

# 10. Ingestion Pipeline

Required pipeline:

```text
UPLOAD
  ↓
VALIDATE
  ↓
STORE ORIGINAL
  ↓
CREATE DOCUMENT RECORD
  ↓
QUEUE JOB
  ↓
DETECT
  ↓
ROUTE
  ↓
EXTRACT / OCR
  ↓
STRUCTURE
  ↓
NORMALIZE
  ↓
CONTEXTUALIZE
  ↓
CHUNK
  ↓
HASH / DEDUPE
  ↓
EMBED
  ↓
INDEX
  ↓
READY
```

Failure at any critical stage:

```text
FAILED
```

Never mark a document `ready` before indexing succeeds.

---

# 11. File Support

P0:

- PDF with selectable text
- scanned PDF
- PNG/JPEG/WebP
- table-containing documents

Do not invent unrelated formats.

The system may classify content internally as:

```text
text_pdf
scanned_pdf
image
table
mixed
```

---

# 12. Detection and Routing

Detection should use more than filename.

Inspect:

- MIME type
- extension
- PDF text density
- page/image ratio
- extracted text availability

Examples:

```text
normal PDF
→ text extraction

scanned PDF
→ OCR pipeline

image
→ OCR / vision pipeline

table-heavy content
→ table-aware structure extraction
```

The frontend only displays the backend-selected route.

---

# 13. PDF Processing

For normal PDFs:

- preserve page boundaries
- extract page text
- preserve available metadata
- identify headings/sections where possible
- identify tables/images when practical

Do not build a perfect PDF layout reconstruction system.

The requirement is searchable, attributable content.

---

# 14. OCR Processing

For scanned/noisy documents:

```text
page image
→ preprocessing
→ OCR
→ text normalization
→ page storage
```

Possible preprocessing:

- grayscale
- contrast normalization
- thresholding
- deskewing
- denoising
- resizing

Retain:

- page number
- OCR text
- source page

Do not silently invent uncertain OCR text.

If extraction yields unusable content, fail the job rather than falsely reporting `ready`.

---

# 15. Image Processing

For images:

```text
image
→ OCR
→ normalized text
→ optional vision interpretation
→ structure
→ chunk
→ embed
```

Vision should be selective rather than applied to every page.

Use vision when:

- image is the primary content
- OCR alone is insufficient
- image structure matters
- tables/diagrams are difficult to parse

---

# 16. Table Processing

Tables must preserve relational meaning.

Bad:

```text
Domestic 50000 International 75000 Approval Required
```

Preferred:

```text
Travel Type | Limit | Approval
Domestic    | 50000 | No
International | 75000 | Yes
```

Preserve:

- headers
- rows
- page number
- source document
- table context

Serialize structured table content into retrieval-friendly text.

---

# 17. Structure Extraction

Create normalized page elements where possible:

```text
heading
paragraph
list
table
image
```

Maintain page and section ancestry.

Example:

```text
Document: Travel Policy 2026
Section: Domestic Travel
Subsection: Hotel Accommodation
Page: 12
Text: The reimbursement limit is ₹50,000.
```

Do not fabricate missing structure.

---

# 18. Contextualized Chunking

This is a core NEXUS capability.

Do not embed only isolated raw fragments.

Example:

Raw:

```text
The limit is ₹50,000.
```

Contextualized:

```text
Travel Policy 2026
Section: Domestic Travel
Subsection: Hotel Accommodation
Page: 12

The limit is ₹50,000.
```

Store both.

Embed the contextualized representation.

Display the raw/source text as evidence.

---

# 19. Chunking Strategy

Use content-aware strategies.

### Prose

Start with recursive chunking.

Initial target:

- approximately 500 tokens
- approximately 100-token overlap

These are starting parameters, not immutable rules.

### OCR

Page-aware recursive chunking.

### Structured sections

Keep heading/section context attached.

### Tables

Use row/section-aware serialization rather than arbitrary character slicing.

Do not implement advanced semantic chunking unless evaluation proves the simpler strategy is inadequate.

---

# 20. Chunk Metadata

Each chunk must retain:

```text
document_id
page_id
page_number
section
heading
chunk_index
content_type
document_hash
chunk_hash
workspace_id
collection_id
```

This metadata supports:

- contextual retrieval
- provenance
- permissions
- evidence
- deduplication
- debugging

---

# 21. Hashing and Deduplication

Compute:

```text
document_hash = SHA-256(file bytes)
chunk_hash = SHA-256(normalized chunk content)
```

Duplicate document behavior:

```text
same workspace + same document hash
→ identify duplicate
→ do not reprocess unnecessarily
```

Chunk deduplication:

```text
same normalized chunk
→ reuse embedding where practical
```

Do not build a global deduplication platform.

Deduplication is primarily an ingestion optimization and correctness mechanism.

---

# 22. Embeddings

Every indexable chunk receives an embedding.

Embed:

`contextual_text`

not merely:

`raw_text`

Embedding provider must be configurable.

Do not couple core business logic to a single provider.

---

# 23. Semantic Retrieval

Semantic retrieval is mandatory.

Flow:

```text
query
→ query embedding
→ vector similarity
→ candidate chunks
```

Retrieval must be scoped to:

```text
workspace
+
permitted documents
+
optional document/collection filters
```

---

# 24. Lexical Retrieval

Implement keyword/lexical retrieval alongside vector retrieval.

This helps with:

- names
- exact phrases
- IDs
- dates
- policy codes
- exact numerical values

Basic hybrid flow:

```text
vector candidates
+
lexical candidates
→ merge
→ dedupe
→ rank
```

Do not add a separate search service for the hackathon.

---

# 25. Conversational Query Context

Follow-up questions must influence retrieval.

Example:

First:

```text
What is the reimbursement limit?
```

Follow-up:

```text
What about international travel?
```

Do not retrieve using only the second sentence.

The backend should construct a contextualized query using:

- current question
- recent conversation context
- known entities/topics
- current workspace

Output conceptually:

```json
{
  "original_query": "What about international travel?",
  "resolved_query": "What is the reimbursement limit for international travel?",
  "requires_multi_source": false
}
```

The resolved query does not need to be shown to the user.

---

# 26. Query Understanding

The query layer should identify lightweight intent, not become an autonomous agent.

Useful fields:

```text
resolved_query
entities
keywords
comparison_requested
multi_source_requested
document_filters
```

Possible query types:

```text
fact_lookup
comparison
summary
cross_document
follow_up
```

Do not build a general-purpose planning agent.

---

# 27. Candidate Retrieval

Initial retrieval target:

```text
vector top-k: 15–20
lexical top-k: 15–20
```

Then:

```text
merge
→ deduplicate
→ rerank
→ final context
```

Tune these against the demo evaluation set.

The exact values are configuration, not hard requirements.

---

# 28. Reranking

Vector similarity alone must not automatically determine final context.

The reranker should consider:

- query relevance
- contextualized chunk meaning
- exact term matches
- section relevance
- source diversity

P0 may use a lightweight reranker.

P1 may replace it with a stronger dedicated reranking model if available.

Do not block the vertical slice on advanced reranking.

---

# 29. Source-Aware Retrieval

For questions requiring multiple documents:

```text
candidate chunks
→ group by source document
→ preserve highly relevant sources
→ select strongest evidence from each
```

Example:

```text
Policy 2025
Policy 2026
Expense Table
```

should remain distinguishable in context.

Do not allow ten nearly-identical chunks from one document to crowd out another relevant source.

---

# 30. Context Assembly

The generator receives structured source blocks.

Example:

```text
SOURCE 1
Document: Policy_2025.pdf
Page: 12
Section: Reimbursement
Evidence:
"..."

SOURCE 2
Document: Policy_2026.pdf
Page: 4
Section: Reimbursement
Evidence:
"..."
```

Never send an anonymous concatenated text blob.

Source identity must survive into generation and validation.

---

# 31. Retrieval Sufficiency

Before generating a normal answer, determine whether retrieved material is sufficient.

Possible states:

```text
answered
insufficient_evidence
conflict
no_results
```

Do not rely only on the LLM's prose to decide this.

---

# 32. Insufficient Evidence

Return:

```json
{
  "status": "insufficient_evidence",
  "answer": null,
  "claims": [],
  "sources": [],
  "evidence": []
}
```

Use this when:

- no relevant evidence exists
- evidence is too weak
- retrieved material does not answer the question
- critical information is missing

Rule:

> No sufficient evidence → no definitive answer.

---

# 33. No Results

Return:

```json
{
  "status": "no_results",
  "answer": null,
  "sources": [],
  "evidence": []
}
```

This means nothing sufficiently relevant was found.

Keep this distinct from an actual evidence set that exists but is insufficient to answer.

---

# 34. Conflict Detection

Conflict is a first-class state.

Example:

```text
Policy 2025 → ₹50,000
Policy 2026 → ₹40,000
```

The system must preserve both source claims.

Do not silently pick one.

Return:

```json
{
  "status": "conflict",
  "sources": [
    {
      "document_id": "doc_2025",
      "page": 12,
      "claim": "₹50,000"
    },
    {
      "document_id": "doc_2026",
      "page": 4,
      "claim": "₹40,000"
    }
  ]
}
```

If source metadata explicitly establishes a relationship such as supersession, that information may be surfaced.

Do not infer authority solely from a newer date.

---

# 35. Answer Planner

Before generation, classify the response task:

```text
single-source factual answer
multi-source synthesis
comparison
conflict response
insufficient evidence
```

The planner controls the generation mode.

Example:

```text
comparison
→ require evidence from both relevant sources
```

Example:

```text
conflict
→ present disagreement
→ do not generate a single definitive winner
```

---

# 36. Grounded Generation

The generation model receives:

- system instructions
- normalized user question
- conversation context
- retrieved evidence
- source metadata
- answer mode

Core rules:

```text
Answer only from supplied evidence.

Do not invent facts.

Do not invent source names.

Do not invent pages.

Do not invent sections.

Do not invent citations.

When evidence is insufficient, say so.

When evidence conflicts, surface the conflict.
```

---

# 37. Structured Generation Contract

Prefer structured model output:

```json
{
  "status": "answered",
  "answer": {
    "text": "The reimbursement limit is ₹50,000.",
    "source_count": 2
  },
  "claims": [
    {
      "text": "The reimbursement limit is ₹50,000.",
      "evidence_ids": ["ev_123"]
    }
  ],
  "source_ids": ["doc_1", "doc_2"]
}
```

Do not allow arbitrary model text to become the final API response without validation.

---

# 38. Claim / Evidence Validation

Validation pipeline:

```text
model response
→ schema validation
→ evidence IDs exist?
→ evidence belongs to retrieved context?
→ evidence belongs to accessible documents?
→ source metadata consistent?
→ persist
→ return
```

If validation fails:

```text
SEARCH_ERROR
```

Do not manufacture missing evidence.

---

# 39. Evidence Provenance

Recommended trace:

```text
CLAIM
  ↓
EVIDENCE ID
  ↓
CHUNK
  ↓
PAGE
  ↓
DOCUMENT
  ↓
ORIGINAL FILE
```

Evidence must remain traceable after:

- reprocessing
- retry
- document listing
- conversation retrieval

---

# 40. Conversation Persistence

First question may create a conversation.

Subsequent questions:

```text
POST /conversations/{conversation_id}/messages
```

The backend owns conversation memory.

Use a bounded recent-message window for the hackathon.

Suggested:

```text
6–10 recent messages
```

Do not implement long-term semantic memory unless needed.

---

# 41. Document Preview

Required behavior:

```text
authorized document
→ requested page
→ page preview
```

For PDFs:

- render/load requested page
- return through an authenticated route or temporary private URL

No permanent public URLs for private documents.

---

# 42. API Contract

Base prefix:

`/api/v1`

## Identity

### GET `/me`

Returns current user and available workspaces.

---

## Workspace

### GET `/workspaces`

Returns accessible workspaces.

### GET `/workspace/{workspace_id}/overview`

Returns:

```json
{
  "metrics": {
    "documents": 24,
    "pages": 1284,
    "indexed_chunks": 8492,
    "processing_jobs": 2
  },
  "documents": []
}
```

Metrics must come from actual database state.

---

## Documents

### POST `/documents/upload`

Multipart fields:

```text
file
workspace_id
collection_id?
```

Returns immediately:

```json
{
  "document": {
    "id": "doc_123",
    "name": "Policy.pdf",
    "mimeType": "application/pdf",
    "status": "queued"
  }
}
```

### GET `/documents`

Filters:

```text
workspace_id
status
collection_id
file_type
search
```

### GET `/documents/{document_id}/status`

Returns:

```json
{
  "document_id": "doc_123",
  "status": "processing",
  "stage": "ocr",
  "progress": 62,
  "message": "Extracting content from page 31 of 50"
}
```

### POST `/documents/{document_id}/retry`

Contributor/Admin only, subject to permission.

---

## Search

### POST `/search`

Request:

```json
{
  "workspace_id": "workspace_123",
  "conversation_id": "conv_456",
  "query": "What is the reimbursement limit?",
  "document_ids": [],
  "collection_ids": []
}
```

The backend still enforces authorization even when filters are supplied.

---

## Conversations

### POST `/conversations`

Creates a conversation.

### GET `/conversations/{conversation_id}`

Returns thread.

### POST `/conversations/{conversation_id}/messages`

Request:

```json
{
  "query": "What about international travel?"
}
```

Returns the same structured search contract.

---

## Evidence

### GET `/documents/{document_id}/evidence`

Optional:

```text
?page=12
&evidence_id=ev_123
```

### GET `/documents/{document_id}/pages/{page_number}/preview`

Authorization required.

---

# 43. Standard Search Response

Minimum:

```json
{
  "status": "answered",
  "conversation_id": "conv_123",

  "answer": {
    "text": "The reimbursement limit is ₹50,000.",
    "source_count": 2
  },

  "claims": [
    {
      "text": "The reimbursement limit is ₹50,000.",
      "evidence_ids": ["ev_1"]
    }
  ],

  "sources": [
    {
      "document_id": "doc_1",
      "document_name": "Employee_Policy.pdf",
      "page": 12,
      "used": true
    }
  ],

  "evidence": [
    {
      "id": "ev_1",
      "document_id": "doc_1",
      "document_name": "Employee_Policy.pdf",
      "page": 12,
      "section": "Reimbursement",
      "text": "Employees may claim reimbursement..."
    }
  ]
}
```

Search status is authoritative:

```text
answered
insufficient_evidence
conflict
no_results
error
```

---

# 44. Processing State Contract

Frontend-visible lifecycle:

```text
QUEUED
↓
DETECTING
↓
ROUTING
↓
EXTRACTING / OCR
↓
STRUCTURING
↓
INDEXING
↓
READY
```

Failure:

```text
FAILED
```

The frontend must only display progress supplied by backend state.

---

# 45. Error Contract

Use:

```json
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "The requested document could not be found."
  }
}
```

Known categories:

```text
UNAUTHORIZED
FORBIDDEN
NOT_FOUND
VALIDATION_ERROR
CONFLICT
RATE_LIMITED
PROCESSING_ERROR
SEARCH_ERROR
INTERNAL_ERROR
```

Never expose stack traces.

---

# 46. Security

Minimum:

- authenticated API access
- workspace authorization
- document authorization
- evidence authorization
- page preview authorization
- download authorization
- file size limits
- MIME validation
- safe filenames/storage keys
- path traversal protection
- no public private-file paths
- no unauthorized content in AI context

---

# 47. Prompt Injection Defense

Document content is untrusted data.

The model must treat retrieved document text as evidence, not instructions.

Prompt structure should explicitly separate:

```text
SYSTEM RULES
USER QUESTION
CONVERSATION CONTEXT
RETRIEVED EVIDENCE
```

Do not let retrieved text override system behavior.

This is P1 for the hackathon but should be designed into the generation boundary from the beginning.

---

# 48. Logging

Log enough to debug the demo without logging sensitive content by default.

Processing:

```text
document_id
job_id
stage
attempt
duration
status
error_code
```

Search:

```text
query_id
workspace_id
conversation_id
retrieved_count
reranked_count
source_count
status
latency
```

Never log raw document contents unnecessarily.

---

# 49. Evaluation Harness

Create:

```text
eval/questions.json
eval/run_eval.py
```

The evaluation set should contain approximately 10–20 known questions covering:

- semantic lookup
- exact lookup
- contextual follow-up
- multi-source synthesis
- conflict
- insufficient evidence
- OCR document
- table content

Each test should record expected source/page information where practical.

Minimum evaluation question shape:

```json
{
  "question": "What is the domestic hotel reimbursement limit?",
  "expected": [
    {
      "document": "Travel_Policy_2026.pdf",
      "page": 12
    }
  ]
}
```

The first evaluation goal is retrieval correctness, not fancy LLM scoring.

---

# 50. Demo Dataset

Prepare four documents:

1. normal text PDF
2. scanned/noisy PDF
3. image/table document
4. related or conflicting document

The content should be deliberately designed so the demo exposes:

- multi-source retrieval
- OCR
- evidence
- follow-up context
- insufficient evidence
- conflict

---

# 51. Seed Scripts

### `scripts/seed_demo.py`

Must create:

- demo workspace
- demo users
- collections
- permissions
- demo documents

Where practical, run the real ingestion pipeline against the demo documents.

### `scripts/reset_demo.py`

Must reset the demo data cleanly.

The demo should be repeatable.

---

# 52. Sprint Model

Each sprint follows the same loop:

```text
READ PRD
→ inspect current code
→ implement only sprint scope
→ run targeted tests
→ run integration tests where applicable
→ update BUILD_STATE.md
→ update AGENTS.md if a reusable rule was discovered
→ stop
```

Do not silently pull work forward from later sprints.

---

# 53. Sprint 0 — Repository and Contract Foundation

## Goal

Create the backend skeleton and lock the contracts.

## Build

- FastAPI app
- configuration
- database connection
- migrations
- core models
- Pydantic schemas
- health endpoint
- `/api/v1` routing
- provider interfaces
- storage interface
- error model

## Create

```text
AGENTS.md
BUILD_STATE.md
BUILD_BLOCKERS.md
```

## Acceptance

```text
GET /api/v1/health → 200

database connects

migrations run

app starts cleanly

OpenAPI loads

tests run
```

## Do not build

- document parsing
- retrieval
- LLM calls
- admin UI
- advanced authentication

---

# 54. Sprint 1 — Workspace, Identity, Permissions

## Goal

Make workspace and authorization real before retrieval exists.

## Build

- `/me`
- workspace model
- workspace membership
- roles
- collection model
- permission service
- development auth mode
- authorization dependencies

## Acceptance

Viewer/Contributor/Admin permissions are testable.

A user cannot access another workspace.

Permission checks are reusable from services.

## Critical test

```text
User A
→ cannot access User B's workspace/document
```

---

# 55. Sprint 2 — Upload and Processing Jobs

## Goal

Get a real document into storage and show truthful asynchronous processing state.

## Build

- upload endpoint
- storage implementation
- document creation
- processing job creation
- worker
- status endpoint
- retry endpoint
- failure persistence

## Acceptance

```text
upload
→ 200/201 immediately
→ document = queued
→ worker processes
→ status changes over time
```

A failed job remains failed.

Retry creates a valid new attempt.

---

# 56. Sprint 3 — Document Intelligence / Ingestion

## Goal

Make heterogeneous documents searchable.

## Build

- detector
- route selection
- normal PDF pipeline
- OCR pipeline
- image pipeline
- table handling
- page extraction
- metadata
- structure extraction

## Acceptance

All four demo document types produce usable page-level content.

Example:

```text
normal PDF → extracted text
scanned PDF → OCR text
image → OCR/vision text
table → structured text
```

The original file is preserved.

---

# 57. Sprint 4 — Contextual Chunking and Indexing

## Goal

Turn extracted content into high-quality retrieval units.

## Build

- contextualized text generation
- content-aware chunking
- raw/contextual text storage
- document hash
- chunk hash
- deduplication
- embeddings
- pgvector index

## Acceptance

For each chunk:

```text
document_id
page_number
section
raw_text
contextual_text
chunk_hash
embedding
```

exists.

A retry does not create uncontrolled duplicates.

---

# 58. Sprint 5 — Semantic + Contextual Retrieval

## Goal

Implement the core intelligence of NEXUS.

## Build

- contextual query resolution
- conversation-aware query rewrite
- semantic retrieval
- lexical retrieval
- candidate merge
- deduplication
- reranking
- source-aware selection
- multi-source context assembly

## Acceptance

### Semantic

A paraphrased question retrieves the correct evidence.

### Contextual

A follow-up question uses previous conversation context.

### Multi-source

A comparison question retrieves evidence from multiple documents.

### Security

Only permitted documents participate in retrieval.

---

# 59. Sprint 6 — Grounded Answering and Reliability

## Goal

Turn retrieved evidence into reliable structured answers.

## Build

- answer planner
- structured LLM generation
- grounding prompt
- claim/evidence mapping
- validation
- insufficient-evidence logic
- no-results logic
- conflict detection
- conflict response

## Acceptance

### Answered

Returns answer + evidence.

### Insufficient

Returns no fabricated answer.

### Conflict

Returns conflicting source claims without silently selecting a winner.

### Validation

A nonexistent evidence ID can never reach the frontend.

---

# 60. Sprint 7 — Evidence, Conversations, Preview

## Goal

Complete the judge-critical evidence experience.

## Build

- conversation persistence
- follow-up endpoint
- evidence endpoint
- page preview
- authorized document access
- stored assistant result

## Acceptance

```text
question
→ answer
→ click citation
→ evidence
→ page
→ follow-up
```

works with real backend data.

---

# 61. Sprint 8 — Integration, Evaluation, Hardening

## Goal

Make the backend demo-safe.

## Build

- evaluation harness
- seed/reset scripts
- health checks
- structured logs
- error cleanup
- performance cleanup
- permission regression tests
- frontend contract verification

## Run exact demo

```text
1. Open Home
2. Upload 3–4 documents
3. Show processing
4. Wait for Ready
5. Ask complex multi-source question
6. Show answer
7. Click citation
8. Show evidence
9. Ask follow-up
10. Ask unsupported question
11. Show insufficient evidence
12. Trigger/show conflict
```

## Stop condition

Do not add features after this flow is reliable.

---

# 62. Sprint Dependencies

```text
Sprint 0
  ↓
Sprint 1
  ↓
Sprint 2
  ↓
Sprint 3
  ↓
Sprint 4
  ↓
Sprint 5
  ↓
Sprint 6
  ↓
Sprint 7
  ↓
Sprint 8
```

Some work may overlap after interfaces are stable, but the critical dependencies should remain intact.

---

# 63. Aider Operating Rules

Aider must:

1. Read this PRD before every sprint.
2. Inspect the repository before modifying code.
3. Preserve existing working behavior.
4. Make the smallest coherent change for the sprint.
5. Add/update tests with every backend capability.
6. Run targeted tests before moving forward.
7. Never invent API fields that are not part of this contract.
8. Never hard-code demo answers.
9. Never hard-code citations.
10. Never return unauthorized documents.
11. Never mark a document ready without completed indexing.
12. Never silently swallow processing failures.
13. Update `BUILD_STATE.md` after each sprint.
14. Record blockers in `BUILD_BLOCKERS.md`.
15. Stop at the sprint acceptance criteria.

---

# 64. Aider Anti-Patterns

Do NOT:

- rewrite the project unnecessarily
- introduce microservices
- add a new database without need
- add a new vector database when pgvector is sufficient
- build a custom PDF parser
- build custom OCR from scratch
- build an agent swarm
- build a knowledge graph
- add web search
- add internet fact checking
- implement fine-tuning
- implement complex IAM
- add analytics dashboards
- invent confidence scores
- add fake retrieval scores to responses
- hard-code demo answers
- bypass permissions for demo convenience

---

# 65. When to Simplify

When a component becomes difficult to implement, prefer the simpler valid implementation.

Examples:

Instead of WebSockets:

`poll document status`

Instead of microservices:

`background worker`

Instead of vector database infrastructure:

`PostgreSQL + pgvector`

Instead of semantic chunking:

`structure-aware recursive chunking`

Instead of an agent framework:

`query resolver + answer planner`

Instead of a complex PDF viewer:

`page preview endpoint`

Instead of an enterprise IAM:

`three roles + collection/document permissions`

---

# 66. P0 / P1 / P2

## P0

- PDF ingestion
- scanned PDF/OCR
- image support
- table support
- structure/page preservation
- contextual chunking
- embeddings
- semantic retrieval
- conversational query context
- multi-source retrieval
- grounded generation
- evidence attribution
- insufficient evidence
- conflict
- conversations
- page evidence
- processing state
- permission-filtered retrieval

## P1

- lexical retrieval
- reranking
- source-aware selection
- deduplication
- document version metadata
- robust permission administration
- prompt injection defense
- evaluation harness
- richer observability
- retry improvements

## P2

- streaming
- page bounding boxes
- advanced rerankers
- advanced vision
- sophisticated semantic chunking
- event streaming
- advanced admin UI
- caching
- knowledge graphs
- agentic retrieval

---

# 67. Non-Goals

Explicitly out of scope:

- billing
- subscription management
- notifications center
- team collaboration UI
- document editing
- annotation tools
- custom model training
- long-term personal memory
- universal web fact checking
- internet search
- enterprise SSO
- complex workflow automation
- recommendation systems
- analytics platform

---

# 68. Golden Backend Acceptance Test

The backend is considered functionally complete when this chain passes:

```text
UPLOAD
  ↓
VALIDATE
  ↓
STORE
  ↓
QUEUE
  ↓
DETECT
  ↓
ROUTE
  ↓
EXTRACT / OCR
  ↓
STRUCTURE
  ↓
CONTEXTUALIZE
  ↓
CHUNK
  ↓
EMBED
  ↓
INDEX
  ↓
READY
  ↓
USER QUERY
  ↓
PERMISSION FILTER
  ↓
CONTEXTUAL QUERY
  ↓
SEMANTIC + LEXICAL RETRIEVAL
  ↓
RERANK
  ↓
SOURCE-AWARE SELECTION
  ↓
MULTI-SOURCE CONTEXT
  ↓
CONFLICT / SUFFICIENCY CHECK
  ↓
GROUNDED GENERATION
  ↓
EVIDENCE VALIDATION
  ↓
ANSWER
  ↓
CITATION
  ↓
PAGE PROOF
  ↓
FOLLOW-UP
```

---

# 69. Final Definition of Done

## Ingestion

- [ ] normal PDF works
- [ ] scanned PDF works
- [ ] OCR works
- [ ] noisy OCR has a useful failure path
- [ ] image input works
- [ ] tables remain understandable
- [ ] page identity is preserved
- [ ] metadata is retained
- [ ] contextualized chunks are generated
- [ ] duplicate content is safely handled

## Retrieval

- [ ] semantic retrieval works
- [ ] contextual query rewrite works
- [ ] conversation context affects retrieval
- [ ] retrieval works across multiple documents
- [ ] source identity is preserved
- [ ] permission filtering occurs before retrieval
- [ ] final context is source-aware

## AI

- [ ] answer is grounded in supplied evidence
- [ ] structured response is validated
- [ ] claim/evidence mapping works
- [ ] insufficient evidence is explicit
- [ ] no-results is explicit
- [ ] conflicts are explicit
- [ ] no fabricated citations

## Evidence

- [ ] source is returned
- [ ] page is returned
- [ ] section is returned when available
- [ ] supporting text is returned
- [ ] evidence resolves to actual chunks
- [ ] cited page can be opened
- [ ] unauthorized evidence cannot be opened

## Conversations

- [ ] conversation persists
- [ ] follow-up works
- [ ] follow-up uses context
- [ ] conversation access is authorized

## Engineering

- [ ] migrations work
- [ ] worker works
- [ ] health endpoint works
- [ ] seed/reset works
- [ ] errors are structured
- [ ] no stack traces leak
- [ ] API contract matches frontend
- [ ] evaluation set passes
- [ ] golden demo flow works

---

# 70. Final Instruction to the Coding Agent

Do not optimize for architectural sophistication.

Optimize for this:

> A judge uploads messy documents, asks a difficult question, sees NEX retrieve information from multiple sources, sees an answer, clicks the citation, verifies the source page, asks a follow-up question, and then deliberately asks something unsupported and sees NEX refuse to fabricate an answer.

Everything in the backend exists to make that experience real.

Build that first.

Then make it reliable.
