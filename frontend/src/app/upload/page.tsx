"use client";

import * as React from "react";
import { motion, AnimatePresence } from "motion/react";
import { Navbar } from "@/components/ui/navbar";
import { FileText, ArrowRight, X, Warning } from "@phosphor-icons/react";
import Link from "next/link";
import { documentsService, saveSessionDocument, updateSessionDocument } from "@/services/documentsService";
import { ProcessState, DocumentSource } from "@/services/types";
import { useNexusSession } from "@/hooks/useNexusSession";
import { ApiError, setDevUserId } from "@/services/apiClient";

export default function UploadPage() {
  const { workspace, isReady, error: sessionError } = useNexusSession();
  const [doc, setDoc] = React.useState<DocumentSource | null>(null);
  const [isPolling, setIsPolling] = React.useState(false);
  const [uploadError, setUploadError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isPolling && doc?.id) {
      interval = setInterval(async () => {
        try {
          const updatedDoc = await documentsService.getDocumentStatus(doc.id, doc);
          setDoc(updatedDoc);
          updateSessionDocument(updatedDoc);
          if (updatedDoc.status === "READY" || updatedDoc.status === "FAILED") {
            setIsPolling(false);
          }
        } catch (e) {
          console.error("Failed to poll status", e);
          if (e instanceof ApiError && e.status === 401) {
            setUploadError("Authentication required. Please set your user ID.");
          }
          setIsPolling(false);
        }
      }, 1500);
    }
    return () => clearInterval(interval);
  }, [isPolling, doc?.id]);

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      await startUpload(e.dataTransfer.files[0]);
    }
  };

  const startUpload = async (file: File) => {
    setUploadError(null);
    if (!workspace) {
      setUploadError("No workspace available. Ensure you are authenticated.");
      return;
    }

    try {
      const newDoc = await documentsService.uploadDocument(file, workspace.id);
      setDoc(newDoc);
      saveSessionDocument(newDoc);
      setIsPolling(true);
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.status === 401) {
          setUploadError("Authentication required. Please configure your user ID.");
        } else if (e.status === 403) {
          setUploadError("You do not have permission to upload to this workspace.");
        } else {
          setUploadError(`Upload failed: ${e.message}`);
        }
      } else {
        setUploadError("Upload failed. Is the backend running?");
      }
    }
  };

  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); };

  return (
    <main className="relative min-h-[100dvh] w-full bg-[#050505]">
      <Navbar />
      
      <div className="relative z-10 mx-auto max-w-[900px] px-4 md:px-6 pt-32 md:pt-40 pb-24">
        
        <div className="mb-8 md:mb-12 border-b border-white/10 pb-6 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-medium tracking-tight text-zinc-50">Knowledge Ingestion</h1>
            <p className="mt-2 text-xs md:text-sm text-zinc-500 font-mono uppercase tracking-[0.1em]">
              {workspace ? `Workspace: ${workspace.name}` : "Target: Core Index"}
            </p>
          </div>
          {doc?.status === "READY" && (
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

        {(sessionError || uploadError) && (
          <div className="mb-6 flex items-start gap-3 border border-red-500/20 bg-red-500/5 px-4 py-3">
            <Warning size={16} className="text-red-400 mt-0.5 shrink-0" />
            <p className="text-xs text-red-300 font-mono">{sessionError ?? uploadError}</p>
          </div>
        )}

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

        <AnimatePresence mode="wait">
          {!doc && (
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
              role="button" aria-label="Upload document - click or drag and drop a file" onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  document.getElementById("file-upload")?.click();
                }
              }}
            >
              <div className="absolute top-0 left-0 w-4 h-4 border-t border-l border-white/20 transition-colors group-hover:border-indigo-500/50" />
              <div className="absolute top-0 right-0 w-4 h-4 border-t border-r border-white/20 transition-colors group-hover:border-indigo-500/50" />
              <div className="absolute bottom-0 left-0 w-4 h-4 border-b border-l border-white/20 transition-colors group-hover:border-indigo-500/50" />
              <div className="absolute bottom-0 right-0 w-4 h-4 border-b border-r border-white/20 transition-colors group-hover:border-indigo-500/50" />
              
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[length:24px_24px] opacity-0 group-hover:opacity-100 transition-opacity duration-700" />
              
              <div className="relative z-10 flex flex-col items-center text-center">
                <FileText size={32} className="text-zinc-600 group-hover:text-zinc-300 transition-colors mb-6" weight="light" />
                <span className="text-sm font-mono text-zinc-400 uppercase tracking-widest">Select Source Data</span>
                <span className="text-[10px] font-mono text-zinc-600 mt-4 uppercase tracking-[0.2em]">PDF, TXT, DOCX</span>
                {!isReady && (
                  <span className="text-[10px] font-mono text-zinc-700 mt-3 uppercase tracking-[0.2em] animate-pulse">Connecting to engine...</span>
                )}
              </div>
              
              <input
                type="file"
                className="hidden"
                id="file-upload"
                accept=".pdf,.txt,.docx,.doc"
                disabled={!isReady || workspace?.role === "viewer"}
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    startUpload(e.target.files[0]);
                  }
                }} 
              />
            </motion.div>
          )}

          {doc && (
            <motion.div
              key="processing"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="w-full bg-[#0A0A0A] border border-white/5 p-6 md:p-12"
            >
              <div className="flex items-start justify-between mb-10 md:mb-16 border-b border-white/5 pb-6 md:pb-8">
                <div className="min-w-0 flex-1 pr-4">
                  <div className="text-[10px] font-mono text-indigo-400 uppercase tracking-widest mb-2">
                    Source: {doc.id.slice(0, 13)}…
                  </div>
                  <h3 className="text-lg md:text-xl font-medium text-zinc-50 truncate">{doc.filename}</h3>
                  <p className="text-xs font-mono text-zinc-500 mt-2">{(doc.sizeBytes / 1024 / 1024).toFixed(2)} MB</p>
                  {doc.processingProgress != null && doc.status !== "READY" && doc.status !== "FAILED" && (
                    <div className="mt-3 flex items-center gap-3">
                      <div className="flex-1 h-0.5 bg-white/5">
                        <div
                          className="h-full bg-indigo-500 transition-all duration-700"
                          style={{ width: `${doc.processingProgress}%` }}
                        />
                      </div>
                      <span className="text-[10px] font-mono text-zinc-500">{doc.processingProgress}%</span>
                    </div>
                  )}
                </div>
                {(doc.status === "READY" || doc.status === "FAILED") && (
                  <button
                    onClick={() => { setDoc(null); setIsPolling(false); setUploadError(null); }}
                    className="p-2 text-zinc-500 hover:text-zinc-300 transition-colors shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0A0A0A]"
                  >
                    <X size={20} />
                  </button>
                )}
              </div>

              {doc.status === "FAILED" && (
                <div className="mb-8 flex items-start gap-3 border border-red-500/20 bg-red-500/5 px-4 py-3">
                  <Warning size={16} className="text-red-400 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-xs font-mono text-red-400 uppercase tracking-widest mb-1">Processing Failed</p>
                    <p className="text-xs text-zinc-400">Unable to process this document. Try a different format or re-upload.</p>
                  </div>
                </div>
              )}

              <div className="space-y-1">
                <ProcessRow label="INITIALIZE" fullLabel="INITIALIZING INGESTION" status={doc.status === "QUEUED" ? "ACTIVE" : doc.status !== "FAILED" ? "DONE" : "PENDING"} />
                <ProcessRow label="ANALYZE" fullLabel="ANALYZING LAYOUT" status={doc.status === "DETECTING" ? "ACTIVE" : ["ROUTING", "EXTRACTING", "STRUCTURING", "INDEXING", "READY"].includes(doc.status) ? "DONE" : "PENDING"} />
                <ProcessRow label="QUEUE" fullLabel="ROUTING & QUEUING" status={doc.status === "ROUTING" ? "ACTIVE" : ["EXTRACTING", "STRUCTURING", "INDEXING", "READY"].includes(doc.status) ? "DONE" : "PENDING"} />
                <ProcessRow label="EXTRACT" fullLabel="EXTRACTING ENTITIES" status={doc.status === "EXTRACTING" ? "ACTIVE" : ["STRUCTURING", "INDEXING", "READY"].includes(doc.status) ? "DONE" : "PENDING"} />
                <ProcessRow label="STRUCTURE" fullLabel="STRUCTURING KNOWLEDGE" status={doc.status === "STRUCTURING" ? "ACTIVE" : ["INDEXING", "READY"].includes(doc.status) ? "DONE" : "PENDING"} />
                <ProcessRow label="INDEX" fullLabel="COMMITTING TO INDEX" status={doc.status === "INDEXING" ? "ACTIVE" : doc.status === "READY" ? "DONE" : "PENDING"} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </main>
  );
}

