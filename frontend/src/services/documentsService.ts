import { DocumentSource, ProcessState } from "./types";

// In-memory mock DB for document statuses
const documentStore = new Map<string, DocumentSource>();

// Private internal function, not exposed on the exported service
async function simulateLifecycle(id: string) {
  const sequence: ProcessState[] = ["DETECTING", "ROUTING", "EXTRACTING", "STRUCTURING", "INDEXING", "READY"];
  for (const state of sequence) {
    await new Promise(resolve => setTimeout(resolve, 1500));
    const doc = documentStore.get(id);
    if (doc) {
      doc.status = state;
      documentStore.set(id, doc);
    }
  }
}

export const documentsService = {
  async uploadDocument(file: File): Promise<DocumentSource> {
    const id = "DOC-" + Math.random().toString(36).substring(2, 9).toUpperCase();
    const doc: DocumentSource = {
      id,
      filename: file.name,
      sizeBytes: file.size,
      status: "QUEUED",
      uploadedAt: new Date().toISOString()
    };
    
    documentStore.set(id, doc);
    
    // Simulate backend lifecycle progression asynchronously
    simulateLifecycle(id);
    
    return doc;
  },

  async getDocumentStatus(id: string): Promise<DocumentSource> {
    const doc = documentStore.get(id);
    if (!doc) throw new Error("Document not found");
    return doc;
  },

  async getAllDocuments(): Promise<DocumentSource[]> {
    return Array.from(documentStore.values()).sort((a, b) => 
      new Date(b.uploadedAt).getTime() - new Date(a.uploadedAt).getTime()
    );
  }
};
