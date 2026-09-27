"use client";

/**
 * Search / Chat page — NEXUS Active Workspace
 *
 * Architecture
 * ────────────
 * Three-column layout (hidden on mobile → stacked):
 *   Left  (col-span-3)  Source Rail    — indexed documents
 *   Centre (col-span-6) Answer Canvas  — streaming chat thread
 *   Right  (col-span-3) Evidence Panel — active citation detail
 *
 * SSE stream handling
 * ───────────────────
 * Uses searchService.streamQuestion() which wraps the shared streamRequest()
 * generator from apiClient.ts.  The stream yields three event types:
 *
 *   { type: "evidence", chunks: ChunkSearchResult[] }
 *   { type: "text",     text: string }
 *   { type: "done" }
 *
 * Token accumulation uses a ref (not state) to avoid re-renders on every
 * character; a single setState flush happens at the end or on abort.
 *
 * Auto-scroll
 * ───────────
 * A sentinel <div ref={bottomRef}> sits after the last message.  Two
 * effects scroll it into view: one when a new message is appended, one
 * on every streaming tick so the user always sees the latest token.
 */

import * as React from "react";
import { motion, AnimatePresence } from "motion/react";
import { Navbar } from "@/components/ui/navbar";
import {
  ArrowRight,
  CaretLeft,
  FileText,
  MagnifyingGlass,
  Quotes,
  Sidebar,
  Textbox,
  X,
} from "@phosphor-icons/react";
import { searchService } from "@/services/searchService";
import { documentsService } from "@/services/documentsService";
import { useNexusSession } from "@/hooks/useNexusSession";
import { Citation, DocumentSource } from "@/services/types";
import { ChatMessage, ChatMsg } from "@/components/ui/chat-message";
import Link from "next/link";
import { useRouter } from "next/navigation";

// ─── Layout constants ─────────────────────────────────────────────────────────

/** Source Rail width — within the 260–320px design range (w-72 = 288px). */
const LEFT_RAIL_WIDTH = 288;
/** Evidence Inspector width — within the 300–380px design range (w-80 = 320px). */
const RIGHT_RAIL_WIDTH = 320;

