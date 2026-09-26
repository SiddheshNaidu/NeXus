/**
 * NEXUS Documents Service
 *
 * Wraps all document-related backend endpoints:
 *   POST /workspaces/{workspace_id}/documents  - upload
 *   GET  /documents/{document_id}/status       - poll status
 *   GET  /documents/{document_id}              - fetch record
 */

import { api, getActiveWorkspaceId, ApiError } from "./apiClient";
import {
  DocumentRead,
  DocumentSource,
  DocumentStatusResponse,
  DocumentUploadResponse,
  ProcessState,
} from "./types";

function mapStatus(
  status: string,
  stage: string | null | undefined,
): ProcessState {
  const upper = status.toUpperCase();

  if (upper === "READY") return "READY";
  if (upper === "FAILED") return "FAILED";

  if (upper === "PROCESSING" || upper === "QUEUED") {
    if (!stage) return upper === "QUEUED" ? "QUEUED" : "DETECTING";
    switch (stage.toLowerCase()) {
      case "detecting": return "DETECTING";
      case "routing":   return "ROUTING";
      case "extracting":
      case "ocr":       return "EXTRACTING";
      case "structuring": return "STRUCTURING";
      case "indexing":  return "INDEXING";
      case "ready":     return "READY";
      default:          return "DETECTING";
    }
  }

  return "QUEUED";
}

function toDocumentSource(doc: DocumentRead): DocumentSource {
  return {
    id: doc.id,
    filename: doc.name,
    sizeBytes: doc.size_bytes ?? 0,
    status: mapStatus(doc.status, doc.processing_stage),
    uploadedAt: doc.created_at,
    workspaceId: doc.workspace_id,
    processingStage: doc.processing_stage,
    processingProgress: doc.processing_progress,
    mimeType: doc.mime_type,
  };
}

function statusResponseToSource(
  base: DocumentSource,
  status: DocumentStatusResponse,
): DocumentSource {
  return {
    ...base,
    status: mapStatus(status.status, status.stage),
    processingStage: status.stage,
    processingProgress: status.progress,
  };
}

export const documentsService = {
  async uploadDocument(
    file: File,
    workspaceId?: string,
  ): Promise<DocumentSource> {
    const wsId = workspaceId ?? getActiveWorkspaceId();
    if (!wsId) {
      throw new Error(
        "No active workspace. Call identityService.resolveActiveWorkspace() first.",
      );
    }

    const form = new FormData();
    form.append("file", file);

    const response = await api.postForm<DocumentUploadResponse>(
      `/workspaces/${wsId}/documents`,
      form,
    );

    return toDocumentSource(response.document);
  },

  async getDocumentStatus(
    id: string,
    currentSource?: DocumentSource,
  ): Promise<DocumentSource> {
    const status = await api.get<DocumentStatusResponse>(
      `/documents/${id}/status`,
    );

    if (currentSource) {
      return statusResponseToSource(currentSource, status);
    }

    const doc = await api.get<DocumentRead>(`/documents/${id}`);
    return toDocumentSource({ ...doc, status: status.status, processing_stage: status.stage, processing_progress: status.progress } as DocumentRead);
  },

  async getDocument(id: string): Promise<DocumentSource> {
    const doc = await api.get<DocumentRead>(`/documents/${id}`);
    return toDocumentSource(doc);
  },

  async getAllDocuments(workspaceId?: string): Promise<DocumentSource[]> {
    const wsId = workspaceId ?? getActiveWorkspaceId();
    if (!wsId) return [];

    try {
      return getSessionDocuments(wsId);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return [];
      return [];
    }
  },
};

const SESSION_DOCS_KEY = "nexus_session_docs";

function getSessionDocuments(workspaceId: string): DocumentSource[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = sessionStorage.getItem(`${SESSION_DOCS_KEY}_${workspaceId}`);
    return raw ? (JSON.parse(raw) as DocumentSource[]) : [];
  } catch {
    return [];
  }
}

export function saveSessionDocument(doc: DocumentSource): void {
  if (typeof window === "undefined") return;
  const key = `${SESSION_DOCS_KEY}_${doc.workspaceId}`;
  try {
    const existing = getSessionDocuments(doc.workspaceId);
    const updated = [doc, ...existing.filter((d) => d.id !== doc.id)];
    sessionStorage.setItem(key, JSON.stringify(updated));
  } catch {
  }
}

export function updateSessionDocument(doc: DocumentSource): void {
  if (typeof window === "undefined") return;
  const key = `${SESSION_DOCS_KEY}_${doc.workspaceId}`;
  try {
    const existing = getSessionDocuments(doc.workspaceId);
    const updated = existing.map((d) => (d.id === doc.id ? doc : d));
    sessionStorage.setItem(key, JSON.stringify(updated));
  } catch {
  }
}
