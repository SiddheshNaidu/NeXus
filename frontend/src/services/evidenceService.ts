/**
 * NEXUS Evidence Service
 */

import { api } from "./apiClient";
import { DocumentRead, EvidenceContext } from "./types";

export const evidenceService = {
  async getEvidenceContext(
    documentId: string,
    citationId?: string,
    extractedText?: string,
    pageNumber?: string,
    section?: string,
  ): Promise<EvidenceContext> {
    const doc = await api.get<DocumentRead>(`/documents/${documentId}`);

    return {
      documentId: doc.id,
      documentTitle: doc.name,
      citationId: citationId ?? `chunk-${documentId.slice(0, 8)}`,
      page: pageNumber,
      section: section ?? undefined,
      extractedText:
        extractedText ??
        "Evidence text not available — open the source document to view this passage.",
      surroundingContext:
        doc.storage_key
          ? `[Full document available in backend storage — page ${pageNumber ?? "?"} of ${doc.page_count ?? "?"}]`
          : "[Document body requires the backend document preview endpoint to display the full page context.]",
    };
  },

  async getDocumentMeta(documentId: string): Promise<DocumentRead> {
    return api.get<DocumentRead>(`/documents/${documentId}`);
  },
};
