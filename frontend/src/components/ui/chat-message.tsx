"use client";

/**
 * ChatMessage — renders a single turn in the NEXUS conversation.
 *
 * User turns:  right-aligned, frosted glass bubble.
 * NEX turns:   left-aligned, full-width with an optional collapsible
 *              "Sources" accordion that lists evidence chunks.
 *
 * Props:
 *   message          — the message to render (see ChatMsg below)
 *   streamingText    — live token string while isStreaming === true
 *   onCitationClick  — callback invoked when a citation source card is clicked
 */

import * as React from "react";
import { motion, AnimatePresence } from "motion/react";
import { CaretDown, FileText, Quotes, WarningCircle } from "@phosphor-icons/react";
import { Citation, AnswerStatus } from "@/services/types";

// ─── Public shape used by the chat page ──────────────────────────────────────

export interface ChatMsg {
  id: string;
  role: "user" | "nexus";
  content: string;
  /** Truthy while the assistant message is still streaming. */
  isStreaming?: boolean;
  citations?: Citation[];
  status?: AnswerStatus;
}

// ─── Internal sub-components ─────────────────────────────────────────────────

/** Blinking caret that appears at the end of a streaming assistant reply. */
function StreamCursor() {
  return (
    <span
      aria-hidden
      className="inline-block w-[2px] h-[1em] bg-indigo-400 ml-[2px] align-middle animate-pulse"
    />
  );
}

/** Score bar — maps a 0–1 cosine score to a coloured fill. */
function RelevanceBar({ score }: { score?: number }) {
  if (score == null) return null;
  const pct = Math.round(score * 100);
  const colour =
    pct >= 80 ? "bg-emerald-500" : pct >= 50 ? "bg-indigo-500" : "bg-zinc-500";
  return (
    <div className="flex items-center gap-2 mt-1.5">
      <div className="flex-1 h-0.5 bg-white/5 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${colour} transition-all`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[9px] font-mono text-zinc-600 tabular-nums w-8 text-right">
        {pct}%
      </span>
    </div>
  );
}

