"use client";

import * as React from "react";
import { motion, AnimatePresence } from "motion/react";
import { Navbar } from "@/components/ui/navbar";
import { FileText, Image, ArrowRight, X, Warning, CheckCircle, XCircle } from "@phosphor-icons/react";
import Link from "next/link";
import { documentsService, saveSessionDocument, updateSessionDocument } from "@/services/documentsService";
import { DocumentSource } from "@/services/types";
import { useNexusSession } from "@/hooks/useNexusSession";
import { ApiError } from "@/services/apiClient";

// ── Validation constants ───────────────────────────────────────────────────────

const MAX_FILES = 10;
const MAX_DOC_BYTES  = 15 * 1024 * 1024; // 15 MB
const MAX_IMG_BYTES  =  5 * 1024 * 1024; //  5 MB

const ALLOWED_TYPES: Record<string, "doc" | "image"> = {
  "application/pdf": "doc",
  "text/plain": "doc",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "doc",
  "image/png": "image",
  "image/jpeg": "image",
  "image/webp": "image",
};

const ACCEPT_ATTR =
  ".pdf,.txt,.docx,.doc,.png,.jpg,.jpeg,.webp," +
  "application/pdf,text/plain," +
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document," +
  "image/png,image/jpeg,image/webp";

// ── Types ──────────────────────────────────────────────────────────────────────

interface ValidationError {
  filename: string;
  reason: string;
}

type BatchItemState =
  | { phase: "uploading" }
  | { phase: "polling"; doc: DocumentSource }
  | { phase: "done";    doc: DocumentSource }
  | { phase: "error";   message: string };

interface BatchItem {
  file: File;
  state: BatchItemState;
}

// ── Validation helper ─────────────────────────────────────────────────────────