function ProcessRow({ label, fullLabel, status }: { label: string; fullLabel: string; status: "PENDING" | "ACTIVE" | "DONE" }) {
  return (
    <div className={`grid grid-cols-[auto_1fr_auto] items-center gap-3 md:gap-6 py-4 border-b border-white/5 font-mono text-[10px] md:text-xs uppercase tracking-widest transition-colors duration-500 ${status === 'ACTIVE' ? 'text-zinc-50' : status === 'DONE' ? 'text-zinc-500' : 'text-zinc-800'}`}>
      <div className="w-4 flex justify-center shrink-0">
        {status === 'ACTIVE' && <div className="h-1.5 w-1.5 rounded-full bg-indigo-500 animate-pulse" />}
        {status === 'DONE' && <div className="h-1.5 w-1.5 bg-zinc-600 rotate-45" />}
        {status === 'PENDING' && <div className="h-1.5 w-1.5 border border-zinc-800" />}
      </div>
      <div className="truncate">
        <span className="md:hidden">{label}</span>
        <span className="hidden md:inline">{fullLabel}</span>
      </div>
      <div className={`text-[9px] md:text-[10px] shrink-0 ${status === 'ACTIVE' ? 'text-indigo-400' : ''}`}>
        {status === 'ACTIVE' ? 'PROCESSING' : status}
      </div>
    </div>
  );
}