/** Collapsible Sources accordion attached to an assistant message. */
function SourcesAccordion({
  citations,
  onCitationClick,
}: {
  citations: Citation[];
  onCitationClick?: (citation: Citation) => void;
}) {
  const [open, setOpen] = React.useState(false);

  return (
    <div className="mt-5 border border-white/5 bg-white/[0.02]">
      {/* Header toggle */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 text-left focus:outline-none focus-visible:ring-1 focus-visible:ring-indigo-500 transition-colors hover:bg-white/[0.03]"
        aria-expanded={open}
      >
        <div className="flex items-center gap-2.5">
          <Quotes size={13} className="text-zinc-500 flex-shrink-0" />
          <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-400">
            Sources
          </span>
          <span className="inline-flex items-center justify-center h-4 min-w-[1rem] px-1 bg-white/5 text-[9px] font-mono text-zinc-500 border border-white/10 rounded-sm">
            {citations.length}
          </span>
        </div>
        <motion.span
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <CaretDown size={12} className="text-zinc-500" />
        </motion.span>
      </button>

      {/* Expandable content */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="sources"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.32, 0.72, 0, 1] }}
            className="overflow-hidden"
          >
            <div className="divide-y divide-white/5 border-t border-white/5">
              {citations.map((cit, idx) => (
                <div
                  key={cit.id}
                  onClick={() => onCitationClick?.(cit)}
                  className={`px-4 py-3.5 group ${
                    onCitationClick
                      ? "cursor-pointer hover:bg-white/[0.03] transition-colors"
                      : ""
                  }`}
                  role={onCitationClick ? "button" : undefined}
                  tabIndex={onCitationClick ? 0 : undefined}
                  onKeyDown={(e) => {
                    if (onCitationClick && (e.key === "Enter" || e.key === " ")) {
                      e.preventDefault();
                      onCitationClick(cit);
                    }
                  }}
                >
                  {/* Source header */}
                  <div className="flex items-start gap-2.5 mb-2">
                    <span className="flex-shrink-0 mt-px text-[9px] font-mono text-zinc-600 border border-white/5 px-1 py-0.5 rounded-sm leading-none group-hover:border-indigo-500/40 group-hover:text-indigo-400 transition-colors">
                      {idx + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <FileText
                          size={11}
                          className="text-zinc-500 group-hover:text-indigo-400 transition-colors flex-shrink-0"
                        />
                        <span className="text-[10px] font-mono text-zinc-400 group-hover:text-zinc-200 transition-colors truncate leading-tight">
                          {cit.documentTitle}
                        </span>
                      </div>
                      {cit.page && (
                        <span className="text-[9px] font-mono text-zinc-600 mt-0.5 block">
                          p. {cit.page}
                          {cit.section ? ` · ${cit.section}` : ""}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Excerpt */}
                  <blockquote className="border-l border-indigo-500/40 pl-3 ml-[calc(1rem+10px)]">
                    <p className="text-[11px] text-zinc-500 leading-relaxed line-clamp-3 italic group-hover:text-zinc-400 transition-colors">
                      {cit.extractedText}
                    </p>
                  </blockquote>

                  <RelevanceBar score={cit.relevanceScore} />
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/** Edge / error state banner used for non-SUCCESS statuses. */
function StatusBanner({
  status,
  content,
}: {
  status: Exclude<AnswerStatus, "SUCCESS">;
  content: string;
}) {
  const map: Record<
    string,
    { label: string; colour: string; bg: string; border: string }
  > = {
    INSUFFICIENT_EVIDENCE: {
      label: "Insufficient Evidence",
      colour: "text-indigo-400",
      bg: "bg-indigo-500/5",
      border: "border-indigo-500/20",
    },
    NO_RESULTS: {
      label: "No Results",
      colour: "text-zinc-400",
      bg: "bg-zinc-500/5",
      border: "border-zinc-500/20",
    },
    CONFLICT: {
      label: "Evidence Conflict",
      colour: "text-amber-400",
      bg: "bg-amber-500/5",
      border: "border-amber-500/20",
    },
    ERROR: {
      label: "Engine Error",
      colour: "text-red-400",
      bg: "bg-red-500/5",
      border: "border-red-500/20",
    },
    ACCESS_RESTRICTED: {
      label: "Clearance Restricted",
      colour: "text-amber-400",
      bg: "bg-amber-500/5",
      border: "border-amber-500/20",
    },
  };

  const theme = map[status] ?? map.ERROR;

  return (
    <div
      className={`flex items-start gap-3 border ${theme.border} ${theme.bg} p-4 rounded-sm`}
    >
      <WarningCircle
        size={15}
        weight="bold"
        className={`${theme.colour} flex-shrink-0 mt-0.5`}
      />
      <div>
        <p
          className={`text-[10px] font-mono uppercase tracking-[0.2em] ${theme.colour} mb-1`}
        >
          {theme.label}
        </p>
        <p className="text-sm text-zinc-300 leading-relaxed">{content}</p>
      </div>
    </div>
  );
}

// ─── Main export ─────────────────────────────────────────────────────────────

interface ChatMessageProps {
  message: ChatMsg;
  /** Accumulated token string; only used when message.isStreaming === true. */
  streamingText?: string;
  /** Called when the user clicks a citation badge or source item. */
  onCitationClick?: (citation: Citation) => void;
}

export function ChatMessage({
  message,
  streamingText = "",
  onCitationClick,
}: ChatMessageProps) {
  const { role, content, isStreaming, citations, status } = message;

  // ── User bubble ──────────────────────────────────────────────────────────
  if (role === "user") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25, ease: [0.32, 0.72, 0, 1] }}
        className="flex justify-end"
      >
        <div className="max-w-[78%] bg-white/5 border border-white/10 px-5 py-3.5 rounded-sm shadow-sm">
          <p className="text-sm text-zinc-200 leading-relaxed whitespace-pre-wrap">
            {content}
          </p>
        </div>
      </motion.div>
    );
  }

  // ── Assistant — streaming skeleton ──────────────────────────────────────
  if (isStreaming) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25, ease: [0.32, 0.72, 0, 1] }}
        className="flex flex-col gap-1"
      >
        {/* label */}
        <div className="flex items-center gap-2 mb-3">
          <span className="h-1.5 w-1.5 bg-indigo-500 animate-pulse flex-shrink-0" />
          <span className="text-[10px] font-mono uppercase tracking-[0.22em] text-zinc-500">
            NEX · Composing
          </span>
        </div>

        {/* live text */}
        <p className="text-[15px] text-zinc-200 leading-[1.75] whitespace-pre-wrap">
          {streamingText || (
            <span className="text-zinc-600 italic text-sm">Retrieving evidence…</span>
          )}
          <StreamCursor />
        </p>

        {/* Display citations as soon as the evidence event arrives */}
        {citations && citations.length > 0 && (
          <SourcesAccordion
            citations={citations}
            onCitationClick={onCitationClick}
          />
        )}
      </motion.div>
    );
  }

  // ── Assistant — complete, non-SUCCESS ────────────────────────────────────
  if (status && status !== "SUCCESS") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: [0.32, 0.72, 0, 1] }}
      >
        <div className="flex items-center gap-2 mb-4">
          <span className="h-1.5 w-1.5 bg-zinc-700 flex-shrink-0" />
          <span className="text-[10px] font-mono uppercase tracking-[0.22em] text-zinc-600">
            NEX Response
          </span>
        </div>
        <StatusBanner
          status={status as Exclude<AnswerStatus, "SUCCESS">}
          content={content}
        />
      </motion.div>
    );
  }

  // ── Assistant — complete, SUCCESS ────────────────────────────────────────
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.32, 0.72, 0, 1] }}
    >
      {/* Response header */}
      <div className="flex items-center gap-2.5 border-b border-white/5 pb-3 mb-4">
        <span className="h-1.5 w-1.5 bg-indigo-500 flex-shrink-0" />
        <span className="text-[10px] font-mono uppercase tracking-[0.22em] text-zinc-500">
          NEX Verified Response
        </span>
        {citations && citations.length > 0 && (
          <span className="ml-auto text-[9px] font-mono text-zinc-600">
            {citations.length} source{citations.length !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Answer body */}
      <p className="text-[15px] text-zinc-200 leading-[1.75] whitespace-pre-wrap mb-2">
        {content}
      </p>

      {/* Sources accordion */}
      {citations && citations.length > 0 && (
        <SourcesAccordion
          citations={citations}
          onCitationClick={onCitationClick}
        />
      )}
    </motion.div>
  );
}