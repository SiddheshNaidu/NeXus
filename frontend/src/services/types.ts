export type ProcessState = 
  | "QUEUED"
  | "DETECTING"
  | "ROUTING"
  | "EXTRACTING"
  | "STRUCTURING"
  | "INDEXING"
  | "READY"
  | "FAILED";

export type AnswerStatus = 
  | "SUCCESS"
  | "INSUFFICIENT_EVIDENCE"
  | "CONFLICT"
  | "NO_RESULTS"
  | "ERROR"
  | "ACCESS_RESTRICTED";

export interface DocumentSource {
  id: string;
  filename: string;
  sizeBytes: number;
  status: ProcessState;
  uploadedAt: string;
}

export interface Citation {
  id: string;
  documentId: string;
  documentTitle: string;
  page?: string;
  section?: string;
  extractedText: string;
}

export interface Message {
  id: string;
  role: "user" | "nexus";
  content: string;
  status?: AnswerStatus;
  citations?: Citation[];
  conflictingSources?: { sourceA: string; sourceB: string; detail: string }[];
}

export interface Conversation {
  id: string;
  messages: Message[];
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