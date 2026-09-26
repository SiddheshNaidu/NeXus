/**
 * NEXUS Frontend Type Contracts
 * All shapes derived directly from backend Pydantic schemas.
 */

export type DocumentStatus = "queued" | "processing" | "ready" | "failed";

export type ProcessingStage =
  | "detecting"
  | "routing"
  | "extracting"
  | "ocr"
  | "structuring"
  | "indexing"
  | "ready";

export type ProcessState =
  | "QUEUED"
  | "DETECTING"
  | "ROUTING"
  | "EXTRACTING"
  | "STRUCTURING"
  | "INDEXING"
  | "READY"
  | "FAILED";

export type SearchStatus =
  | "answered"
  | "insufficient_evidence"
  | "conflict"
  | "no_results"
  | "error"
  | "access_restricted";

export type AnswerStatus =
  | "SUCCESS"
  | "INSUFFICIENT_EVIDENCE"
  | "CONFLICT"
  | "NO_RESULTS"
  | "ERROR"
  | "ACCESS_RESTRICTED";

// Identity
export interface UserRead {
  id: string;
  name: string;
  email: string;
  created_at: string;
}

export interface WorkspaceWithRole {
  id: string;
  name: string;
  mode: "personal" | "organization";
  created_at: string;
  role: "viewer" | "contributor" | "admin";
}

export interface MeResponse {
  user: UserRead;
  workspaces: WorkspaceWithRole[];
}

// Collections
export interface CollectionRead {
  id: string;
  workspace_id: string;
  name: string;
  created_at: string;
}

// Documents
export interface DocumentRead {
  id: string;
  name: string;
  workspace_id: string;
  collection_id: string | null;
  mime_type: string | null;
  size_bytes: number | null;
  page_count: number | null;
  status: string;
  processing_stage: string | null;
  processing_progress: number | null;
  processing_route: string | null;
  storage_key: string | null;
  document_hash: string | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentUploadResponse {
  document: DocumentRead;
  job_id: string;
}

export interface DocumentStatusResponse {
  document_id: string;
  status: string;
  stage: string | null;
  progress: number | null;
  message: string | null;
}

export interface DocumentSource {
  id: string;
  filename: string;
  sizeBytes: number;
  status: ProcessState;
  uploadedAt: string;
  workspaceId: string;
  processingStage: string | null;
  processingProgress: number | null;
  mimeType: string | null;
}

// Evidence
export interface EvidenceRead {
  id: string;
  chunk_id: string;
  document_id: string;
  page_number: number | null;
  section: string | null;
  text: string;
  relevance_score: number | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
}

export interface Citation {
  id: string;
  documentId: string;
  documentTitle: string;
  page?: string;
  section?: string;
  extractedText: string;
  relevanceScore?: number;
}

export interface EvidenceContext {
  documentId: string;
  documentTitle: string;
  citationId: string;
  page?: string;
  section?: string;
  extractedText: string;
  surroundingContext: string;
}

// Conversations
export interface ConversationRead {
  id: string;
  workspace_id: string;
  user_id: string;
  created_at: string;
  updated_at: string;
}

export interface MessageRead {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  result_json: Record<string, unknown> | null;
  created_at: string;
}

export interface ConversationWithMessages {
  id: string;
  workspace_id: string;
  user_id: string;
  messages: MessageRead[];
}

export interface Message {
  id: string;
  role: "user" | "nexus";
  content: string;
  status?: AnswerStatus;
  citations?: Citation[];
  conflictingSources?: { sourceA: string; sourceB: string; detail: string }[];
  isStreaming?: boolean;
}

export interface Conversation {
  id: string;
  messages: Message[];
}

// Search / RAG
export interface SendMessageResponse {
  user_message: MessageRead;
  assistant_message: MessageRead;
  evidence: EvidenceRead[];
}

export interface SseEvidenceEvent {
  type: "evidence";
  chunks: ChunkSearchResult[];
}

export interface SseTextEvent {
  type: "text";
  text: string;
}

export interface SseDoneEvent {
  type: "done";
}

export type SseEvent = SseEvidenceEvent | SseTextEvent | SseDoneEvent;

// Vector search
export interface ChunkSearchResult {
  chunk_id: string;
  document_id: string;
  document_name: string;
  chunk_index: number;
  text: string;
  score: number;
}

export interface ChunkSearchResponse {
  query: string;
  results: ChunkSearchResult[];
}
