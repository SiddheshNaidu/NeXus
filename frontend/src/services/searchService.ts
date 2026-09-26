/**
 * NEXUS Search / Conversation Service
 */

import { api, getActiveWorkspaceId, streamRequest } from "./apiClient";
import {
  AnswerStatus,
  ChunkSearchResponse,
  Citation,
  Conversation,
  ConversationRead,
  ConversationWithMessages,
  EvidenceRead,
  Message,
  MessageRead,
  SendMessageResponse,
  SseDoneEvent,
  SseEvidenceEvent,
  SseTextEvent,
} from "./types";

function evidenceToCitations(evidence: EvidenceRead[]): Citation[] {
  return evidence.map((ev) => ({
    id: ev.id,
    documentId: ev.document_id,
    documentTitle:
      (ev.metadata_json?.document_name as string | undefined) ??
      `Document ${ev.document_id.slice(0, 8)}`,
    page: ev.page_number != null ? String(ev.page_number) : undefined,
    section: ev.section ?? undefined,
    extractedText: ev.text,
    relevanceScore: ev.relevance_score ?? undefined,
  }));
}

function assistantMessageToUiMessage(
  msg: MessageRead,
  evidence: EvidenceRead[],
): Message {
  const citations = evidenceToCitations(evidence);

  let status: AnswerStatus = "SUCCESS";
  if (evidence.length === 0) {
    status = "INSUFFICIENT_EVIDENCE";
  }

  return {
    id: msg.id,
    role: "nexus",
    content: msg.content,
    status,
    citations: citations.length > 0 ? citations : undefined,
  };
}

export const searchService = {
  async createConversation(workspaceId?: string): Promise<Conversation> {
    const wsId = workspaceId ?? getActiveWorkspaceId();
    if (!wsId) {
      throw new Error(
        "No active workspace. Ensure identityService.resolveActiveWorkspace() has been called.",
      );
    }

    const conv = await api.post<ConversationRead>(
      `/workspaces/${wsId}/conversations`,
    );

    return { id: conv.id, messages: [] };
  },

  async getConversation(conversationId: string): Promise<Conversation> {
    const conv = await api.get<ConversationWithMessages>(
      `/conversations/${conversationId}`,
    );

    const messages: Message[] = conv.messages.map((msg) => ({
      id: msg.id,
      role: msg.role === "user" ? "user" : "nexus",
      content: msg.content,
      status: msg.role === "assistant" ? "SUCCESS" : undefined,
    }));

    return { id: conv.id, messages };
  },

  async askQuestion(
    conversationId: string,
    query: string,
  ): Promise<Message> {
    const response = await api.post<SendMessageResponse>(
      `/conversations/${conversationId}/messages`,
      { content: query },
    );

    return assistantMessageToUiMessage(
      response.assistant_message,
      response.evidence,
    );
  },

  async streamQuestion(
    conversationId: string,
    query: string,
    handlers: {
      onEvidence?: (ev: SseEvidenceEvent) => void;
      onToken?: (ev: SseTextEvent) => void;
      onDone?: (ev: SseDoneEvent) => void;
    },
  ): Promise<{ content: string; citations: Citation[] }> {
    const gen = streamRequest(`/conversations/${conversationId}/messages/stream`, {
      content: query,
    });

    let assembled = "";
    let citations: Citation[] = [];

    for await (const raw of gen) {
      const event = raw as { type: string; [key: string]: unknown };

      if (event.type === "evidence") {
        const ev = event as unknown as SseEvidenceEvent;
        citations = ev.chunks.map((c) => ({
          id: c.chunk_id,
          documentId: c.document_id,
          documentTitle: c.document_name,
          extractedText: c.text,
          relevanceScore: c.score,
        }));
        handlers.onEvidence?.(ev);
      } else if (event.type === "text") {
        const ev = event as unknown as SseTextEvent;
        assembled += ev.text;
        handlers.onToken?.(ev);
      } else if (event.type === "done") {
        handlers.onDone?.(event as unknown as SseDoneEvent);
        break;
      }
    }

    return { content: assembled, citations };
  },

  async semanticSearch(
    query: string,
    limit = 10,
    workspaceId?: string,
  ): Promise<ChunkSearchResponse> {
    const wsId = workspaceId ?? getActiveWorkspaceId();
    if (!wsId) {
      throw new Error("No active workspace.");
    }

    return api.get<ChunkSearchResponse>(
      `/workspaces/${wsId}/search?q=${encodeURIComponent(query)}&limit=${limit}`,
    );
  },
};
