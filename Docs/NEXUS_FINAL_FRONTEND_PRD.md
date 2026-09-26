NEXUS

AI Evidence Intelligence Workspace

Technical Frontend PRD --- HackStreak Third-Year PS

------------------------------------------------------------------------

0.  FRONTEND AGENT CONTRACT

You are the FRONTEND ENGINEERING AGENT.

Your job is to build the frontend described in this document.

Do not change

Do NOT change the existing visual/art direction:

-   Awwwards-style editorial composition
-   cinematic dark interface
-   premium enterprise aesthetic
-   restrained electric blue-violet accent
-   strong typography
-   Motion/Framer Motion interactions
-   21st.dev-inspired React components
-   three-column AI workspace
-   source rail
-   answer canvas
-   evidence inspector
-   document viewer
-   intentional micro-interactions

The visual design is already approved.

Your job is to make the interface technically precise and backend-ready.

------------------------------------------------------------------------

1.  PRODUCT DEFINITION

Product

NEXUS

AI assistant:

NEX

Product purpose

NEXUS is an evidence intelligence platform.

It allows users to upload heterogeneous documents and ask questions
about them.

The system retrieves relevant information from the user's permitted
sources, combines information across sources, and returns an answer with
visible evidence.

The system must never invent citations or pretend that unsupported
information exists.

------------------------------------------------------------------------

2.  TWO USAGE MODES

NEXUS supports two product contexts.

2.1 Personal Mode

For individual users.

Primary use cases:

-   fact checking
-   research
-   comparing documents
-   understanding reports
-   checking claims against supplied evidence
-   extracting information from PDFs/images/scans

Personal users have a private workspace.

Their uploaded documents belong to their workspace.

Other users cannot access them.

No organization-level permissions are required in Personal Mode.

------------------------------------------------------------------------

2.2 Organization Mode

For organizations that maintain private document collections.

Examples:

-   HR
-   Finance
-   Legal
-   Operations
-   Research
-   Compliance
-   Internal knowledge

Users belong to an organization.

Documents belong to the organization's workspace.

Access is controlled through roles and document/collection permissions.

The frontend must never assume that every authenticated organization
user can access every document.

------------------------------------------------------------------------

3.  RBAC

RBAC is intentionally small.

Do not create a complicated enterprise IAM system.

Roles

Viewer

Can:

-   view permitted documents
-   search permitted documents
-   ask NEX questions
-   view conversations
-   inspect evidence
-   open cited document pages

Cannot:

-   upload documents
-   delete documents
-   modify document permissions

------------------------------------------------------------------------

Contributor

Everything a Viewer can do.

Additionally:

-   upload documents
-   view processing status
-   manage documents they are permitted to manage
-   retry failed processing where permitted

------------------------------------------------------------------------

Admin

Everything a Contributor can do.

Additionally:

-   manage workspace document access
-   manage users/roles
-   manage collections
-   view system/document processing health

------------------------------------------------------------------------

4.  PERMISSION MODEL

Permissions are applied to documents and collections, not only users.

Conceptual model:

Organization \| +-- Collection \| \| \| +-- Document \| +-- Document \|
+-- Collection \| +-- Document

Example:

HR Collection ├── Employee Handbook.pdf ├── Leave Policy.pdf └──
Benefits.pdf

Finance Collection ├── Expense Policy.pdf └── Annual Report.pdf

A user may have:

HR READ Finance NONE

The frontend must reflect access returned by the backend.

Do not hard-code permissions in the frontend.

------------------------------------------------------------------------

5.  SECURITY PRINCIPLE

The frontend is NOT the security boundary.

Hiding a document from the UI is not sufficient.

The backend must enforce access before:

-   document retrieval
-   semantic search
-   evidence retrieval
-   document preview
-   document download

The frontend only renders permissions supplied by the backend.

Never assume:

hidden UI = secure

The frontend must send authenticated requests.

------------------------------------------------------------------------

6.  CORE DATA MODEL

The frontend should expect the following conceptual entities.

User

type User = { id: string name: string email: string avatarUrl?: string }

Workspace

type Workspace = { id: string name: string mode: "personal" \|
"organization" organizationId?: string role?: "viewer" \| "contributor"
\| "admin" }

------------------------------------------------------------------------

Document

type Document = { id: string name: string mimeType: string sizeBytes:
number pageCount?: number

status: \| "queued" \| "processing" \| "ready" \| "failed"

processingStage?: \| "detecting" \| "routing" \| "extracting" \| "ocr"
\| "structuring" \| "indexing" \| "ready"

processingProgress?: number

createdAt: string updatedAt: string

collectionId?: string uploadedBy?: string

access?: { canRead: boolean canManage: boolean } }

------------------------------------------------------------------------

7.  DOCUMENT PROCESSING MODEL

The frontend must represent processing as an asynchronous workflow.

The frontend must NOT assume:

upload → immediately ready

Actual workflow:

UPLOAD ↓ QUEUED ↓ DETECTING ↓ ROUTING ↓ EXTRACTING / OCR ↓ STRUCTURING ↓
INDEXING ↓ READY

Possible terminal failure:

PROCESSING ↓ FAILED

------------------------------------------------------------------------

8.  MULTI-PIPELINE PROCESSING

The backend decides which pipeline to use.

Possible processing routes:

Text PDF → text extraction

Scanned PDF → OCR / vision extraction

Image → vision / OCR

Table → table extraction / structured parsing

The frontend does not decide the pipeline.

It only displays the backend-provided processing route.

Example:

Scanned_Invoice.pdf

Vision / OCR pipeline Page 3 / 5

DETECTED ✓ ROUTED ✓ OCR ● INDEXING ○ READY ○

------------------------------------------------------------------------

9.  UPLOAD CONTRACT

Request

POST /documents/upload Content-Type: multipart/form-data Authorization:
Bearer `<token>`{=html}

Fields:

file workspace_id collection_id?

------------------------------------------------------------------------

Response

{ "document": { "id": "doc_123", "name": "Policy.pdf", "status":
"queued" } }

The frontend should immediately navigate/update into the processing
state.

Do not block the interface waiting for the entire document pipeline.

------------------------------------------------------------------------

10. PROCESSING STATUS

Endpoint

GET /documents/{document_id}/status

Response:

{ "document_id": "doc_123", "status": "processing", "stage": "ocr",
"progress": 62, "message": "Extracting content from page 31 of 50" }

Frontend behavior:

-   update progress
-   animate stage transition
-   preserve previous completed stages
-   show current stage
-   show backend error if failed

Do not use an infinite generic spinner.

------------------------------------------------------------------------

11. PROCESSING FAILURE

Response example:

{ "status": "failed", "stage": "ocr", "error": { "code": "OCR_FAILED",
"message": "Unable to process the document." } }

UI:

PROCESSING FAILED

Unable to process this document.

\[ Retry \]

Do not expose internal stack traces.

------------------------------------------------------------------------

12. KNOWLEDGE BASE API

List documents

GET /documents?workspace_id=`<id>`{=html}

Optional filters:

status collection file_type search

Response:

{ "documents": \[\], "total": 24 }

------------------------------------------------------------------------

13. SEARCH MODEL

Search is the core interaction.

The frontend sends the user's natural-language question.

The backend handles:

Question ↓ Permission filtering ↓ Semantic retrieval ↓ Context assembly
↓ Multi-source reasoning ↓ Answer generation ↓ Evidence attribution

The frontend does not implement retrieval logic.

------------------------------------------------------------------------

14. SEARCH REQUEST

POST /search Authorization: Bearer `<token>`{=html} Content-Type:
application/json

Request:

{ "workspace_id": "workspace_123", "conversation_id": "conv_456",
"query": "What is the reimbursement limit?" }

Optional:

{ "document_ids": \[\], "collection_ids": \[\] }

If filters are supplied, the backend must still enforce user
permissions.

------------------------------------------------------------------------

15. SEARCH RESPONSE

The frontend expects:

{ "status": "answered", "conversation_id": "conv_456",

"answer": { "text": "The reimbursement limit is ₹50,000.",
"source_count": 3 },

"sources": \[ { "document_id": "doc_1", "document_name":
"Employee_Policy.pdf", "page": 12, "used": true } \],

"evidence": \[ { "id": "evidence_1", "document_id": "doc_1",
"document_name": "Employee_Policy.pdf", "page": 12, "section":
"Reimbursement", "text": "Employees may claim reimbursement..." } \] }

------------------------------------------------------------------------

16. SEARCH STATUS TYPES

The frontend must support these backend outcomes.

type SearchStatus = \| "answered" \| "insufficient_evidence" \|
"conflict" \| "no_results" \| "error"

Do not infer status from answer text.

Use the explicit backend status.

------------------------------------------------------------------------

17. ANSWERED STATE

Render:

ANSWER

The reimbursement limit is ₹50,000.

Based on 3 sources.

\[Policy p.12\] \[Finance p.7\] \[Invoice p.1\]

Citation chips must be interactive.

Clicking a citation opens the Evidence Inspector.

------------------------------------------------------------------------

18. EVIDENCE MODEL

Evidence is first-class data.

type Evidence = { id: string

documentId: string documentName: string

page?: number section?: string

text: string

relevance?: number }

The frontend must never manufacture:

-   page numbers
-   source names
-   supporting text
-   citations

Every displayed citation must originate from backend data.

------------------------------------------------------------------------

19. CLAIM → EVIDENCE RELATIONSHIP

Where supported by the backend, answers may contain claim-level
evidence.

Preferred response shape:

{ "claims": \[ { "text": "The reimbursement limit is ₹50,000.",
"evidence_ids": \["evidence_1"\] } \] }

This allows the UI to establish:

ANSWER CLAIM ↓ PROOF ↓ DOCUMENT ↓ PAGE ↓ SUPPORTING TEXT

If claim-level evidence is not available, fall back to answer-level
citations.

Do not invent claim relationships.

------------------------------------------------------------------------

20. EVIDENCE VIEWER

Endpoint

GET /documents/{document_id}/evidence

Optional query:

page evidence_id

Response should contain enough information to render:

document metadata page number page image/PDF preview URL highlight
coordinates or text supporting text

If exact highlight coordinates are unavailable, highlight the returned
supporting text in the evidence panel instead.

Do not implement a full PDF editor.

------------------------------------------------------------------------

21. DOCUMENT PREVIEW

Preferred backend response:

{ "document_id": "doc_123", "page": 12, "preview_url": "...",
"expires_at": "..." }

The frontend should treat preview URLs as temporary.

Never permanently store signed/private URLs in frontend state beyond the
active session where unnecessary.

------------------------------------------------------------------------

22. CONVERSATIONS

Follow-up questions must maintain context.

Create conversation

The first search can create a conversation.

Backend returns:

{ "conversation_id": "conv_123" }

Subsequent requests:

POST /conversations/{conversation_id}/messages

Request:

{ "query": "What about international travel?" }

The backend owns conversation memory.

The frontend only renders the conversation thread.

------------------------------------------------------------------------

23. CONVERSATION UI

Example:

YOU

What is the reimbursement limit?

NEX

The reimbursement limit is ₹50,000.

Based on 3 sources.

\[Policy p.12\] \[Finance p.7\]

YOU

What about international travel?

NEX

For international travel, the applicable limit is...

Do not reset context after each question.

------------------------------------------------------------------------

24. STREAMING

If the backend supports streaming:

POST /search

may return a streamed response.

The frontend should support:

answer token stream ↓ final structured answer ↓ sources ↓ evidence

Important:

Do not reveal citations before the backend has supplied them.

The answer may visually reveal progressively, but evidence must come
from the final structured response.

If streaming is not implemented, use a fast staged loading state
instead.

------------------------------------------------------------------------

25. LOADING EXPERIENCE

Use intentional stages:

UNDERSTANDING QUERY ↓ SEARCHING SOURCES ↓ COMBINING EVIDENCE ↓ FORMING
ANSWER ↓ VERIFYING SOURCES

These are UI states.

Do not claim a backend operation occurred unless the backend actually
provides that state.

If backend status is unavailable, use neutral wording:

Searching your sources...

rather than fake technical claims.

------------------------------------------------------------------------

26. INSUFFICIENT EVIDENCE

Backend:

{ "status": "insufficient_evidence", "answer": null, "evidence": \[\] }

Frontend:

NOT ENOUGH EVIDENCE

NEX couldn't find supporting information in the documents available to
you.

No unsupported answer was generated.

0 verified sources

Primary action:

\[ Ask another question \]

Do not display a fabricated answer.

------------------------------------------------------------------------

27. CONFLICTING SOURCES

Backend:

{ "status": "conflict", "sources": \[ { "document_name":
"Policy_2025.pdf", "page": 12, "claim": "₹50,000" }, { "document_name":
"Policy_2026.pdf", "page": 4, "claim": "₹40,000" } \] }

Frontend:

SOURCES DISAGREE

Policy 2025 ₹50,000

Policy 2026 ₹40,000

Review the cited documents to determine which policy is current.

Never visually imply that one source is correct unless the backend
explicitly establishes this.

------------------------------------------------------------------------

28. NO RESULTS

Backend:

{ "status": "no_results" }

Frontend:

NO RELEVANT EVIDENCE FOUND

NEX couldn't find relevant information in your accessible sources.

\[ Ask a different question \]

------------------------------------------------------------------------

29. ACCESS RESTRICTED

If the backend indicates that relevant information exists but the user
lacks access:

ACCESS RESTRICTED

Relevant information may exist in a source you do not have permission to
access.

Ask a workspace administrator for access.

Do not reveal:

-   document name
-   page
-   content
-   metadata

unless the backend explicitly authorizes disclosure.

------------------------------------------------------------------------

30. DOCUMENT ACCESS STATES

Document cards may show:

READY PROCESSING FAILED RESTRICTED ARCHIVED

Only show actions allowed by the backend.

Example:

Viewer:

Open Search

Contributor:

Open Search Retry Archive

Admin:

Open Search Retry Archive Manage Access

------------------------------------------------------------------------

31. HOME / KNOWLEDGE BASE DATA

The existing visual layout remains unchanged.

The frontend should populate:

Total documents Total pages Indexed chunks Processing jobs

These must come from backend data.

Do not create fake metrics in production/demo mode unless clearly
configured as mock data.

------------------------------------------------------------------------

32. KNOWLEDGE BASE RESPONSE

Preferred:

GET /workspace/{workspace_id}/overview

Response:

{ "metrics": { "documents": 24, "pages": 1284, "indexed_chunks": 8492,
"processing_jobs": 2 },

"documents": \[\] }

This lets the frontend load the home screen with one primary request.

------------------------------------------------------------------------

33. MOCK DATA STRATEGY

Mocks are allowed during frontend development.

Create one typed mock service matching the exact production schemas.

Example:

src/ services/ api/ documents.ts search.ts conversations.ts evidence.ts

    mock/
      documents.mock.ts
      search.mock.ts

The UI components must not know whether data is mocked or real.

Bad:

if (MOCK) { renderFakeAnswer() }

Good:

const result = await searchService.search(query)

Then the service implementation can switch between mock and real API.

------------------------------------------------------------------------

34. FRONTEND ARCHITECTURE

Recommended structure:

src/ ├── app/ │ ├── home/ │ ├── upload/ │ ├── search/ │ └── evidence/ │
├── components/ │ ├── AppShell │ ├── HeroIntro │ ├── DocumentDropzone │
├── DocumentCard │ ├── ProcessingPipeline │ ├── SourceRail │ ├──
AskNEXInput │ ├── ConversationThread │ ├── AnswerBlock │ ├──
CitationChip │ ├── EvidenceInspector │ ├── DocumentViewer │ ├──
StatusBanner │ └── EmptyState │ ├── services/ │ ├── api/ │ └── mock/ │
├── types/ │ ├── hooks/ │ └── lib/

