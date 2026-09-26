"use client";

import * as React from "react";
import { Navbar } from "@/components/ui/navbar";
import { ArrowLeft, Textbox, MagnifyingGlassPlus, MagnifyingGlassMinus, FileText } from "@phosphor-icons/react";
import Link from "next/link";
import { useSearchParams, useParams } from "next/navigation";
import { evidenceService } from "@/services/evidenceService";
import { EvidenceContext } from "@/services/types";
import { EvidenceScene } from "@/components/immersive/EvidenceScene";

class WebGLErrorBoundary extends React.Component<{ children: React.ReactNode, fallback: React.ReactNode }, { hasError: boolean }> {
  constructor(props: { children: React.ReactNode, fallback: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError() { return { hasError: true }; }
  render() { return this.state.hasError ? this.props.fallback : this.props.children; }
}

function EvidenceContent({ documentId }: { documentId: string }) {
  const searchParams = useSearchParams();
  const citationId = searchParams.get("citation") || undefined;
  const citedText = searchParams.get("text") ? decodeURIComponent(searchParams.get("text")!) : undefined;
  const pageParam = searchParams.get("page") || undefined;
  
  const [ctx, setCtx] = React.useState<EvidenceContext | null>(null);
  const [loadError, setLoadError] = React.useState<string | null>(null);
  const anchorRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    setCtx(null);
    setLoadError(null);
    evidenceService
      .getEvidenceContext(documentId, citationId, citedText, pageParam)
      .then(setCtx)
      .catch((err) => {
        console.error("Evidence load failed:", err);
        setLoadError("Failed to load document metadata. Is the backend running?");
      });
  }, [documentId, citationId, citedText, pageParam]);

