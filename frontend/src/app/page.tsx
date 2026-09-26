"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { Navbar } from "@/components/ui/navbar";
import { ArrowRight, FileText } from "@phosphor-icons/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { documentsService } from "@/services/documentsService";
import { DocumentSource } from "@/services/types";
import { StorySection } from "@/components/ui/story-section";
import { NexusContactParticles } from "@/components/ui/nexus-contact-particles";
import { AetherFlowBackground } from "@/components/ui/aether-flow-hero";
import { LisaHeroSequence } from "@/components/immersive/LisaHeroSequence";

export default function Home() {
  const router = useRouter();
  const [isTransitioning, setIsTransitioning] = React.useState(false);
  const [sources, setSources] = React.useState<DocumentSource[] | null>(null);

  React.useEffect(() => {
    documentsService.getAllDocuments().then(setSources);
  }, []);

  return (
    <main className="relative min-h-[100dvh] w-full overflow-hidden bg-[#050505]">
      <Navbar />

      {/* Hero: Locomotive-Style Lisa 3D Sequence */}
      <LisaHeroSequence />

      {/* Search section */}
      <div className="relative">
        <AetherFlowBackground />

        {/* Technical Grid Background */}
        <div className="pointer-events-none absolute inset-0 opacity-[0.03]" 
             style={{ backgroundImage: 'linear-gradient(#ffffff 1px, transparent 1px), linear-gradient(90deg, #ffffff 1px, transparent 1px)', backgroundSize: '64px 64px' }}>
        </div>

        <div className="relative z-10 mx-auto max-w-[1400px] px-4 sm:px-6 pt-20 sm:pt-28 md:pt-32 pb-20 sm:pb-32 flex flex-col items-center pointer-events-none">
          
          <motion.div 
            className="flex flex-col items-center text-center w-full max-w-4xl"
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.8, ease: [0.32, 0.72, 0, 1] }}
          >
            <div className="inline-flex items-center gap-3 border-b border-white/10 pb-4 mb-8 md:mb-12">
              <div className="h-1.5 w-1.5 bg-indigo-500 flex-shrink-0" />
              <span className="text-[10px] md:text-xs font-mono uppercase tracking-[0.3em] text-zinc-500">
                NEXUS Engine
              </span>
            </div>
            
            <h1 className="text-4xl sm:text-5xl md:text-7xl lg:text-[5.5rem] font-medium tracking-tighter leading-[1.05] text-zinc-50">
              Ask what your <br />
              <span className="text-zinc-500">documents</span> know.
            </h1>
            
            <p className="mt-6 md:mt-10 max-w-[36ch] md:max-w-[42ch] text-base md:text-lg text-zinc-400 leading-relaxed font-light">
              NEXUS finds the answer, then shows you exactly where it came from.
            </p>
            
            <div className="mt-10 md:mt-14 flex items-center gap-4 md:gap-6">
              <button 
                onClick={(e) => {
                  e.preventDefault();
                  setIsTransitioning(true);
                  setTimeout(() => router.push("/search"), 800);
                }}
                className="pointer-events-auto group relative inline-flex h-12 items-center justify-center gap-3 overflow-hidden bg-white text-zinc-950 px-6 md:px-8 text-sm font-medium transition-all hover:bg-zinc-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-white/20 active:scale-[0.98] touch-manipulation"
              >
                <span>Enter Workspace</span>
                <span className="transition-transform duration-300 group-hover:translate-x-1">
                  <ArrowRight weight="bold" />
                </span>
              </button>
            </div>
          </motion.div>

          {/* Indexed Sources */}
          <motion.div 
            className="mt-20 md:mt-32 w-full max-w-5xl pointer-events-auto"
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 1, delay: 0.3 }}
          >
            <div className="flex items-center justify-between border-b border-white/10 pb-4 mb-6 md:mb-8">
              <span className="text-[10px] md:text-xs font-mono uppercase tracking-[0.2em] text-zinc-500">Indexed Sources</span>
              <Link href="/upload" className="text-[10px] md:text-xs font-mono uppercase tracking-[0.1em] text-indigo-400 hover:text-indigo-300 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 touch-manipulation">
                + Ingest New
              </Link>
            </div>
            
            {sources === null ? (
              <div className="animate-pulse flex gap-4 bg-white/5 h-24 md:h-32 w-full" />
            ) : sources.length === 0 ? (
              <div className="p-6 md:p-8 text-center flex flex-col items-center border border-white/5 border-dashed">
                <FileText size={24} className="text-zinc-700 mb-4" />
                <p className="text-xs font-mono text-zinc-500 mb-6 uppercase tracking-widest">No documents indexed</p>
                <Link href="/upload" className="text-[10px] font-mono uppercase tracking-widest text-indigo-400 hover:text-indigo-300 transition-colors border border-indigo-500/30 px-4 py-2 hover:bg-indigo-500/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 touch-manipulation">
                  Ingest Sources
                </Link>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-px bg-white/10 relative z-10">
                {sources.map((doc) => (
                  <div key={doc.id} className="group relative bg-[#050505] p-4 md:p-6 transition-colors hover:bg-zinc-900/50 cursor-pointer overflow-hidden">
                    <div className="absolute top-0 right-0 p-4 opacity-0 group-hover:opacity-100 transition-opacity">
                      <ArrowRight size={16} className="text-zinc-500" />
                    </div>
                    <div className="flex items-center gap-3 mb-4 md:mb-6">
                      <FileText size={20} className="text-zinc-600 group-hover:text-indigo-400 transition-colors flex-shrink-0" weight="light" />
                      <span className="text-[10px] font-mono text-zinc-600 truncate">{doc.id}</span>
                    </div>
                    <h3 className="text-sm font-medium text-zinc-300 group-hover:text-zinc-50 transition-colors pr-8 line-clamp-2">
                      {doc.filename}
                    </h3>
                    <div className="mt-6 md:mt-8 flex items-center justify-between">
                      <div className="h-0.5 w-12 bg-white/10 group-hover:bg-indigo-500/50 transition-colors" />
                      <span className={`text-[10px] font-mono tracking-wider ${doc.status === "READY" ? "text-zinc-500" : "text-amber-500/70"}`}>
                        {doc.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        </div>
      </div>
      
      <div className={isTransitioning ? "opacity-0 transition-opacity duration-500 pointer-events-none" : ""}>
        <StorySection />
      </div>
      <NexusContactParticles />
    </main>
  );
}