Do not create an enormous architecture for the hackathon.

------------------------------------------------------------------------

35. STATE MANAGEMENT

Use local/component state where possible.

Global state should be limited to:

current workspace current user current conversation selected document
selected evidence upload/processing state where shared

Do not put every component's state into a global store.

------------------------------------------------------------------------

36. ERROR HANDLING

All API calls must handle:

401 Unauthorized 403 Forbidden 404 Not Found 409 Conflict 422 Validation
Error 429 Rate Limited 500 Server Error Network Error

Frontend messages should be human-readable.

Never show:

AxiosError: Request failed with status code 500

Instead:

Something went wrong while processing this request.

\[ Try again \]

------------------------------------------------------------------------

37. AUTHENTICATION BOUNDARY

Authentication is now part of the product architecture because NEXUS
supports private personal and organization workspaces.

However:

Do not build a complicated authentication UI.

The frontend should support:

current user current workspace role authorization state

The actual authentication provider is backend/infrastructure-owned.

Use the existing auth mechanism supplied by the backend.

Do not invent an OAuth flow if the backend contract has not specified
one.

------------------------------------------------------------------------

38. ROUTING

Suggested routes:

/ Home / Knowledge Base

/upload Upload + Processing

/search AI Search Workspace

/evidence/:documentId Evidence Viewer

Optional workspace prefix:

/w/:workspaceId /w/:workspaceId/upload /w/:workspaceId/search

Do not create separate product surfaces for personal and organization
mode.

They share the same interface.

The workspace context determines behavior.

------------------------------------------------------------------------

39. DESIGN PRESERVATION

The following existing sections remain unchanged:

-   Awwwards visual direction
-   typography
-   color system
-   motion system
-   Home visual composition
-   Upload screen
-   three-column Search Workspace
-   Evidence Inspector
-   Evidence Viewer
-   micro-interactions
-   responsive behavior

Technical refinement must NOT flatten the design into a conventional
SaaS dashboard.

------------------------------------------------------------------------

40. TECHNICAL FRONTEND RULES

Rule 1

Never fabricate backend data.

Rule 2

Never fabricate citations.

Rule 3

Never fabricate processing completion.

Rule 4

Never expose unauthorized document information.

Rule 5

Never hard-code document IDs in production components.

Rule 6

Never couple UI components directly to fetch logic.

Rule 7

All API response types must be explicitly typed.

Rule 8

Backend status controls important state.

Rule 9

Use graceful fallbacks when optional backend fields are absent.

Rule 10

The interface must remain functional with slow APIs.

------------------------------------------------------------------------

41. OPTIONAL BACKEND FEATURES

The frontend may support these if the backend exposes them.

Search streaming

answer_delta sources evidence complete

Processing events

stage_changed progress completed failed

Claim-level evidence

claim → evidence_ids\[\]

Document page coordinates

x y width height

These are enhancements.

The frontend must still work without them.

------------------------------------------------------------------------

42. DEMO DATA CONTRACT

Prepare 3--4 documents representing:

1.  Normal text PDF
2.  Scanned/noisy PDF
3.  Image/table document
4.  A second document containing related or conflicting information

The exact content should be prepared by the backend/demo team.

The frontend should not embed the document content.

------------------------------------------------------------------------

43. REQUIRED DEMO FLOW

The final frontend must support:

HOME ↓ UPLOAD 3--4 DOCUMENTS ↓ PROCESSING ↓ READY ↓ SEARCH ↓
MULTI-SOURCE ANSWER ↓ CLICK CITATION ↓ EVIDENCE INSPECTOR ↓ OPEN
DOCUMENT PAGE ↓ FOLLOW-UP QUESTION ↓ INSUFFICIENT EVIDENCE ↓ CONFLICTING
SOURCES

This is the primary acceptance test.

------------------------------------------------------------------------

44. 8-HOUR PRIORITY

P0 --- Must work

-   document upload UI
-   processing states
-   knowledge base
-   search
-   conversation
-   multi-source answer
-   citations
-   evidence inspector
-   document viewer
-   insufficient evidence
-   conflicting sources

P1 --- Important

-   workspace context
-   role-aware UI
-   document permissions
-   retry processing
-   responsive layout
-   polished loading/error states

P2 --- Only if time remains

-   streaming responses
-   claim-level evidence highlighting
-   advanced collection filtering
-   richer document preview
-   advanced permission management UI

Never sacrifice P0 for P2.

------------------------------------------------------------------------

45. DEFINITION OF DONE

Product

-   [ ] Personal workspace supported
-   [ ] Organization workspace supported
-   [ ] Viewer / Contributor / Admin role model represented
-   [ ] Document-level access respected
-   [ ] Backend is the source of truth for permissions

Documents

-   [ ] Upload works
-   [ ] Processing states work
-   [ ] Failure state works
-   [ ] Document list is backend-driven
-   [ ] Document status is backend-driven

AI

-   [ ] Search request works
-   [ ] Multi-source answers render
-   [ ] Follow-up questions preserve conversation
-   [ ] Sources render
-   [ ] Evidence renders
-   [ ] No-result state works
-   [ ] Insufficient-evidence state works
-   [ ] Conflict state works

Evidence

-   [ ] Citation chips are interactive
-   [ ] Evidence inspector works
-   [ ] Document/page opens from citation
-   [ ] Supporting text is displayed
-   [ ] No citations are fabricated

Visual

-   [ ] Existing Awwwards direction preserved
-   [ ] Three-column workspace preserved
-   [ ] Motion preserved
-   [ ] Responsive behavior works
-   [ ] Loading states are intentional
-   [ ] No generic dashboard styling introduced

------------------------------------------------------------------------

46. FINAL ENGINEERING PRINCIPLE

NEXUS is not:

«"A pretty chatbot."»

It is:

«A permission-aware evidence retrieval interface.»

The visual experience should make this pipeline obvious:

DOCUMENTS ↓ UNDERSTAND ↓ INDEX ↓ RETRIEVE ↓ COMBINE ↓ ANSWER ↓ PROVE

Every major animation, component, and interaction should reinforce that
pipeline.

Make fewer things.

Make them technically real.

## Make every visible interaction traceable to backend state.

# FINAL CREATIVE + AGENT EXECUTION CONTRACT

> **Status:** Final frontend PRD extension\
> **Purpose:** Convert the approved NEXUS visual direction into an
> implementation-grade creative system that coding agents can execute
> without inventing product behavior, flattening the visual identity, or
> introducing unverified assets/dependencies.
>
> **Authority:** Sections 0--46 remain the product, backend, data,
> reliability, and frontend engineering contract. Sections 47 onward
> make the previously approved visual/art direction executable. Where a
> generic framework convention conflicts with this document, this
> document wins unless the backend/API contract requires otherwise.

------------------------------------------------------------------------

## 47. CREATIVE NORTH STAR

NEXUS must feel like an **evidence intelligence instrument**, not a
conventional SaaS dashboard and not a chatbot wrapped in cards.

The experience should communicate:

**DOCUMENTS → UNDERSTAND → INDEX → RETRIEVE → COMBINE → ANSWER → PROVE**

The interface is the visual language of that pipeline.

### 47.1 Emotional target

The first impression should create:

-   curiosity
-   authority
-   precision
-   visual confidence
-   a desire to explore the workspace
-   a sense that the system is doing serious investigative work

The product should feel:

-   cinematic
-   editorial
-   intelligent
-   spatial
-   tactile
-   precise
-   premium
-   technically credible

It must not feel:

-   playful SaaS
-   generic AI wrapper
-   template dashboard
-   cryptocurrency interface
-   gaming HUD
-   cyberpunk terminal
-   marketing-only concept with fake functionality

### 47.2 Design variance

Use high visual agency without sacrificing information hierarchy.

Target baseline:

-   DESIGN_VARIANCE: 8/10
-   MOTION_INTENSITY: 6/10
-   VISUAL_DENSITY: 4/10

These are design targets, not reasons to add decoration.

Every unusual composition must improve:

-   hierarchy
-   orientation
-   storytelling
-   interaction
-   evidence comprehension

If an effect does not improve one of those dimensions, remove it.

### 47.3 One-workspace principle

NEXUS should feel like one continuous environment.

Avoid the feeling of:

Home → random dashboard → random chatbot → random PDF viewer.

Instead:

Knowledge Base → Search → Answer → Evidence → Document Page

must feel like different states of the same workspace.

Persistent visual anchors may include:

-   NEXUS wordmark
-   workspace context
-   source rail
-   evidence relationship
-   current document
-   current conversation

------------------------------------------------------------------------

## 48. VISUAL GRAMMAR

The interface must assign visual meaning to product concepts.

  Product concept         Visual grammar
  ----------------------- -----------------------------
  Document                object / artifact
  Collection              spatial grouping
  Processing              transformation
  OCR                     extraction / reconstruction
  Indexing                ordered connection
  Search                  investigation
  Retrieval               source selection
  Answer                  synthesis
  Citation                relationship
  Evidence                proof
  Conflict                tension
  Insufficient evidence   restraint
  Permission              controlled boundary
  Error                   interruption
  Ready                   stable state

Do not introduce visual metaphors unrelated to this grammar.

### 48.1 Documents are objects

Documents should feel like meaningful artifacts rather than generic
rectangular cards.

Possible treatments:

-   editorial document previews
-   page thumbnails
-   cropped content fragments
-   typographic document identities
-   subtle depth
-   document metadata integrated into composition

Avoid:

-   identical generic cards for every file
-   excessive icon containers
-   giant folder illustrations

### 48.2 Processing is transformation

Processing should visually communicate movement from uncertainty to
understanding.

Preferred conceptual sequence:

RAW → DETECTED → ROUTED → EXTRACTED / OCR → STRUCTURED → INDEXED → READY

The UI may use:

-   progressive line construction
-   document reconstruction
-   page extraction
-   source nodes becoming connected
-   restrained particle/point movement
-   text becoming structured

Do not fake backend progress.

The animation represents the real state supplied by the backend.

### 48.3 Evidence is a relationship

A citation must not behave like a decorative badge.

The visual relationship should be:

**CLAIM → SOURCE → PAGE → SUPPORTING TEXT**

When a user activates a citation:

1.  identify the claim
2.  visually establish the source relationship
3.  open the evidence inspector
4.  reveal page/context
5.  reveal supporting text
6.  allow opening the document page

------------------------------------------------------------------------

## 49. ANTI-AI-SLOP CONTRACT

The following patterns are prohibited unless explicitly justified by a
product requirement.

### 49.1 Banned visual patterns

Do not use:

-   generic SaaS dashboard layouts
-   purple AI gradients as the primary identity
-   rainbow gradients
-   excessive glassmorphism
-   giant floating rounded rectangles
-   excessive `rounded-2xl` / `rounded-3xl` containers
-   card grids for every piece of information
-   decorative metric cards with meaningless numbers
-   generic robot illustrations
-   chatbot speech bubbles as the primary product architecture
-   excessive pills and badges
-   floating blobs with no semantic purpose
-   animated background noise that competes with evidence
-   random particles
-   fake terminal UI
-   crypto/cyberpunk aesthetics
-   generic neon glow
-   default shadcn appearance
-   default component-library spacing
-   excessive drop shadows
-   nested cards inside cards inside cards
-   unnecessary left navigation
-   meaningless dashboard charts
-   fake activity feeds
-   fake AI confidence percentages
-   fake citation counts
-   fake processing metrics
-   fake document content
-   invented source metadata
-   invented page numbers
-   decorative "AI MAGIC" copy

### 49.2 Banned copy patterns

Avoid empty marketing language such as:

-   "Unlock the power of AI"
-   "The future of knowledge"
-   "AI-powered insights"
-   "Revolutionize your workflow"
-   "Supercharge your productivity"

Product copy must describe actual behavior.

Prefer:

-   "Ask across your sources."
-   "See the evidence behind the answer."
-   "No supporting evidence found."
-   "These sources disagree."
-   "Open page 12."

### 49.3 Banned interaction patterns

Do not add:

-   hover effects to every element
-   infinite parallax
-   scroll hijacking
-   unnecessary cursor replacement
-   animations that delay task completion
-   navigation transitions that obscure context
-   decorative loaders that communicate nothing
-   fake progress percentages
-   interaction that only exists for a screenshot

------------------------------------------------------------------------

## 50. LAYOUT SYSTEM

### 50.1 Global canvas

Use a restrained dark canvas.

The page should have:

-   strong negative space
-   controlled horizontal rhythm
-   editorial asymmetry
-   clear information anchors
-   high-quality typography

The canvas must never become visually noisy.

### 50.2 Desktop workspace

The primary Search Workspace uses three conceptual regions:

**SOURCE RAIL \| ANSWER CANVAS \| EVIDENCE INSPECTOR**

The proportions are fluid.

Recommended conceptual range:

-   Source Rail: 18--24%
-   Answer Canvas: 46--58%
-   Evidence Inspector: 22--30%

These are design targets, not hardcoded widths.

The center answer canvas must remain the visual focus.

### 50.3 Grid

Prefer CSS Grid for major layouts.

Do not solve complex layouts with arbitrary percentage-based flex
calculations.

Use:

-   responsive grid columns
-   `minmax`
-   controlled gaps
-   max-width containers
-   content-aware sizing

### 50.4 Container behavior

Marketing/home surfaces may use wide editorial containers.

Workspace surfaces should use the available viewport intelligently.

Do not force every surface into the same max-width.

### 50.5 Mobile

Mobile is not a scaled desktop.

Transform the workspace:

Desktop:

SOURCE RAIL \| ANSWER \| EVIDENCE

Mobile:

ANSWER ↓ SOURCES ↓ EVIDENCE

The source rail becomes a compact source control.

The evidence inspector becomes:

-   bottom sheet
-   full-screen panel
-   route/state transition

Choose one consistent mobile pattern.

Do not create a miniature three-column layout.

------------------------------------------------------------------------

## 51. TYPOGRAPHY SYSTEM

Typography is a primary visual asset.

### 51.1 Hierarchy

Use a strong display face for major editorial moments and a highly
readable UI face for application content.

Do not use Inter as an automatic default merely because it is familiar.

Potential implementation families may include:

-   Geist
-   Satoshi
-   Cabinet Grotesk
-   Outfit

The actual font must be selected based on availability and dependency
verification.

Never invent a font import path.

### 51.2 Display typography

Display type should be:

-   large
-   wide
-   confident
-   tightly controlled

Hero headlines should generally remain within 2--3 lines.

Do not create narrow containers that force:

"AI\
Evidence\
Intelligence\
Workspace"

when a stronger horizontal composition is possible.

### 51.3 UI typography

Use:

-   high legibility
-   restrained weight changes
-   consistent line-height
-   clear numeric treatment
-   controlled uppercase usage

Avoid all-caps everywhere.

### 51.4 Metadata

Metadata should be quiet but readable.

Examples:

DOCUMENT PDF 12 PAGES READY

Metadata must support orientation rather than become decoration.

------------------------------------------------------------------------

## 52. COLOR SYSTEM

The color system must remain restrained.

### 52.1 Base

Use a near-black / charcoal base rather than pure black everywhere.

Recommended conceptual layers:

-   canvas
-   elevated surface
-   raised surface
-   active surface
-   border
-   primary text
-   secondary text
-   muted text

Do not create dozens of visually indistinguishable dark tokens.

### 52.2 Accent

Primary accent:

**electric blue-violet**

Use it selectively for:

-   active state
-   focus
-   evidence relationship
-   important action
-   progress
-   selected source

Do not flood the UI with accent color.

### 52.3 Semantic states

