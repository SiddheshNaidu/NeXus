import { EvidenceContext } from "./types";

export const evidenceService = {
  async getEvidenceContext(documentId: string, citationId?: string): Promise<EvidenceContext> {
    await new Promise(resolve => setTimeout(resolve, 800));
    
    return {
      documentId,
      documentTitle: "Q3 Financial Report 2026.pdf",
      citationId: citationId || "cit-001",
      page: "12",
      section: "4.2 Travel",
      extractedText: "Effective Q3 2026, the maximum allowable limit for international travel expenses, including flights and accommodation, has been revised to ₹50,000 per designated business trip.",
      surroundingContext: "[Document body requires backend PDF extraction to display.]"
    };
  }
};