function validateFiles(files: File[]): { valid: File[]; errors: ValidationError[] } {
  const errors: ValidationError[] = [];
  const valid: File[] = [];

  if (files.length > MAX_FILES) {
    return {
      valid: [],
      errors: [{ filename: "", reason: `Maximum ${MAX_FILES} files per batch. You selected ${files.length}.` }],
    };
  }

  for (const file of files) {
    const kind = ALLOWED_TYPES[file.type];

    if (!kind) {
      errors.push({
        filename: file.name,
        reason: `Unsupported type "${file.type || "unknown"}". Allowed: PDF, TXT, DOCX, PNG, JPEG, WEBP.`,
      });
      continue;
    }

    const limit = kind === "image" ? MAX_IMG_BYTES : MAX_DOC_BYTES;
    const limitLabel = kind === "image" ? "5 MB" : "15 MB";
    if (file.size > limit) {
      errors.push({
        filename: file.name,
        reason: `Exceeds ${limitLabel} limit (${(file.size / 1024 / 1024).toFixed(1)} MB).`,
      });
      continue;
    }

    valid.push(file);
  }

  return { valid, errors };
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function UploadPage() {
  const { workspace, isReady, error: sessionError } = useNexusSession();

  // Per-file batch items — keyed by array index which is stable per batch
  const [batch, setBatch] = React.useState<BatchItem[]>([]);
  const [validationErrors, setValidationErrors] = React.useState<ValidationError[]>([]);
  const [batchError, setBatchError] = React.useState<string | null>(null);

  const hasBatch = batch.length > 0;

  // Derived: is every item settled (done or error)?
  const allSettled = hasBatch && batch.every(
    (item) => item.state.phase === "done" || item.state.phase === "error",
  );
  const anyReady = batch.some(
    (item) => item.state.phase === "done" && item.state.doc.status === "READY",
  );

  // ── Polling effect — runs for every item in "polling" phase ────────────────
  React.useEffect(() => {
    if (!hasBatch) return;

    const pollingItems = batch
      .map((item, idx) => ({ item, idx }))
      .filter(({ item }) => item.state.phase === "polling");

    if (pollingItems.length === 0) return;

    const interval = setInterval(async () => {
      await Promise.allSettled(
        pollingItems.map(async ({ item, idx }) => {
          if (item.state.phase !== "polling") return;
          try {
            const updated = await documentsService.getDocumentStatus(
              item.state.doc.id,
              item.state.doc,
            );
            updateSessionDocument(updated);

            setBatch((prev) => {
              const next = [...prev];
              if (updated.status === "READY" || updated.status === "FAILED") {
                next[idx] = { ...next[idx], state: { phase: "done", doc: updated } };
              } else {
                next[idx] = { ...next[idx], state: { phase: "polling", doc: updated } };
              }
              return next;
            });
          } catch (e) {
            const msg =
              e instanceof ApiError && e.status === 401
                ? "Authentication expired."
                : "Status poll failed.";
            setBatch((prev) => {
              const next = [...prev];
              next[idx] = { ...next[idx], state: { phase: "error", message: msg } };
              return next;
            });
          }
        }),
      );
    }, 1500);

    return () => clearInterval(interval);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batch]);

  // ── Upload handler ─────────────────────────────────────────────────────────
  const startBatch = async (files: File[]) => {
    setValidationErrors([]);
    setBatchError(null);

    if (!workspace) {
      setBatchError("No workspace available. Ensure you are authenticated.");
      return;
    }
    if (workspace.role === "viewer") {
      setBatchError("Viewer role cannot upload documents.");
      return;
    }

    const { valid, errors } = validateFiles(files);
    setValidationErrors(errors);
    if (valid.length === 0) return;

    // Initialise batch state — one item per valid file, all "uploading"
    const initialBatch: BatchItem[] = valid.map((file) => ({
      file,
      state: { phase: "uploading" },
    }));
    setBatch(initialBatch);

    // Fire all uploads concurrently; each updates its own slot on settle
    await Promise.allSettled(
      valid.map(async (file, idx) => {
        try {
          const doc = await documentsService.uploadDocument(file, workspace.id);
          saveSessionDocument(doc);
          setBatch((prev) => {
            const next = [...prev];
            next[idx] = { ...next[idx], state: { phase: "polling", doc } };
            return next;
          });
        } catch (e) {
          let msg = "Upload failed. Is the backend running?";
          if (e instanceof ApiError) {
            if (e.status === 401) msg = "Authentication required.";
            else if (e.status === 403) msg = "Permission denied for this workspace.";
            else msg = `Upload failed: ${e.message}`;
          }
          setBatch((prev) => {
            const next = [...prev];
            next[idx] = { ...next[idx], state: { phase: "error", message: msg } };
            return next;
          });
        }
      }),
    );
  };

  // ── Drag-and-drop ──────────────────────────────────────────────────────────
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files?.length) {
      startBatch(Array.from(e.dataTransfer.files));
    }
  };
  const handleDragOver = (e: React.DragEvent) => e.preventDefault();

  const reset = () => {
    setBatch([]);
    setValidationErrors([]);
    setBatchError(null);
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <main className="relative min-h-[100dvh] w-full bg-[#050505]">
      <Navbar />

      <div className="relative z-10 mx-auto max-w-[900px] px-4 md:px-6 pt-32 md:pt-40 pb-24">

        {/* ── Header ── */}
        <div className="mb-8 md:mb-12 border-b border-white/10 pb-6 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-medium tracking-tight text-zinc-50">Knowledge Ingestion</h1>
            <p className="mt-2 text-xs md:text-sm text-zinc-500 font-mono uppercase tracking-[0.1em]">
              {workspace ? `Workspace: ${workspace.name}` : "Target: Core Index"}
            </p>
          </div>
          {allSettled && anyReady && (
            <Link
              href="/search"
              className="group relative inline-flex h-12 items-center justify-center gap-3 overflow-hidden bg-white text-zinc-950 px-8 text-sm font-medium transition-all hover:bg-zinc-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-white/20 active:scale-[0.98] w-full sm:w-auto"
            >
              <span>Enter Workspace</span>
              <span className="transition-transform duration-300 group-hover:translate-x-1">
                <ArrowRight weight="bold" />
              </span>
            </Link>
          )}
        </div>

        {/* ── Session error ── */}
        {sessionError && (
          <div className="mb-6 flex items-start gap-3 border border-red-500/20 bg-red-500/5 px-4 py-3">
            <Warning size={16} className="text-red-400 mt-0.5 shrink-0" />
            <p className="text-xs text-red-300 font-mono">{sessionError}</p>
          </div>
        )}

        {/* ── Workspace role badge ── */}
        {workspace && (
          <div className="mb-6 flex items-center gap-2">
            <span className={`text-[9px] font-mono uppercase tracking-widest px-2 py-0.5 border ${
              workspace.role === "admin" || workspace.role === "contributor"
                ? "border-indigo-500/30 text-indigo-400"
                : "border-zinc-700 text-zinc-500"
            }`}>
              {workspace.role}
            </span>
            {workspace.role === "viewer" && (
              <span className="text-[9px] font-mono text-zinc-600 uppercase tracking-widest">
                — viewer role cannot upload documents
              </span>
            )}
          </div>
        )}

        {/* ── Batch-level errors (auth / workspace) ── */}
        {batchError && (
          <div className="mb-6 flex items-start gap-3 border border-red-500/20 bg-red-500/5 px-4 py-3">
            <Warning size={16} className="text-red-400 mt-0.5 shrink-0" />
            <p className="text-xs text-red-300 font-mono">{batchError}</p>
          </div>
        )}

        {/* ── Validation errors (per-file, pre-upload) ── */}
        {validationErrors.length > 0 && (
          <div className="mb-6 border border-amber-500/20 bg-amber-500/5 px-4 py-3 space-y-2">
            <div className="flex items-center gap-2">
              <Warning size={14} className="text-amber-400 shrink-0" />
              <p className="text-[10px] font-mono text-amber-400 uppercase tracking-widest">
                {validationErrors.length} file{validationErrors.length > 1 ? "s" : ""} rejected before upload
              </p>
            </div>
            {validationErrors.map((err, i) => (
              <div key={i} className="pl-5 flex items-baseline gap-2">
                {err.filename && (
                  <span className="text-[10px] font-mono text-zinc-400 shrink-0 truncate max-w-[160px]">{err.filename}</span>
                )}
                <span className="text-[10px] font-mono text-amber-300/80">{err.reason}</span>
              </div>
            ))}
          </div>
        )}

        <AnimatePresence mode="wait">

          {/* ── Dropzone (idle) ── */}
          {!hasBatch && (
            <motion.div
              key="idle"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="relative w-full min-h-[300px] md:aspect-[2/1] bg-[#0A0A0A] border border-white/5 cursor-pointer group flex flex-col items-center justify-center p-6 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 focus-visible:ring-offset-[#050505]"
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onClick={() => document.getElementById("file-upload")?.click()}
              tabIndex={0}
              role="button"
              aria-label="Upload documents — click or drag and drop up to 10 files"
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  document.getElementById("file-upload")?.click();
                }
              }}
            >
              {/* Corner accents */}
              <div className="absolute top-0 left-0 w-4 h-4 border-t border-l border-white/20 transition-colors group-hover:border-indigo-500/50" />
              <div className="absolute top-0 right-0 w-4 h-4 border-t border-r border-white/20 transition-colors group-hover:border-indigo-500/50" />
              <div className="absolute bottom-0 left-0 w-4 h-4 border-b border-l border-white/20 transition-colors group-hover:border-indigo-500/50" />
              <div className="absolute bottom-0 right-0 w-4 h-4 border-b border-r border-white/20 transition-colors group-hover:border-indigo-500/50" />
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[length:24px_24px] opacity-0 group-hover:opacity-100 transition-opacity duration-700" />

              <div className="relative z-10 flex flex-col items-center text-center">
                <div className="flex items-center gap-3 mb-6">
                  <FileText size={28} className="text-zinc-600 group-hover:text-zinc-300 transition-colors" weight="light" />
                  <Image size={28} className="text-zinc-600 group-hover:text-zinc-300 transition-colors" weight="light" />
                </div>
                <span className="text-sm font-mono text-zinc-400 uppercase tracking-widest">Select Source Data</span>
                <span className="text-[10px] font-mono text-zinc-600 mt-3 uppercase tracking-[0.2em]">
                  PDF · TXT · DOCX · PNG · JPEG · WEBP
                </span>
                <span className="text-[9px] font-mono text-zinc-700 mt-2 uppercase tracking-[0.15em]">
                  Up to {MAX_FILES} files &nbsp;·&nbsp; 15 MB per document &nbsp;·&nbsp; 5 MB per image
                </span>
                {!isReady && (
                  <span className="text-[10px] font-mono text-zinc-700 mt-4 uppercase tracking-[0.2em] animate-pulse">
                    Connecting to engine...
                  </span>
                )}
              </div>

              <input
                type="file"
                multiple
                className="hidden"
                id="file-upload"
                accept={ACCEPT_ATTR}
                disabled={!isReady || workspace?.role === "viewer"}
                onChange={(e) => {
                  if (e.target.files?.length) {
                    startBatch(Array.from(e.target.files));
                    // Reset so the same files can be re-selected after a fix
                    e.target.value = "";
                  }
                }}
              />
            </motion.div>
          )}

          {/* ── Batch tracker ── */}
          {hasBatch && (
            <motion.div
              key="processing"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="w-full bg-[#0A0A0A] border border-white/5"
            >
              {/* Batch header */}
              <div className="flex items-center justify-between px-6 md:px-10 py-4 border-b border-white/5">
                <div className="flex items-center gap-3">
                  <div className="h-1.5 w-1.5 bg-indigo-500" />
                  <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-400">
                    {batch.length} file{batch.length > 1 ? "s" : ""} &nbsp;·&nbsp;
                    {batch.filter((i) => i.state.phase === "done" || i.state.phase === "error").length} settled
                  </span>
                </div>
                {allSettled && (
                  <button
                    onClick={reset}
                    className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-zinc-500 hover:text-zinc-200 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
                  >
                    <X size={12} />
                    <span>New Batch</span>
                  </button>
                )}
              </div>

              {/* Per-file rows */}
              <div className="divide-y divide-white/[0.04]">
                {batch.map((item, idx) => (
                  <BatchItemRow key={idx} item={item} />
                ))}
              </div>
            </motion.div>
          )}

        </AnimatePresence>
      </div>
    </main>
  );
}