Success, warning, conflict, error, and restricted states must be
distinguishable without depending only on hue.

Use:

-   iconography
-   typography
-   borders
-   layout
-   labels

Do not use fabricated "confidence" colors.

------------------------------------------------------------------------

## 53. SURFACE AND DEPTH LANGUAGE

NEXUS should use depth carefully.

### 53.1 Preferred

-   thin borders
-   subtle tonal shifts
-   controlled blur
-   soft shadows
-   occasional translucent layers
-   document imagery
-   spatial separation

### 53.2 Avoid

-   heavy glass everywhere
-   huge shadows
-   glowing cards
-   excessive blur
-   nested transparent panels
-   fake 3D bevels

### 53.3 Surface hierarchy

A user should be able to tell:

1.  background
2.  workspace
3.  active panel
4.  focused evidence
5.  interactive control

without requiring thick borders around everything.

------------------------------------------------------------------------

## 54. NAVIGATION

Navigation must remain lightweight.

Do not add a conventional enterprise sidebar unless the product actually
needs it.

The navigation should communicate:

-   NEXUS
-   current workspace
-   current mode
-   knowledge/search context
-   user/session controls

The workspace should remain the dominant surface.

------------------------------------------------------------------------

## 55. HOME / KNOWLEDGE BASE CREATIVE DIRECTION

The Home surface should feel like entering an evidence workspace.

It must not look like:

"24 Documents / 1,284 Pages / 8,492 Chunks"

as four generic statistic cards.

### 55.1 Hero

The opening composition may use:

-   large editorial typography
-   document fragments
-   a spatial source field
-   restrained motion
-   a strong visual representation of documents becoming knowledge

Primary message:

**Ask NEX. Get the answer. See the proof.**

### 55.2 Document field

The document collection may be presented as a spatial editorial
composition.

Possible structure:

-   featured document
-   surrounding source artifacts
-   collection grouping
-   processing state
-   recent activity

Every visible document must be real data or clearly marked demo data.

### 55.3 Metrics

Metrics are secondary.

They should be integrated into the composition rather than automatically
becoming four cards.

------------------------------------------------------------------------

## 56. UPLOAD EXPERIENCE

Upload should feel like the first transformation event.

### 56.1 Dropzone

The dropzone should communicate:

**Bring evidence into NEXUS.**

It should support:

-   drag and drop
-   file picker
-   supported file types
-   selected files
-   upload progress
-   cancellation where supported

### 56.2 Selected documents

Once selected, documents become artifacts in the processing environment.

Each item may expose:

-   filename
-   type
-   size
-   upload progress
-   processing state

### 56.3 No fake readiness

Never show:

READY

until the backend says the document is ready.

------------------------------------------------------------------------

## 57. PROCESSING EXPERIENCE

This is one of NEXUS's signature visual moments.

### 57.1 Pipeline

Show the actual backend lifecycle:

UPLOAD → QUEUED → DETECTING → ROUTING → EXTRACTING / OCR → STRUCTURING →
INDEXING → READY

Completed stages become stable.

The active stage moves.

Future stages remain quiet.

### 57.2 Stage transition

Use motion to communicate transformation.

Example:

A document thumbnail enters the processing field.

Its pages may subtly separate.

Extracted content appears.

Structure lines form.

The source becomes indexed.

The document settles into the knowledge base.

The visual is allowed to be cinematic, but the state must remain
truthful.

### 57.3 Failure

Failure should interrupt the transformation clearly.

Do not leave a beautiful animation running after backend failure.

Show:

PROCESSING FAILED

Then the actionable recovery.

------------------------------------------------------------------------

## 58. SEARCH WORKSPACE

This is the core product surface.

### 58.1 Source rail

The source rail answers:

**What evidence is involved?**

It may show:

-   selected documents
-   collections
-   source count
-   document status
-   source relevance when supplied by backend

Do not show fabricated relevance percentages.

### 58.2 Answer canvas

The answer canvas answers:

**What does NEX know from the available evidence?**

It should prioritize:

1.  answer
2.  claims
3.  citations
4.  context
5.  follow-up

### 58.3 Evidence inspector

The evidence inspector answers:

**Why should I trust this claim?**

It should expose:

-   document
-   page
-   section
-   supporting text
-   page preview
-   open-document action

### 58.4 Relationship line

When practical, use subtle motion or spatial alignment to establish:

CLAIM ↓ CITATION ↓ EVIDENCE ↓ PAGE

This is a signature NEXUS interaction.

------------------------------------------------------------------------

## 59. ASK NEX INPUT

The query input is the primary action.

It must not look like a generic chat composer.

It should communicate:

**Search your evidence.**

### 59.1 States

Support:

-   idle
-   focused
-   typing
-   submitting
-   searching
-   answer-ready
-   disabled
-   error

### 59.2 Focus

Focus should create a subtle spatial change.

Do not use a giant neon glow.

### 59.3 Submission

On submit:

-   preserve the question
-   transition into answer state
-   maintain source context
-   show truthful loading state

------------------------------------------------------------------------

## 60. ANSWER COMPOSITION

Answers should feel like evidence-backed synthesis.

### 60.1 Hierarchy

Recommended structure:

NEX

Primary answer

Supporting explanation

Evidence relationships

Source summary

Follow-up

### 60.2 Claim-level evidence

If backend provides:

claim → evidence_ids\[\]

the UI should make the relationship visible.

If not provided:

use answer-level citations.

Never infer the mapping.

### 60.3 Citation interaction

Citation activation should feel like a connection being revealed, not a
modal being randomly opened.

Suggested sequence:

1.  citation becomes active
2.  source rail highlights source
3.  evidence inspector opens
4.  document page is selected
5.  supporting text becomes visually prominent

------------------------------------------------------------------------

## 61. EVIDENCE INSPECTOR

The Evidence Inspector is a signature NEXUS surface.

### 61.1 Anatomy

Recommended order:

-   source identity
-   document name
-   page
-   section
-   supporting text
-   page preview
-   open document

### 61.2 Evidence emphasis

Supporting text should be the strongest content in the inspector.

The page image is contextual proof.

### 61.3 No evidence

If no evidence exists:

Do not render an empty fake inspector.

Use a restrained state explaining that no verified evidence is
available.

------------------------------------------------------------------------

## 62. DOCUMENT VIEWER

The viewer exists to verify evidence.

It is not a document-management suite.

### 62.1 Primary task

User should be able to:

-   see the cited page
-   understand context
-   identify supporting text
-   navigate where supported
-   return to the answer

### 62.2 Highlight

If backend provides coordinates:

use them.

If backend provides text only:

show supporting text in the inspector.

Do not fabricate coordinates.

### 62.3 Signed URLs

Treat signed URLs as temporary.

Do not assume permanence.

------------------------------------------------------------------------

## 63. RELIABILITY STATES AS FIRST-CLASS EXPERIENCES

Reliability is part of the visual identity.

### 63.1 Insufficient evidence

The visual should communicate restraint.

Avoid a sad illustration.

Use typography, space, and evidence count.

Core message:

**NEX could not verify an answer from the sources available.**

### 63.2 Conflict

Conflict should create visual tension.

Recommended:

Source A ₹50,000

versus

Source B ₹40,000

with:

-   document names
-   pages
-   dates when supplied
-   claims

Never declare a winner without backend support.

### 63.3 No results

Keep it quiet and useful.

Offer a better question path.

### 63.4 Access restricted

Reveal only what backend authorizes.

Do not visually tease private metadata.

------------------------------------------------------------------------

## 64. MOTION SYSTEM

Motion must communicate meaning.

### 64.1 Motion principles

Use:

-   continuity
-   physicality
-   hierarchy
-   anticipation
-   restraint
-   progressive disclosure

Avoid:

-   random spring animations
-   constant floating
-   excessive scale changes
-   decorative motion on every component

### 64.2 Motion intensity

Target:

6/10

The experience should feel alive but usable.

