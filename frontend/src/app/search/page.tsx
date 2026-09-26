"use client";

import * as React from "react";
import { motion, AnimatePresence } from "motion/react";
import { Navbar } from "@/components/ui/navbar";
import { ArrowRight, MagnifyingGlass, FileText, Quotes, WarningCircle, Textbox } from "@phosphor-icons/react";
import { searchService } from "@/services/searchService";
import { documentsService } from "@/services/documentsService";
import { useNexusSession } from "@/hooks/useNexusSession";
import { Conversation, Message, Citation, DocumentSource } from "@/services/types";
import Link from "next/link";
import { useRouter } from "next/navigation";

export default function SearchPage() {
  const router = useRouter();
  const { workspace, isReady } = useNexusSession();

  const [query, setQuery] = React.useState("");
  const [conv, setConv] = React.useState<Conversation | null>(null);
  const [isSearching, setIsSearching] = React.useState(false);
  const [streamingContent, setStreamingContent] = React.useState<string>("");
  const [sources, setSources] = React.useState<DocumentSource[]>([]);
  const [activeCitation, setActiveCitation] = React.useState<{
    id: string;
    documentId: string;
    doc: string;
    page: string;
    text: string;
    section?: string;
  } | null>(null);

  const endOfMessagesRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!isReady || !workspace) return;

    searchService
      .createConversation(workspace.id)
      .then(setConv)
      .catch((err) => {
        console.error("Failed to create conversation:", err);
        setConv({ id: "", messages: [] });
      });

    documentsService.getAllDocuments(workspace.id).then(setSources);
  }, [isReady, workspace]);

  React.useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conv?.messages, isSearching]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isSearching || !conv) return;

    const conversationId = conv.id;
    if (!conversationId) {
      console.warn("No conversation ID — backend may not be running.");
      return;
    }

    const currentQuery = query;
    setQuery("");
    setIsSearching(true);
    setStreamingContent("");

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: currentQuery,
    };
    setConv((prev) => prev ? { ...prev, messages: [...prev.messages, userMsg] } : prev);

    const streamingId = (Date.now() + 1).toString();
    const streamingMsg: Message = {
      id: streamingId,
      role: "nexus",
      content: "",
      isStreaming: true,
    };
    setConv((prev) => prev ? { ...prev, messages: [...prev.messages, streamingMsg] } : prev);

    let evidenceCitations: Citation[] = [];

    try {
      const result = await searchService.streamQuestion(
        conversationId,
        currentQuery,
        {
          onEvidence: (ev) => {
            evidenceCitations = ev.chunks.map((c) => ({
              id: c.chunk_id,
              documentId: c.document_id,
              documentTitle: c.document_name,
              extractedText: c.text,
              relevanceScore: c.score,
            }));
          },
          onToken: (ev) => {
            setStreamingContent((prev) => prev + ev.text);
          },
        },
      );

      const finalMsg: Message = {
        id: streamingId,
        role: "nexus",
        content: result.content || streamingContent,
        status: result.citations.length > 0 ? "SUCCESS" : "INSUFFICIENT_EVIDENCE",
        citations: result.citations.length > 0 ? result.citations : evidenceCitations.length > 0 ? evidenceCitations : undefined,
        isStreaming: false,
      };

      setConv((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          messages: prev.messages.map((m) =>
            m.id === streamingId ? finalMsg : m,
          ),
        };
      });
    } catch (err) {
      console.error("Search error:", err);

      const errorMsg: Message = {
        id: streamingId,
        role: "nexus",
        content: "An error occurred while querying the engine. Is the backend running?",
        status: "ERROR",
        isStreaming: false,
      };

      setConv((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          messages: prev.messages.map((m) =>
            m.id === streamingId ? errorMsg : m,
          ),
        };
      });
    } finally {
      setIsSearching(false);
      setStreamingContent("");
    }
  };

  const handleCitationClick = (citation: Citation) => {
    if (window.innerWidth < 1024) {
      router.push(
        `/evidence/${citation.documentId}?citation=${citation.id}&text=${encodeURIComponent(citation.extractedText)}&page=${citation.page ?? ""}`,
      );
    } else {
      setActiveCitation({
        id: citation.id,
        documentId: citation.documentId,
        doc: citation.documentTitle,
        page: citation.page || "",
        text: citation.extractedText,
        section: citation.section,
      });
    }
  };

  const renderMessageContent = (msg: Message) => {
    if (msg.role === "user") {
      return (
        <div className="flex justify-end mb-8">
          <div className="max-w-[80%] bg-white/5 border border-white/10 px-6 py-4">
            <p className="text-zinc-300 text-sm">{msg.content}</p>
          </div>
        </div>
      );
    }

    if (msg.isStreaming) {
      return (
        <div className="mb-12">
          <div className="flex items-center gap-3 border-b border-white/10 pb-4 mb-6">
            <div className="h-1.5 w-1.5 bg-indigo-500 animate-pulse" />
            <span className="text-xs font-mono uppercase tracking-[0.2em] text-zinc-500">NEX · Composing Answer</span>
          </div>
          <p className="text-zinc-300 text-lg leading-relaxed mb-6 whitespace-pre-wrap">
            {streamingContent}
            <span className="inline-block w-0.5 h-4 bg-indigo-400 ml-0.5 animate-pulse align-middle" />
          </p>
        </div>
      );
    }

    if (msg.status === "ERROR") {
      return <EdgeState title="Engine Error" desc={msg.content} color="text-red-400" bg="bg-red-500/5" border="border-red-500/20" />;
    }
    if (msg.status === "ACCESS_RESTRICTED") {
      return <EdgeState title="Clearance Restricted" desc={msg.content} color="text-amber-400" bg="bg-amber-500/5" border="border-amber-500/20" />;
    }
    if (msg.status === "INSUFFICIENT_EVIDENCE") {
      return <EdgeState title="Insufficient Evidence" desc={msg.content || "NEX couldn't find supporting information in the documents available to you."} color="text-indigo-400" bg="bg-indigo-500/5" border="border-indigo-500/20" />;
    }
    if (msg.status === "NO_RESULTS") {
      return <EdgeState title="No Results" desc={msg.content || "No relevant evidence was found across the indexed workspace."} color="text-zinc-400" bg="bg-zinc-500/5" border="border-zinc-500/20" />;
    }
    if (msg.status === "CONFLICT") {
      return (
        <div className="mb-12">
          <EdgeState title="Evidence Conflict Detected" desc={msg.content} color="text-amber-400" bg="bg-amber-500/5" border="border-amber-500/20" />
          {msg.conflictingSources && msg.conflictingSources.length > 0 && (
            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
              {msg.conflictingSources.map((c, i) => (
                <div key={i} className="border border-amber-500/20 bg-amber-500/5 p-4">
                  <div className="flex justify-between items-center mb-3">
                    <span className="text-[10px] font-mono uppercase text-amber-500/70 border border-amber-500/20 px-1.5 py-0.5">Source A</span>
                    <span className="text-[10px] font-mono text-zinc-500">{c.sourceA}</span>
                  </div>
                  <div className="flex justify-between items-center mb-4">
                    <span className="text-[10px] font-mono uppercase text-amber-500/70 border border-amber-500/20 px-1.5 py-0.5">Source B</span>
                    <span className="text-[10px] font-mono text-zinc-500">{c.sourceB}</span>
                  </div>
                  <p className="text-xs text-amber-100/70">{c.detail}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }

    return (
      <div className="mb-12">
        <div className="flex items-center gap-3 border-b border-white/10 pb-4 mb-6">
          <div className="h-1.5 w-1.5 bg-indigo-500" />
          <span className="text-xs font-mono uppercase tracking-[0.2em] text-zinc-500">NEXUS Verified Response</span>
          {msg.citations && msg.citations.length > 0 && (
            <span className="ml-auto text-[10px] font-mono text-zinc-600">
              {msg.citations.length} source{msg.citations.length > 1 ? "s" : ""}
            </span>
          )}
        </div>
        
        <p className="text-zinc-300 text-lg leading-relaxed mb-6 whitespace-pre-wrap">
          {msg.content}
        </p>
        
        {msg.citations && msg.citations.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {msg.citations.map((cit) => (
              <button 
                key={cit.id} 
                onClick={() => handleCitationClick(cit)}
                className="px-3 py-1.5 bg-white/5 border border-white/10 text-zinc-400 text-xs font-mono hover:bg-indigo-500/10 hover:border-indigo-500/30 hover:text-indigo-300 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0A0A0A]"
              >
                [{cit.page ? `p.${cit.page}` : "ref"}] {cit.documentTitle}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <main className="min-h-[100dvh] w-full bg-[#050505] flex flex-col text-zinc-50 overflow-hidden">
      <Navbar />

      <div className="flex-1 mt-16 grid grid-cols-1 lg:grid-cols-12 w-full h-[calc(100dvh-64px)] border-t border-white/5">
        
        {/* LEFT COLUMN: Source Rail */}
        <div className="hidden lg:flex flex-col col-span-3 h-full border-r border-white/5 bg-[#050505]">
          <div className="p-5 border-b border-white/5 flex items-center justify-between">
            <h2 className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-500">Source Rail</h2>
            <span className="text-[10px] font-mono text-zinc-600">{sources.length} Indexed</span>
          </div>
          
          <div className="flex-1 overflow-y-auto">
            {sources.length === 0 ? (
              <div className="p-8 text-center flex flex-col items-center">
                <FileText size={24} className="text-zinc-700 mb-4" />
                <p className="text-xs text-zinc-500 mb-6">No documents indexed in this workspace.</p>
                <Link href="/upload" className="text-[10px] font-mono uppercase tracking-widest text-indigo-400 hover:text-indigo-300 transition-colors border border-indigo-500/30 px-4 py-2 hover:bg-indigo-500/10">
                  Ingest Sources
                </Link>
              </div>
            ) : (
              <div className="divide-y divide-white/5">
                {sources.map((doc) => (
                  <div key={doc.id} className="group p-5 bg-[#050505] hover:bg-white/[0.02] transition-colors cursor-pointer">
                    <div className="flex items-start gap-3">
                      <FileText size={16} className="text-zinc-600 group-hover:text-indigo-400 mt-0.5 shrink-0 transition-colors" />
                      <div>
                        <p className="text-xs font-mono text-zinc-600 mb-1">{doc.status}</p>
                        <p className="text-sm font-medium text-zinc-300 group-hover:text-zinc-50 transition-colors line-clamp-2">
                          {doc.filename}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* CENTER COLUMN: Answer Canvas */}
        <div className="col-span-1 lg:col-span-6 flex flex-col h-full bg-[#0A0A0A] relative">
          
          <div className="flex-1 overflow-y-auto p-6 md:p-12 lg:p-20 flex flex-col pb-40">
            <AnimatePresence mode="wait">
              {(!conv || conv.messages.length === 0) && !isSearching && (
                <motion.div 
                  key="idle"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="m-auto text-center max-w-md w-full"
                >
                  <h3 className="text-2xl font-medium text-zinc-300 mb-4">Interrogate your documents.</h3>
                  <p className="text-sm text-zinc-500 font-mono tracking-wide uppercase">
                    {isReady
                      ? workspace
                        ? `NEX Core Engine · ${workspace.name}`
                        : "NEX Core Engine · No workspace"
                      : "Connecting..."}
                  </p>
                </motion.div>
              )}

              {conv?.messages.map((msg) => (
                <motion.div 
                  key={msg.id}
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="w-full max-w-3xl mx-auto"
                >
                  {renderMessageContent(msg)}
                </motion.div>
              ))}

              <div ref={endOfMessagesRef} />
            </AnimatePresence>
          </div>

          <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-[#0A0A0A] via-[#0A0A0A] to-transparent pt-12 pb-6 px-6 md:px-12 lg:px-20">
            <form onSubmit={handleSubmit} className="relative w-full max-w-3xl mx-auto group">
              <div className="absolute inset-y-0 left-0 flex items-center pl-4 pointer-events-none">
                <MagnifyingGlass size={18} className="text-zinc-500 group-focus-within:text-indigo-400 transition-colors" />
              </div>
              <input 
                type="text" 
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={isReady && conv ? "Submit query to engine..." : "Connecting to engine…"}
                className="w-full bg-[#050505] border border-white/10 hover:border-white/20 focus:border-indigo-500/50 rounded-none pl-12 pr-14 py-4 text-sm text-zinc-50 placeholder:text-zinc-600 focus:outline-none transition-all shadow-2xl"
                disabled={isSearching || !conv || !conv.id}
              />
              <button 
                type="submit" 
                disabled={!query.trim() || isSearching || !conv || !conv.id}
                className="absolute inset-y-0 right-0 px-4 flex items-center justify-center text-zinc-500 hover:text-indigo-400 disabled:opacity-50 disabled:hover:text-zinc-500 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0A0A0A]"
              >
                <ArrowRight size={18} />
              </button>
            </form>
          </div>
        </div>

        {/* RIGHT COLUMN: Evidence Inspector */}
        <div className="hidden lg:flex flex-col col-span-3 h-full border-l border-white/5 bg-[#050505]">
          <div className="p-5 border-b border-white/5">
            <h2 className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-500">Evidence Inspector</h2>
          </div>
          
          <div className="flex-1 overflow-y-auto p-5">
            {activeCitation ? (
              <motion.div 
                key={activeCitation.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex flex-col gap-8"
              >
                <div>
                  <span className="text-[10px] font-mono text-indigo-400 uppercase tracking-widest mb-2 block">Active Citation</span>
                  <div className="flex items-center gap-2 mb-2">
                    <FileText size={16} className="text-zinc-400 shrink-0" />
                    <h3 className="text-sm font-medium text-zinc-300 leading-tight">{activeCitation.doc}</h3>
                  </div>
                  <div className="flex gap-2 text-[10px] font-mono text-zinc-500 uppercase tracking-widest">
                    {activeCitation.page && <span>Pg {activeCitation.page}</span>}
                    {activeCitation.section && <span>· {activeCitation.section}</span>}
                  </div>
                </div>
                
                <div className="relative border-l-2 border-indigo-500 pl-4 py-1">
                  <p className="text-sm text-zinc-400 leading-relaxed font-serif italic">
                    &ldquo;{activeCitation.text}&rdquo;
                  </p>
                </div>
                
                <Link
                  href={`/evidence/${activeCitation.documentId}?citation=${activeCitation.id}&text=${encodeURIComponent(activeCitation.text)}&page=${activeCitation.page}`}
                  className="group flex items-center gap-3 w-full py-3 px-4 border border-white/5 hover:border-white/10 hover:bg-white/[0.02] transition-colors mt-4 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 focus-visible:ring-offset-2 focus-visible:ring-offset-[#050505]"
                >
                  <Textbox size={16} className="text-zinc-500 group-hover:text-zinc-300 transition-colors" />
                  <span className="text-xs font-mono uppercase tracking-widest text-zinc-400 group-hover:text-zinc-300 transition-colors">Inspect Document</span>
                </Link>
              </motion.div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center opacity-30">
                <Quotes size={24} className="text-zinc-600 mb-4" />
                <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-zinc-500 max-w-[200px]">Waiting for citation selection</p>
              </div>
            )}
          </div>
        </div>

      </div>
    </main>
  );
}

function EdgeState({ title, desc, color, bg, border }: { title: string, desc: string, color: string, bg: string, border: string }) {
  return (
    <div className={`p-6 border ${border} ${bg} mb-12`}>
      <span className={`text-[10px] font-mono uppercase tracking-[0.2em] mb-4 flex items-center gap-2 ${color}`}>
        <WarningCircle size={14} weight="bold" />
        {title}
      </span>
      <p className="text-zinc-300 text-sm leading-relaxed">{desc}</p>
    </div>
  );
}