// ── BatchItemRow ──────────────────────────────────────────────────────────────

function BatchItemRow({ item }: { item: BatchItem }) {
  const { file, state } = item;
  const sizeLabel = `${(file.size / 1024 / 1024).toFixed(2)} MB`;
  const isImage = (ALLOWED_TYPES[file.type] ?? "doc") === "image";

  return (
    <div className="px-6 md:px-10 py-5">
      {/* File identity */}
      <div className="flex items-start gap-4 mb-3">
        <div className="mt-0.5 shrink-0">
          {isImage
            ? <Image size={16} className="text-zinc-600" weight="light" />
            : <FileText size={16} className="text-zinc-600" weight="light" />}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-zinc-200 truncate">{file.name}</p>
          <p className="text-[10px] font-mono text-zinc-600 mt-0.5">{sizeLabel}</p>
        </div>
        <StatusBadge state={state} />
      </div>

      {/* Progress pipeline — only shown while a doc is processing */}
      {(state.phase === "polling" || state.phase === "done") && (() => {
        const doc = state.doc;
        return (
          <div className="ml-8 space-y-0.5">
            {doc.processingProgress != null &&
              state.phase === "polling" &&
              doc.status !== "READY" &&
              doc.status !== "FAILED" && (
                <div className="flex items-center gap-3 mb-2">
                  <div className="flex-1 h-0.5 bg-white/5">
                    <div
                      className="h-full bg-indigo-500 transition-all duration-700"
                      style={{ width: `${doc.processingProgress}%` }}
                    />
                  </div>
                  <span className="text-[9px] font-mono text-zinc-600">{doc.processingProgress}%</span>
                </div>
              )}
            <MiniPipeline status={doc.status} />
          </div>
        );
      })()}

      {/* Error message */}
      {state.phase === "error" && (
        <p className="ml-8 text-[10px] font-mono text-red-400 mt-1">{state.message}</p>
      )}
    </div>
  );
}