### 64.3 Timing

Use shorter transitions for local controls.

Use longer transitions for:

-   workspace state changes
-   document transformation
-   evidence opening
-   major navigation transitions

### 64.4 Easing

Prefer purposeful easing.

Do not use one easing curve for every interaction.

### 64.5 Reduced motion

When reduced motion is requested:

-   remove nonessential movement
-   disable scroll-driven choreography
-   replace spatial transitions with fades/instant state changes
-   preserve all information and interaction

------------------------------------------------------------------------

## 65. SCROLL EXPERIENCE

Scroll should reveal product meaning.

Do not use scroll effects merely because they are technically possible.

### 65.1 Suitable uses

-   document transformation story
-   source-to-answer narrative
-   processing pipeline
-   evidence relationship
-   landing/home storytelling

### 65.2 Prohibited

-   scroll hijacking
-   mandatory long scroll before task access
-   pinned content that blocks mobile usability
-   animations that make text unreadable
-   scroll effects that prevent keyboard access

### 65.3 Workspace scrolling

The application workspace must prioritize task efficiency over cinematic
scrolling.

The immersive treatment belongs primarily to:

-   home
-   onboarding
-   processing
-   transition moments

The search task itself must remain fast.

------------------------------------------------------------------------

## 66. 3D / IMMERSIVE LAB CONTRACT

3D is an enhancement, not the source of truth.

### 66.1 Isolation

All experimental 3D work must begin in:

`/lab/immersive`

Do not introduce WebGL directly into the production workspace without
passing the immersive gates.

### 66.2 Approved asset sources

A 3D asset may come only from:

1.  an existing repository asset
2.  an explicitly generated local asset
3.  procedurally generated geometry
4.  an explicitly approved external dependency

Never invent:

-   `.glb` paths
-   `.gltf` paths
-   HDRI URLs
-   texture URLs
-   shader include paths
-   CDN assets
-   model filenames

### 66.3 IMMERSIVE_SCENE_CONTRACT

Before implementation, create:

`IMMERSIVE_SCENE_CONTRACT.md`

It must define:

-   scene purpose
-   product concept represented
-   camera behavior
-   geometry
-   materials
-   lighting
-   animation
-   interaction
-   scroll relationship
-   assets
-   fallback
-   performance budget
-   reduced-motion behavior
-   mobile behavior

### 66.4 Product meaning

Every 3D effect must map to the NEXUS grammar.

Examples:

Documents → spatial artifacts

Processing → transformation

Search → investigation

Evidence → connection

Conflict → opposing structures

Insufficient evidence → empty/restraint

### 66.5 Three.js gates

Implement sequentially:

1.  foundation
2.  geometry
3.  materials
4.  lighting
5.  animation
6.  interaction
7.  scroll
8.  post-processing
9.  performance
10. production integration

Do not jump directly to post-processing.

### 66.6 WebGL fallback

If WebGL fails or is unavailable:

-   preserve the product
-   preserve the information hierarchy
-   preserve the interaction
-   replace the effect with deterministic DOM/CSS composition

3D must never be required to understand evidence.

------------------------------------------------------------------------

## 67. IMMERSIVE PERFORMANCE CONTRACT

3D and motion must respect the application nature of NEXUS.

### 67.1 Rules

Do not:

-   run unnecessary perpetual animations
-   render huge scenes
-   load large assets without justification
-   create excessive particle counts
-   block the main UI thread
-   make evidence interaction dependent on canvas rendering

### 67.2 CPU-heavy effects

Isolate CPU/GPU-heavy animation into dedicated components.

### 67.3 Cleanup

Every animation lifecycle must clean up:

-   animation frames
-   event listeners
-   observers
-   timers
-   WebGL resources where applicable

### 67.4 Performance acceptance

Test:

-   desktop
-   laptop
-   mobile
-   reduced motion
-   WebGL unavailable/failure

------------------------------------------------------------------------

## 68. COMPONENT STATES CONTRACT

Every interactive component must explicitly consider:

-   default
-   hover
-   focus
-   active
-   selected
-   disabled
-   loading
-   success
-   error
-   empty
-   restricted

Do not rely on browser defaults for primary product controls.

### 68.1 Buttons

Buttons must have:

-   visible label
-   clear affordance
-   keyboard focus
-   disabled state
-   loading state where asynchronous
-   adequate contrast

### 68.2 Cards

Cards should not exist merely to contain content.

Use a card only when:

-   grouping improves comprehension
-   the content needs a boundary
-   interaction requires a surface

Prefer spacing when a card adds no meaning.

### 68.3 Inputs

Inputs must communicate:

-   what can be entered
-   current state
-   validation
-   submission state

------------------------------------------------------------------------

## 69. ACCESSIBILITY CONTRACT

Accessibility is part of the visual quality bar.

Required:

-   semantic HTML
-   keyboard navigation
-   visible focus
-   accessible labels
-   sufficient contrast
-   logical heading hierarchy
-   reduced-motion support
-   no interaction that requires hover
-   usable mobile touch targets
-   meaningful alt text for meaningful imagery
-   decorative visuals hidden from assistive technology

Do not sacrifice accessibility for cinematic presentation.

------------------------------------------------------------------------

## 70. RESPONSIVE CONTRACT

Required test widths:

-   320px
-   375px
-   390px
-   430px
-   768px
-   1024px
-   1280px
-   1440px
-   1728px

### 70.1 Mobile priorities

At mobile:

1.  question
2.  answer
3.  citations
4.  evidence
5.  source browsing

Everything else becomes secondary.

### 70.2 Full-height sections

Never assume `100vh` is stable on mobile browsers.

Prefer dynamic viewport behavior such as:

`min-height: 100dvh`

when a full viewport section is actually required.

### 70.3 Overflow

Prevent unintended horizontal overflow.

Animations must not create persistent horizontal scrollbars.

------------------------------------------------------------------------

## 71. AGENT EXECUTION MODEL

NEXUS is intended to be built by AI coding agents.

The agents must operate in controlled phases.

### 71.1 Primary builder

**Gemini 3.1 Pro High**

Primary responsibilities:

-   repository reconnaissance
-   implementation
-   architecture integration
-   component construction
-   API integration
-   browser verification
-   iterative visual refinement

### 71.2 Adversarial reviewer

**Claude Sonnet 4.6 Thinking**

Primary responsibilities:

-   visual critique
-   product hierarchy review
-   motion review
-   accessibility review
-   responsive review
-   3D integrity review
-   API hallucination detection
-   regression detection
-   anti-generic review

Claude must critique before rebuilding.

Claude must not silently invent new product requirements.

### 71.3 Separation of responsibility

Gemini builds.

Claude challenges.

The PRD governs both.

Neither agent may redefine product behavior without an explicit change
to this PRD.

------------------------------------------------------------------------

## 72. AGENT MEMORY / BUILD ARTIFACTS

The repository must contain:

`BUILD_STATE.md`

Tracks:

-   current phase
-   completed work
-   verified work
-   known limitations
-   current blockers

`BUILD_BLOCKERS.md`

Tracks:

-   blocking issue
-   affected files
-   cause
-   required decision
-   status

`DESIGN_SYSTEM.md`

Tracks:

-   typography
-   color
-   spacing
-   surfaces
-   components
-   states

`VISUAL_RULES.md`

Tracks:

-   composition
-   anti-patterns
-   visual grammar
-   responsive behavior

`MOTION_RULES.md`

Tracks:

-   motion principles
-   durations
-   easing
-   reduced motion
-   scroll behavior

`IMMERSIVE_SCENE_CONTRACT.md`

Required only when 3D is being implemented.

`AGENT_CHANGELOG.md`

Tracks:

-   phase
-   change
-   reason
-   files
-   verification
-   rollback checkpoint

Agents must read the relevant artifact before changing the corresponding
system.

------------------------------------------------------------------------

## 73. ROLLING BUILD PHASES

The project is built incrementally.

### PHASE 00 --- RECON