const SIDEBAR_SPRING = {
  type: "spring" as const,
  stiffness: 380,
  damping: 36,
  mass: 0.8,
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Stable ID for a new message placeholder. */
function nextId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function SearchPage() {
  const router = useRouter();
  const { workspace, isReady } = useNexusSession();

  // ── Conversation state ────────────────────────────────────────────────────
  const [conversationId, setConversationId] = React.useState<string | null>(null);
  const [messages, setMessages] = React.useState<ChatMsg[]>([]);
  const [query, setQuery] = React.useState("");
  const [isStreaming, setIsStreaming] = React.useState(false);

  /**
   * Accumulated token text for the in-flight assistant message.
   * Stored in a ref to avoid triggering a re-render on every token;
   * we only push it to state on the streaming message's `streamingText` prop
   * via a separate tick-based counter.
   */
  const streamAccRef = React.useRef("");
  /** Incrementing counter to force a re-render on each token batch. */
  const [tokenTick, setTokenTick] = React.useState(0);
  /** ID of the placeholder "streaming" message currently in the list. */
  const streamingMsgIdRef = React.useRef<string | null>(null);

  // ── Document sources ──────────────────────────────────────────────────────
  const [sources, setSources] = React.useState<DocumentSource[]>([]);

  // ── Right-panel active citation ──────────────────────────────────────────
  const [activeCitation, setActiveCitation] = React.useState<Citation | null>(null);

  // ── Collapsible sidebars (desktop) ───────────────────────────────────────
  const [isLeftSidebarOpen, setIsLeftSidebarOpen] = React.useState(true);
  /** Starts closed; opens automatically when a citation is selected. */
  const [isRightSidebarOpen, setIsRightSidebarOpen] = React.useState(false);

  // ── Auto-scroll sentinel ──────────────────────────────────────────────────
  const bottomRef = React.useRef<HTMLDivElement>(null);
  const scrollContainerRef = React.useRef<HTMLDivElement>(null);

  // ── Session bootstrap ─────────────────────────────────────────────────────
  React.useEffect(() => {
    if (!isReady || !workspace) return;

    // Create a fresh conversation and fetch indexed documents in parallel.
    Promise.all([
      searchService.createConversation(workspace.id),
      documentsService.getAllDocuments(workspace.id),
    ]).then(([conv, docs]) => {
      setConversationId(conv.id || null);
      setSources(docs);
    }).catch((err) => {
      console.error("Session bootstrap failed:", err);
      setConversationId(null);
    });
  }, [isReady, workspace]);

  // ── Auto-scroll on new messages ───────────────────────────────────────────
  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length]);

  // ── Auto-scroll on each streaming token ──────────────────────────────────
  React.useEffect(() => {
    if (!isStreaming) return;
    bottomRef.current?.scrollIntoView({ behavior: "instant", block: "end" });
  }, [tokenTick, isStreaming]);

  // ── Submit ─────────────────────────────────────────────────────────────────
  const handleSubmit = React.useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!query.trim() || isStreaming || !conversationId) return;

      const userText = query.trim();
      setQuery("");

      // 1. Append user message immediately.
      const userMsgId = nextId();
      setMessages((prev) => [
        ...prev,
        { id: userMsgId, role: "user", content: userText } satisfies ChatMsg,
      ]);

      // 2. Append a streaming placeholder for the assistant.
      const asstId = nextId();
      streamingMsgIdRef.current = asstId;
      streamAccRef.current = "";
      setMessages((prev) => [
        ...prev,
        { id: asstId, role: "nexus", content: "", isStreaming: true } satisfies ChatMsg,
      ]);
      setIsStreaming(true);

      try {
        const result = await searchService.streamQuestion(
          conversationId,
          userText,
          {
            onToken: (ev) => {
              // Accumulate without state update; bump tick to trigger render.
              streamAccRef.current += ev.text;
              setTokenTick((t) => t + 1);
            },
          },
        );

        // 3. Replace placeholder with finalised message.
        const finalMsg: ChatMsg = {
          id: asstId,
          role: "nexus",
          content: result.content || streamAccRef.current,
          isStreaming: false,
          status: result.citations.length > 0 ? "SUCCESS" : "INSUFFICIENT_EVIDENCE",
          citations: result.citations.length > 0 ? result.citations : undefined,
        };

        setMessages((prev) =>
          prev.map((m) => (m.id === asstId ? finalMsg : m)),
        );
      } catch (err) {
        console.error("Stream error:", err);

        const errMsg: ChatMsg = {
          id: asstId,
          role: "nexus",
          content:
            "An error occurred while querying the engine. Is the backend running?",
          isStreaming: false,
          status: "ERROR",
        };

        setMessages((prev) =>
          prev.map((m) => (m.id === asstId ? errMsg : m)),
        );
      } finally {
        setIsStreaming(false);
        streamAccRef.current = "";
        streamingMsgIdRef.current = null;
      }
    },
    [query, isStreaming, conversationId],
  );

  // ── Keyboard shortcut: Cmd/Ctrl+Enter submits ─────────────────────────────
  const handleKeyDown = React.useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        handleSubmit(e as unknown as React.FormEvent);
      }
      // Plain Enter without shift submits (single-line behaviour)
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit(e as unknown as React.FormEvent);
      }
    },
    [handleSubmit],
  );

  // ── Citation click ────────────────────────────────────────────────────────
  const handleCitationClick = React.useCallback(
    (cit: Citation) => {
      if (typeof window !== "undefined" && window.innerWidth < 1024) {
        router.push(
          `/evidence/${cit.documentId}?citation=${cit.id}&text=${encodeURIComponent(cit.extractedText)}&page=${cit.page ?? ""}`,
        );
      } else {
        setActiveCitation(cit);
        setIsRightSidebarOpen(true);
      }
    },
    [router],
  );

  // ── Derived ───────────────────────────────────────────────────────────────
  const inputDisabled = isStreaming || !conversationId;
  const isEmpty = messages.length === 0 && !isStreaming;

  /**
   * Snapshot the streaming accumulator outside JSX so the linter does not
   * flag reading a ref value during render.  tokenTick changing forces
   * a re-render so this re-derives on every token.
   */
  const liveStreamText = streamAccRef.current; // safe: used in render, deps tracked via tokenTick

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <main className="h-[100dvh] w-full bg-[#050505] flex flex-col text-zinc-50 overflow-hidden">
      <Navbar />
      {/* Spacer matching fixed navbar height so the workspace gets a real remaining height */}
      <div className="h-14 md:h-16 flex-shrink-0" aria-hidden />

      {/* Three-column workspace — flex so sidebars can animate width and chat fills the rest */}
      <div className="flex-1 min-h-0 flex w-full border-t border-white/5 overflow-hidden">

        {/* ── LEFT: Source Rail ─────────────────────────────────────────── */}
        <motion.aside
          initial={false}
          animate={{ width: isLeftSidebarOpen ? LEFT_RAIL_WIDTH : 0 }}
          transition={SIDEBAR_SPRING}
          className="hidden lg:flex flex-col h-full min-h-0 flex-shrink-0 overflow-hidden border-r border-white/5 bg-[#050505]"
        >
          <div className="flex w-[288px] h-full min-h-0 flex-col">
            <div className="flex-shrink-0 px-5 py-4 border-b border-white/5 flex items-center justify-between gap-2">
              <div className="min-w-0 flex items-center gap-2">
                <h2 className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-500 truncate">
                  Source Rail
                </h2>
                <span className="text-[10px] font-mono text-zinc-600 tabular-nums">
                  {sources.length}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setIsLeftSidebarOpen(false)}
                className="h-7 w-7 flex items-center justify-center text-zinc-500 hover:text-zinc-200 hover:bg-white/5 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
                aria-label="Collapse source rail"
              >
                <CaretLeft size={14} />
              </button>
            </div>

            <div
              data-lenis-prevent
              className="flex-1 min-h-0 overflow-y-auto overscroll-contain"
            >
              {sources.length === 0 ? (
                <div className="p-8 text-center flex flex-col items-center gap-4">
                  <FileText size={22} className="text-zinc-700" />
                  <p className="text-xs text-zinc-500">
                    No documents indexed in this workspace.
                  </p>
                  <Link
                    href="/upload"
                    className="text-[10px] font-mono uppercase tracking-widest text-indigo-400 hover:text-indigo-300 transition-colors border border-indigo-500/30 px-4 py-2 hover:bg-indigo-500/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
                  >
                    Ingest Sources
                  </Link>
                </div>
              ) : (
                <div className="divide-y divide-white/[0.04]">
                  {sources.map((doc) => (
                    <div
                      key={doc.id}
                      className="group flex items-start gap-3 px-5 py-4 hover:bg-white/[0.025] transition-colors cursor-default"
                    >
                      <FileText
                        size={14}
                        className="text-zinc-600 group-hover:text-indigo-400 mt-0.5 flex-shrink-0 transition-colors"
                      />
                      <div className="min-w-0 flex-1">
                        <p className="text-[10px] font-mono text-zinc-600 mb-0.5 uppercase tracking-wider">
                          {doc.status}
                        </p>
                        <p className="text-xs font-medium text-zinc-400 group-hover:text-zinc-200 transition-colors line-clamp-2 leading-relaxed">
                          {doc.filename}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </motion.aside>

        {/* ── CENTRE: Answer Canvas ─────────────────────────────────────── */}
        <section className="relative flex-1 min-w-0 flex flex-col h-full min-h-0 bg-[#0a0a0a] overflow-hidden">

          {/* Reopen controls when a rail is collapsed (desktop only) */}
          <div className="hidden lg:flex absolute top-3 left-3 z-20 gap-2">
            <AnimatePresence>
              {!isLeftSidebarOpen && (
                <motion.button
                  key="open-left"
                  type="button"
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -6 }}
                  transition={{ duration: 0.15 }}
                  onClick={() => setIsLeftSidebarOpen(true)}
                  className="h-8 px-2.5 flex items-center gap-1.5 border border-white/10 bg-[#0d0d0d]/90 backdrop-blur-sm text-zinc-400 hover:text-zinc-100 hover:border-white/20 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
                  aria-label="Open source rail"
                >
                  <Sidebar size={14} />
                  <span className="text-[9px] font-mono uppercase tracking-widest">
                    Sources
                  </span>
                </motion.button>
              )}
            </AnimatePresence>
          </div>
          <div className="hidden lg:flex absolute top-3 right-3 z-20 gap-2">
            <AnimatePresence>
              {!isRightSidebarOpen && (
                <motion.button
                  key="open-right"
                  type="button"
                  initial={{ opacity: 0, x: 6 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 6 }}
                  transition={{ duration: 0.15 }}
                  onClick={() => setIsRightSidebarOpen(true)}
                  className="h-8 px-2.5 flex items-center gap-1.5 border border-white/10 bg-[#0d0d0d]/90 backdrop-blur-sm text-zinc-400 hover:text-zinc-100 hover:border-white/20 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
                  aria-label="Open evidence inspector"
                >
                  <span className="text-[9px] font-mono uppercase tracking-widest">
                    Evidence
                  </span>
                  <Quotes size={14} />
                </motion.button>
              )}
            </AnimatePresence>
          </div>

          {/* Scrollable message list */}
          <div
            ref={scrollContainerRef}
            data-lenis-prevent
            className="flex-1 h-full min-h-0 overflow-y-auto overscroll-contain"
          >
            <div className="px-6 md:px-12 lg:px-16 py-10 flex flex-col gap-10 pb-36">
              {/* Empty-state prompt */}
              <AnimatePresence mode="wait">
                {isEmpty && (
                  <motion.div
                    key="idle"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0, transition: { duration: 0.15 } }}
                    className="m-auto mt-20 text-center max-w-sm"
                  >
                    <h3 className="text-xl font-medium text-zinc-300 mb-3">
                      Interrogate your documents.
                    </h3>
                    <p className="text-xs text-zinc-500 font-mono tracking-widest uppercase">
                      {isReady
                        ? workspace
                          ? `${workspace.name} · NEX Core`
                          : "NEX Core · No workspace"
                        : "Connecting to engine…"}
                    </p>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Message list */}
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className="w-full max-w-2xl mx-auto"
                >
                  <ChatMessage
                    message={msg}
                    streamingText={msg.isStreaming ? liveStreamText : undefined}
                    onCitationClick={handleCitationClick}
                  />
                </div>
              ))}

              {/* Auto-scroll sentinel */}
              <div ref={bottomRef} className="h-px" aria-hidden />
            </div>
          </div>

          {/* ── Input bar — sticky at the bottom ─────────────────────── */}
          <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-[#0a0a0a] via-[#0a0a0a]/95 to-transparent pt-10 pb-5 px-6 md:px-12 lg:px-16 pointer-events-none">
            <form
              onSubmit={handleSubmit}
              className="relative w-full max-w-2xl mx-auto pointer-events-auto"
            >
              {/* Glass border + focus ring wrapper */}
              <div className="relative flex items-end gap-0 border border-white/10 bg-[#0d0d0d] transition-colors focus-within:border-indigo-500/50 shadow-2xl">
                <MagnifyingGlass
                  size={16}
                  className="absolute left-4 bottom-[14px] text-zinc-600 pointer-events-none"
                />

                {/* Auto-growing textarea for multi-line input */}
                <textarea
                  rows={1}
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    // Auto-grow: reset height, then set to scrollHeight
                    e.target.style.height = "auto";
                    e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
                  }}
                  onKeyDown={handleKeyDown}
                  placeholder={
                    inputDisabled && !isStreaming
                      ? "Connecting to engine…"
                      : "Submit query to engine…"
                  }
                  disabled={inputDisabled}
                  className="
                    flex-1 resize-none overflow-y-auto
                    bg-transparent pl-10 pr-12 py-3.5
                    text-sm text-zinc-100 placeholder:text-zinc-600
                    focus:outline-none leading-relaxed
                    disabled:opacity-50 disabled:cursor-not-allowed
                    max-h-40
                  "
                  style={{ scrollbarWidth: "none" }}
                />

                {/* Submit button */}
                <button
                  type="submit"
                  disabled={!query.trim() || inputDisabled}
                  className="
                    absolute right-0 bottom-0
                    h-full px-4 flex items-end pb-3.5
                    text-zinc-500 hover:text-indigo-400
                    disabled:opacity-30 disabled:hover:text-zinc-500
                    transition-colors focus:outline-none
                    focus-visible:ring-2 focus-visible:ring-indigo-400
                    focus-visible:ring-inset
                  "
                  aria-label="Send"
                >
                  {isStreaming ? (
                    <span className="h-4 w-4 rounded-full border-2 border-indigo-500/50 border-t-indigo-400 animate-spin" />
                  ) : (
                    <ArrowRight size={16} />
                  )}
                </button>
              </div>

              {/* Hint */}
              <p className="mt-1.5 text-right text-[9px] font-mono text-zinc-700 tracking-wider select-none">
                ENTER to send · SHIFT+ENTER for newline
              </p>
            </form>
          </div>
        </section>

        {/* ── RIGHT: Evidence Inspector ─────────────────────────────────── */}
        <motion.aside
          initial={false}
          animate={{ width: isRightSidebarOpen ? RIGHT_RAIL_WIDTH : 0 }}
          transition={SIDEBAR_SPRING}
          className="hidden lg:flex flex-col h-full min-h-0 flex-shrink-0 overflow-hidden border-l border-white/5 bg-[#050505]"
        >
          <div className="flex w-[320px] h-full min-h-0 flex-col">
            <div className="flex-shrink-0 px-5 py-4 border-b border-white/5 flex items-center justify-between gap-2">
              <h2 className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-500 truncate">
                Evidence Inspector
              </h2>
              <button
                type="button"
                onClick={() => setIsRightSidebarOpen(false)}
                className="h-7 w-7 flex items-center justify-center text-zinc-500 hover:text-zinc-200 hover:bg-white/5 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
                aria-label="Close evidence inspector"
              >
                <X size={14} />
              </button>
            </div>

            <div
              data-lenis-prevent
              className="flex-1 min-h-0 overflow-y-auto overscroll-contain p-5"
            >
              <AnimatePresence mode="wait">
                {activeCitation ? (
                  <motion.div
                    key={activeCitation.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="flex flex-col gap-6"
                  >
                    {/* Citation header */}
                    <div>
                      <span className="text-[9px] font-mono text-indigo-400 uppercase tracking-widest mb-2 block">
                        Active Citation
                      </span>
                      <div className="flex items-start gap-2 mb-1">
                        <FileText size={14} className="text-zinc-400 flex-shrink-0 mt-0.5" />
                        <h3 className="text-sm font-medium text-zinc-300 leading-snug">
                          {activeCitation.documentTitle}
                        </h3>
                      </div>
                      <div className="flex gap-2 text-[9px] font-mono text-zinc-600 uppercase tracking-widest pl-5">
                        {activeCitation.page && (
                          <span>Pg {activeCitation.page}</span>
                        )}
                        {activeCitation.section && (
                          <span>· {activeCitation.section}</span>
                        )}
                      </div>
                    </div>

                    {/* Excerpt */}
                    <blockquote className="border-l-2 border-indigo-500 pl-4">
                      <p className="text-sm text-zinc-400 leading-relaxed italic">
                        &ldquo;{activeCitation.extractedText}&rdquo;
                      </p>
                    </blockquote>

                    {/* Relevance */}
                    {activeCitation.relevanceScore != null && (
                      <div className="flex items-center gap-3">
                        <span className="text-[9px] font-mono text-zinc-600 uppercase tracking-wider">
                          Relevance
                        </span>
                        <div className="flex-1 h-0.5 bg-white/5 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-indigo-500 rounded-full"
                            style={{
                              width: `${Math.round(activeCitation.relevanceScore * 100)}%`,
                            }}
                          />
                        </div>
                        <span className="text-[9px] font-mono text-zinc-500 tabular-nums">
                          {Math.round(activeCitation.relevanceScore * 100)}%
                        </span>
                      </div>
                    )}

                    {/* Inspect link */}
                    <Link
                      href={`/evidence/${activeCitation.documentId}?citation=${activeCitation.id}&text=${encodeURIComponent(activeCitation.extractedText)}&page=${activeCitation.page ?? ""}`}
                      className="group flex items-center gap-3 w-full py-3 px-4 border border-white/5 hover:border-white/10 hover:bg-white/[0.025] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 focus-visible:ring-offset-2 focus-visible:ring-offset-[#050505]"
                    >
                      <Textbox
                        size={14}
                        className="text-zinc-500 group-hover:text-zinc-300 transition-colors"
                      />
                      <span className="text-xs font-mono uppercase tracking-widest text-zinc-500 group-hover:text-zinc-300 transition-colors">
                        Inspect Document
                      </span>
                    </Link>
                  </motion.div>
                ) : (
                  <motion.div
                    key="empty"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 0.3 }}
                    exit={{ opacity: 0 }}
                    className="h-full flex flex-col items-center justify-center text-center"
                  >
                    <Quotes size={22} className="text-zinc-600 mb-3" />
                    <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-500 max-w-[180px] leading-relaxed">
                      Click a citation badge to inspect the source evidence
                    </p>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </motion.aside>

      </div>
    </main>
  );
}