function StatusBadge({ state }: { state: BatchItemState }) {
  if (state.phase === "uploading") {
    return (
      <span className="flex items-center gap-1.5 text-[9px] font-mono uppercase tracking-widest text-zinc-500 shrink-0">
        <span className="h-1.5 w-1.5 rounded-full bg-zinc-600 animate-pulse" />
        Uploading
      </span>
    );
  }
  if (state.phase === "polling") {
    return (
      <span className="flex items-center gap-1.5 text-[9px] font-mono uppercase tracking-widest text-indigo-400 shrink-0">
        <span className="h-1.5 w-1.5 rounded-full bg-indigo-500 animate-pulse" />
        Processing
      </span>
    );
  }
  if (state.phase === "done") {
    return state.doc.status === "READY"
      ? <CheckCircle size={16} className="text-emerald-400 shrink-0" weight="fill" />
      : <XCircle size={16} className="text-red-400 shrink-0" weight="fill" />;
  }
  // error
  return <XCircle size={16} className="text-red-400 shrink-0" weight="fill" />;
}

function MiniPipeline({ status }: { status: string }) {
  const stages: { key: string; label: string }[] = [
    { key: "QUEUED",      label: "Init" },
    { key: "DETECTING",   label: "Analyze" },
    { key: "ROUTING",     label: "Route" },
    { key: "EXTRACTING",  label: "Extract" },
    { key: "STRUCTURING", label: "Structure" },
    { key: "INDEXING",    label: "Index" },
  ];

  const order = stages.map((s) => s.key);
  const currentIdx = order.indexOf(status);

  return (
    <div className="flex items-center gap-0">
      {stages.map((stage, i) => {
        const isDone   = status === "READY" || (currentIdx > i);
        const isActive = currentIdx === i;
        const isFailed = status === "FAILED";
        return (
          <React.Fragment key={stage.key}>
            <div className="flex flex-col items-center gap-1">
              <div className={`h-1 w-1 rounded-full transition-colors ${
                isFailed   ? "bg-red-600" :
                isDone     ? "bg-zinc-500" :
                isActive   ? "bg-indigo-500" :
                             "bg-zinc-800"
              }`} />
              <span className={`text-[8px] font-mono uppercase tracking-wider hidden sm:block ${
                isFailed   ? "text-red-700" :
                isDone     ? "text-zinc-600" :
                isActive   ? "text-indigo-400" :
                             "text-zinc-800"
              }`}>{stage.label}</span>
            </div>
            {i < stages.length - 1 && (
              <div className={`h-px w-6 mb-3.5 transition-colors ${
                isDone ? "bg-zinc-700" : "bg-zinc-900"
              }`} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}