Goal:

Understand the repository before touching it.

Inspect:

-   framework
-   package manager
-   package.json
-   existing routes
-   component structure
-   CSS/Tailwind configuration
-   installed icon library
-   motion dependencies
-   existing assets
-   environment variables
-   API layer
-   auth layer

Do not assume dependencies.

Deliver:

-   BUILD_STATE.md
-   initial AGENT_CHANGELOG.md
-   dependency map
-   route map
-   asset inventory

Gate:

No implementation before repository facts are known.

------------------------------------------------------------------------

### PHASE 01 --- STRUCTURAL SKELETON

Build:

-   application shell
-   routing
-   workspace structure
-   Home
-   Upload
-   Search
-   Evidence
-   responsive structural behavior

No elaborate motion.

No 3D.

No invented APIs.

Goal:

The product should be navigable and structurally correct.

Checkpoint:

`nexus/phase-01-structural-skeleton`

------------------------------------------------------------------------

### PHASE 02 --- VISUAL DNA

Implement:

-   typography
-   color
-   surfaces
-   spacing
-   borders
-   component states
-   editorial composition
-   NEXUS visual identity

Use:

`design-taste-frontend`

and, where appropriate:

`high-end-visual-design`

The AAS design-taste skill explicitly targets anti-generic frontend work
and recommends dependency verification and responsive/state validation;
these requirements are adopted here rather than treated as optional.

Checkpoint:

`nexus/phase-02-visual-dna`

------------------------------------------------------------------------

### PHASE 03 --- REAL PRODUCT VERTICAL SLICE

Build the narrowest complete working path:

UPLOAD → PROCESS → READY → ASK → ANSWER → CITATION → EVIDENCE

Connect it to the typed service layer.

Use real backend contracts where available.

Use exact-schema mocks where backend is unavailable.

No decorative feature expansion until this vertical slice works.

Checkpoint:

`nexus/phase-03-vertical-slice`

------------------------------------------------------------------------

### PHASE 04 --- IMMERSIVE LAB

Only if the visual direction benefits from 3D.

Create:

`/lab/immersive`

Create:

`IMMERSIVE_SCENE_CONTRACT.md`

Use:

`threejs-skills`

then only the specialized Three.js skills actually required.

Available AAS Three.js modules include fundamentals, geometry,
materials, lighting, textures, animation, loaders, shaders,
post-processing, and interaction.

Do not activate every Three.js skill automatically.

Checkpoint:

`nexus/phase-04-immersive-lab`

------------------------------------------------------------------------

### PHASE 05 --- CINEMATIC INTERACTION

Implement:

-   meaningful transitions
-   processing transformation
-   evidence reveal
-   scroll storytelling where appropriate
-   micro-interactions

Use:

`gpt-taste`

only for surfaces where cinematic/GSAP-style motion is appropriate.

The AAS `gpt-taste` skill is specifically aimed at cinematic,
motion-rich frontend work and warns that heavy scroll/pinning requires
browser and performance validation. citeturn0search2

Do not force landing-page animation patterns into the evidence
workspace.

Checkpoint:

`nexus/phase-05-cinematic`

------------------------------------------------------------------------

### PHASE 06 --- PRODUCT + IMMERSIVE INTEGRATION

Connect the successful immersive experiment to the real product.

Verify:

-   no fake data
-   no fake states
-   no invented assets
-   no interaction conflicts
-   no evidence obscured by motion
-   mobile fallback
-   reduced motion
-   performance

Checkpoint:

`nexus/phase-06-integration`

------------------------------------------------------------------------

### PHASE 07 --- ADVERSARIAL REVIEW

Claude Sonnet 4.6 Thinking reviews the current build.

Review categories:

-   product clarity
-   visual distinctiveness
-   hierarchy
-   typography
-   spacing
-   composition
-   interaction
-   motion
-   accessibility
-   responsive behavior
-   performance
-   3D integrity
-   dependency integrity
-   API hallucination
-   state correctness

Claude outputs:

BLOCKING HIGH MEDIUM LOW

For each issue:

-   evidence
-   affected file/component
-   why it matters
-   smallest acceptable fix
-   verification method

Claude must not silently rewrite the product.

Checkpoint:

`nexus/phase-07-adversarial-review`

------------------------------------------------------------------------

### PHASE 08 --- FINAL POLISH + DEMO HARDENING

Final pass:

-   remove visual noise
-   remove dead code
-   remove unused dependencies
-   verify loading states
-   verify error states
-   verify citations
-   verify evidence
-   verify conflict
-   verify insufficient evidence
-   verify access restriction
-   verify mobile
-   verify reduced motion
-   verify browser runtime
-   verify demo flow

Checkpoint:

`nexus/phase-08-final`

------------------------------------------------------------------------

## 74. PHASE GATE CONTRACT

No phase is complete because code "looks finished."

Every phase requires:

### SPEC GATE

The implementation follows the PRD.

### BUILD GATE

The repository builds successfully.

### RUNTIME GATE

The application starts without runtime errors.

### BROWSER GATE

The affected flow has been tested in a real browser.

### RESPONSIVE GATE

At least desktop and mobile have been checked.

### ACCESSIBILITY GATE

Keyboard, focus, semantics, contrast, and reduced motion are checked
where applicable.

### VISUAL GATE

The implementation preserves the NEXUS visual direction.

### DATA GATE

No backend data is fabricated.

### NO-HALLUCINATION GATE

No invented:

-   API
-   endpoint
-   dependency
-   asset
-   model
-   file
-   field
-   backend state

### REGRESSION GATE

Previously working P0 behavior remains working.

### 3D GATE

If 3D is present:

-   WebGL behavior verified
-   fallback verified
-   asset paths verified
-   cleanup verified
-   performance checked
-   mobile checked
-   reduced motion checked

------------------------------------------------------------------------

## 75. SKILL ACTIVATION CONTRACT

Do not dump every available skill into the agent context.

Skills are phase-scoped expertise modules.

### P0 visual skill

`design-taste-frontend`

Mandatory for primary frontend visual construction.

### P0 premium visual skill

`high-end-visual-design`

Use when implementing or auditing agency-grade visual polish.

### P0 motion skill

`gpt-taste`

Use during cinematic motion/scroll phases, not automatically for every
component.

### P0 3D orchestrator

`threejs-skills`

Mandatory only if the project actually implements Three.js/WebGL.

### 3D specialists

Activate only when required:

-   `threejs-fundamentals`
-   `threejs-geometry`
-   `threejs-materials`
-   `threejs-lighting`
-   `threejs-textures`
-   `threejs-animation`
-   `threejs-loaders`
-   `threejs-shaders`
-   `threejs-postprocessing`
-   `threejs-interaction`

### Review skills

Use:

-   `fixing-motion-performance`
-   `fixing-accessibility`
-   `baseline-ui`

at the appropriate validation stages.

### Optional redesign review

`redesign-existing-projects`

May be used for a targeted redesign critique of an existing surface.

Do not allow a redesign skill to override the NEXUS PRD.

### API contract skill

`api-and-interface-design`

Use when designing or changing API/interface contracts between frontend
and backend.

The current AAS catalog describes it as appropriate for REST/GraphQL
endpoints, module boundaries, and component interfaces.
citeturn0search4

### Architecture skill

`codebase-design`

Use when restructuring modules or designing clean seams.

Do not introduce architecture for architecture's sake.

------------------------------------------------------------------------

## 76. DEPENDENCY VERIFICATION

Before importing any third-party library:

1.  inspect package.json
2.  verify installed version
3.  verify framework compatibility
4.  use the installed API
5.  if missing, explicitly identify the dependency addition
6.  install only when justified

Never write:

"Assuming Framer Motion is installed."

Never invent an import.

The design-taste skill likewise requires dependency verification before
introducing third-party libraries. citeturn0search0

### 76.1 Icon policy

Use the project's existing icon system if present.

If no icon system exists, select one deliberately.

Do not mix five icon libraries.