  return (
    <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 w-full h-full border-t border-white/5">
      <div className="hidden lg:flex flex-col col-span-3 h-full border-r border-white/5 bg-[#050505]">
        <div className="p-5 border-b border-white/5 flex items-center justify-between">
          <Link href="/search" className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-zinc-500 hover:text-zinc-300 transition-colors">
            <ArrowLeft size={14} />
            Return to Answer
          </Link>
        </div>
        
        <div className="flex-1 overflow-y-auto p-6 space-y-10">
          {loadError ? (
            <div className="text-xs font-mono text-red-400">{loadError}</div>
          ) : !ctx ? (
            <div className="animate-pulse space-y-6">
              <div className="h-2 bg-white/10 w-24 mb-4" />
              <div className="h-4 bg-white/10 w-full" />
              <div className="h-2 bg-white/10 w-16" />
            </div>
          ) : (
            <>
              <div>
                <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest mb-4 block">Source Document</span>
                <div className="flex items-start gap-3">
                  <FileText size={20} className="text-zinc-600 shrink-0 mt-0.5" />
                  <div>
                    <h3 className="text-sm font-medium text-zinc-300 leading-tight">{ctx.documentTitle}</h3>
                    <div className="flex gap-2 text-[10px] font-mono text-zinc-500 uppercase tracking-widest mt-2">
                      {ctx.page && <span>Pg {ctx.page}</span>}
                      {ctx.citationId && <span>• {ctx.citationId.slice(0, 12)}…</span>}
                    </div>
                  </div>
                </div>
              </div>

              {ctx.section && (
                <div>
                  <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest mb-2 block">Section</span>
                  <p className="text-sm text-zinc-400 font-mono">{ctx.section}</p>
                </div>
              )}

              <div>
                <span className="text-[10px] font-mono text-indigo-400 uppercase tracking-[0.2em] mb-4 block">Extracted Evidence Match</span>
                <div className="relative border-l-2 border-indigo-500 pl-4 py-1" ref={anchorRef}>
                  <p className="text-sm text-zinc-400 leading-relaxed font-serif italic">
                    &ldquo;{ctx.extractedText}&rdquo;
                    <div className="absolute -right-6 top-1/2 -translate-y-1/2 w-6 h-[1px] bg-indigo-500 hidden lg:block" />
                  </p>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      <div className="col-span-1 lg:col-span-9 flex flex-col h-full bg-[#0A0A0A] relative">
        <div className="absolute inset-0 z-0 hidden lg:flex items-center justify-center pointer-events-none">
          {ctx && (
            <WebGLErrorBoundary 
              fallback={
                <svg width="100%" height="100%" viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 z-0 opacity-50">
                  <path d="M 0,50 C 50,50 50,50 100,50" stroke="#6366f1" strokeWidth="0.2" fill="none" className="animate-in fade-in duration-1000" />
                </svg>
              }
            >
              <EvidenceScene anchorRef={anchorRef} isActive={!!ctx} reducedMotion={false} />
            </WebGLErrorBoundary>
          )}
        </div>

        <div className="lg:hidden p-4 border-b border-white/5 bg-[#050505] flex items-center">
          <Link href="/search" className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-zinc-400 hover:text-zinc-200 transition-colors">
            <ArrowLeft size={16} />
            Return to Answer
          </Link>
        </div>

        <div className="flex items-center justify-between p-3 px-5 border-b border-white/5 bg-[#050505]">
          <div className="flex items-center gap-3">
            <Textbox size={16} className="text-zinc-500" />
            <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-400">Document Preview</span>
            {ctx && (
              <span className="text-[10px] font-mono text-zinc-600 ml-3 truncate max-w-[200px]">{ctx.documentTitle}</span>
            )}
          </div>
          <div className="flex items-center gap-1 bg-[#0A0A0A] border border-white/5 rounded">
            <button disabled className="p-1.5 opacity-50 text-zinc-500">
              <MagnifyingGlassMinus size={14} />
            </button>
            <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 w-12 text-center">100%</span>
            <button disabled className="p-1.5 opacity-50 text-zinc-500">
              <MagnifyingGlassPlus size={14} />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-auto p-6 md:p-12 flex justify-center items-start">
          <div className="w-full max-w-[850px] min-h-[1100px] bg-[#111113]/95 backdrop-blur-sm border border-white/5 shadow-[0_0_50px_rgba(0,0,0,0.5)] p-12 md:p-20 relative z-10">
            {loadError ? (
              <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
                <p className="text-sm font-mono text-red-400">{loadError}</p>
                <Link href="/search" className="text-xs font-mono text-zinc-400 hover:text-zinc-200 uppercase tracking-widest border border-white/10 px-4 py-2 transition-colors">
                  ← Back to Search
                </Link>
              </div>
            ) : !ctx ? (
              <div className="animate-pulse space-y-8">
                <div className="h-6 bg-white/5 w-1/3 mb-8" />
                <div className="h-4 bg-white/5 w-full" />
                <div className="h-4 bg-white/5 w-5/6" />
                <div className="h-4 bg-white/5 w-full" />
              </div>
            ) : (
              <div className="my-16">
                {ctx.section && (
                  <h4 className="text-xl font-serif text-zinc-300 mb-6">{ctx.section}</h4>
                )}

                <p className="text-sm text-zinc-400 font-serif leading-loose text-justify">
                  <span className="bg-indigo-500/10 text-zinc-300 px-1 py-0.5 outline outline-1 outline-indigo-500/30 relative">
                    {ctx.extractedText}
                    <span className="absolute -left-3 top-0 bottom-0 w-1 bg-indigo-500" />
                  </span>
                </p>
                
                <div className="border border-dashed border-white/10 p-6 mt-6">
                  <p className="text-sm font-mono text-zinc-500 text-center uppercase tracking-widest">
                    {ctx.surroundingContext}
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function EvidenceViewer() {
  const params = useParams();
  const documentId = params?.documentId as string;
  
  return (
    <main className="min-h-[100dvh] w-full bg-[#050505] flex flex-col text-zinc-50 overflow-hidden">
      <Navbar />
      <div className="flex-1 mt-16 flex flex-col">
        <React.Suspense fallback={<div className="flex-1 bg-[#0A0A0A] border-t border-white/5 p-12">Loading...</div>}>
          {documentId ? <EvidenceContent documentId={documentId} /> : null}
        </React.Suspense>
      </div>
    </main>
  );
}
