import { Conversation, Message, AnswerStatus, Citation } from "./types";

export const searchService = {
  async createConversation(): Promise<Conversation> {
    const id = "CONV-" + Math.random().toString(36).substring(2, 9).toUpperCase();
    return { id, messages: [] };
  },

  async askQuestion(query: string): Promise<Message> {
    // Simulate network delay
    await new Promise(resolve => setTimeout(resolve, 2000));

    let status: AnswerStatus = "SUCCESS";
    let content = "";
    let citations: Citation[] = [];
    let conflictingSources: { sourceA: string; sourceB: string; detail: string }[] = [];

    const lowerQuery = query.toLowerCase();

    if (lowerQuery.includes("conflict")) {
      status = "CONFLICT";
      content = "Sources provide conflicting information regarding this policy.";
      conflictingSources = [
        { sourceA: "Policy V1.pdf", sourceB: "Finance Addendum.pdf", detail: "V1 says ₹40,000, Addendum says ₹50,000." }
      ];
    } else if (lowerQuery.includes("insufficient") || lowerQuery.includes("unknown")) {
      status = "INSUFFICIENT_EVIDENCE";
      content = "NEXUS could not verify an answer from the available sources.";
    } else if (lowerQuery.includes("none") || lowerQuery.includes("nothing")) {
      status = "NO_RESULTS";
      content = "No relevant evidence was found across the indexed workspace.";
    } else if (lowerQuery.includes("error")) {
      status = "ERROR";
      content = "An internal engine error occurred while routing this query.";
    } else if (lowerQuery.includes("restricted")) {
      status = "ACCESS_RESTRICTED";
      content = "You do not have permission to access the sources required to answer this query.";
    } else {
      status = "SUCCESS";
      content = "The new reimbursement limit is ₹50,000 per designated business trip.";
      citations = [
        {
          id: "cit-001",
          documentId: "DOC-8992",
          documentTitle: "Q3 Financial Report 2026.pdf",
          page: "12",
          section: "4.2 Travel",
          extractedText: "Effective Q3 2026, the maximum allowable limit for international travel expenses, including flights and accommodation, has been revised to ₹50,000 per designated business trip."
        }
      ];
    }

    const nexMsg: Message = {
      id: (Date.now() + 1).toString(),
      role: "nexus",
      content,
      status,
      citations,
      conflictingSources
    };

    return nexMsg;
  }
};