Do not use emojis as UI icons.

------------------------------------------------------------------------

## 77. MOCK / REAL DATA BOUNDARY

The UI must not know whether data is:

-   mock
-   staging
-   production

The service layer owns that distinction.

Good:

`searchService.search(query)`

Bad:

`if (MOCK) renderFakeAnswer()`

Mock data must use the same TypeScript types as production.

Mock responses must contain realistic but clearly controlled demo
content.

Do not make the UI infer backend behavior from filenames.

------------------------------------------------------------------------

## 78. DEMO NARRATIVE

The final demo should feel like one investigation.

### Act 1 --- Enter

User enters NEXUS.

They immediately understand:

**Ask NEX. Get the answer. See the proof.**

### Act 2 --- Bring evidence

User uploads heterogeneous documents.

The system shows truthful processing.

### Act 3 --- Understand

Documents become ready.

The workspace communicates that evidence is now searchable.

### Act 4 --- Investigate

User asks a natural-language question.

NEX searches the permitted sources.

### Act 5 --- Synthesize

NEX returns a multi-source answer.

### Act 6 --- Prove

User clicks a citation.

The Evidence Inspector reveals:

source → page → supporting text.

### Act 7 --- Continue

User asks a follow-up.

Conversation context persists.

### Act 8 --- Restraint

User asks something unsupported.

NEX refuses to invent an answer.

### Act 9 --- Tension

A conflicting source example demonstrates that NEX can surface
disagreement without silently choosing a source.

This sequence demonstrates the actual product value rather than merely
showing visual effects.

------------------------------------------------------------------------

## 79. GOLDEN DEMO COMPOSITION

The most important screenshot/video state should be:

**ANSWER + SOURCE RAIL + EVIDENCE INSPECTOR**

It should visually communicate the product in one frame.

The viewer should immediately understand:

-   what was asked
-   what NEX answered
-   which sources were used
-   where the evidence is
-   that the evidence can be inspected

Avoid using a hero screenshot where the product is only decorative.

------------------------------------------------------------------------

## 80. CREATIVE DEFINITION OF DONE

The frontend is visually complete only when:

-   [ ] It does not resemble a generic SaaS dashboard.
-   [ ] The NEXUS visual identity is consistent across routes.
-   [ ] Typography creates a recognizable hierarchy.
-   [ ] Dark surfaces have intentional depth.
-   [ ] Blue-violet accent is restrained.
-   [ ] Motion has semantic purpose.
-   [ ] Processing feels like transformation.
-   [ ] Search feels like investigation.
-   [ ] Answer feels like synthesis.
-   [ ] Citation feels like relationship.
-   [ ] Evidence feels like proof.
-   [ ] Conflict feels visibly distinct.
-   [ ] Insufficient evidence feels restrained rather than broken.
-   [ ] The three-column workspace feels like one instrument.
-   [ ] Mobile is intentionally redesigned rather than merely squeezed.
-   [ ] Reduced motion preserves usability.
-   [ ] 3D, if present, has a deterministic fallback.
-   [ ] No fabricated visual/data claims exist.
-   [ ] No generic AI imagery has been added.
-   [ ] No unnecessary component-library styling dominates the
    experience.

------------------------------------------------------------------------

## 81. ENGINEERING DEFINITION OF DONE

-   [ ] Build succeeds.
-   [ ] Runtime starts cleanly.
-   [ ] Primary routes work.
-   [ ] Upload service is typed.
-   [ ] Processing status is backend-driven.
-   [ ] Search service is typed.
-   [ ] Conversation state is preserved.
-   [ ] Evidence is backend-driven.
-   [ ] Document preview respects backend access.
-   [ ] 401 is handled.
-   [ ] 403 is handled.
-   [ ] 404 is handled.
-   [ ] 409 is handled.
-   [ ] 422 is handled.
-   [ ] 429 is handled.
-   [ ] 500 is handled.
-   [ ] Network errors are handled.
-   [ ] Loading states are explicit.
-   [ ] Empty states are explicit.
-   [ ] Error states are explicit.
-   [ ] Restricted states are explicit.
-   [ ] No sensitive metadata leaks through the UI.
-   [ ] No API assumptions remain undocumented.
-   [ ] No unused experimental 3D code remains in production.
-   [ ] No invented assets remain.
-   [ ] No unverified dependency imports remain.

------------------------------------------------------------------------

## 82. FINAL AGENT PRE-FLIGHT

Before declaring completion, the builder must answer:

### Product

1.  Can a user upload evidence?
2.  Can the user see truthful processing?
3.  Can the user ask a question?
4.  Can NEX return a multi-source answer?
5.  Can the user inspect evidence?
6.  Can the user open the cited page?
7.  Can the user ask a follow-up?
8.  Can NEX decline when evidence is insufficient?
9.  Can NEX surface conflicting sources?
10. Are permissions respected?

### Visual

1.  Does the product feel like NEXUS?
2.  Does it avoid generic SaaS patterns?
3.  Is the visual hierarchy obvious?
4.  Is the typography deliberate?
5.  Is motion meaningful?
6.  Does the interface feel immersive without becoming distracting?
7.  Does the evidence relationship read visually?

### Technical

1.  Did you inspect dependencies before importing?
2.  Did you verify every API field?
3.  Did you avoid inventing endpoints?
4.  Did you avoid inventing backend states?
5.  Did you verify runtime behavior?
6.  Did you verify responsive behavior?
7.  Did you verify keyboard behavior?
8.  Did you verify reduced motion?
9.  Did you verify 3D fallback if applicable?

If any answer is "no", the build is not done.

------------------------------------------------------------------------

## 83. ROLLBACK PRINCIPLE   

Every major phase must be recoverable.

Recommended checkpoints:

`nexus/phase-00-recon`

`nexus/phase-01-structural-skeleton`

`nexus/phase-02-visual-dna`

`nexus/phase-03-vertical-slice`

`nexus/phase-04-immersive-lab`

`nexus/phase-05-cinematic`

`nexus/phase-06-integration`

`nexus/phase-07-adversarial-review`

`nexus/phase-08-final`

If a visual experiment damages product usability, revert the experiment
rather than weakening the product.

If 3D introduces instability, revert 3D integration while preserving the
DOM/CSS implementation.

If motion introduces accessibility or performance problems, reduce
motion before removing functional capability.

------------------------------------------------------------------------

## 84. FINAL PRIORITY ORDER

When time is limited, use this order:

### P0 --- Product truth

UPLOAD → READY → ASK → ANSWER → CITATION → EVIDENCE

### P0 --- Reliability

INSUFFICIENT EVIDENCE CONFLICT ERROR RESTRICTED

### P0 --- Visual identity

TYPOGRAPHY COMPOSITION SPACING SURFACES EVIDENCE RELATIONSHIP

### P1 --- Motion

PROCESSING TRANSFORMATION CITATION REVEAL STATE TRANSITIONS
MICRO-INTERACTIONS

### P1 --- Responsive

MOBILE WORKSPACE EVIDENCE SHEET SOURCE COLLAPSE

### P2 --- Immersive

3D SCROLL CHOREOGRAPHY POST-PROCESSING ADVANCED PARTICLES

Never sacrifice P0 for P2.

------------------------------------------------------------------------

# 85. FINAL PRINCIPLE --- MAKE THE PROOF VISIBLE

NEXUS succeeds when the interface makes one idea undeniable:

**An answer is more useful when the user can inspect why it is true.**

The product should therefore never visually separate:

**ANSWER**

from

**EVIDENCE**

The design language should make their relationship obvious.

The final mental model is:

``` text
DOCUMENTS
    ↓
UNDERSTAND
    ↓
INDEX
    ↓
RETRIEVE
    ↓
COMBINE
    ↓
ANSWER
    ↓
PROVE
```

And the final engineering rule remains:

**Make fewer things.**

**Make them technically real.**

**Make every visible interaction traceable to backend state.**

**Make the proof visible.**
