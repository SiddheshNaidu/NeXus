"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { List, X } from "@phosphor-icons/react";

export function Navbar() {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = React.useState(false);
  
  const isActive = (path: string) => {
    if (path === "/") return pathname === "/";
    return pathname?.startsWith(path);
  };

  return (
    <>
      <nav className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between h-14 md:h-16 px-4 md:px-6 bg-[#050505]/90 backdrop-blur-md border-b border-white/5">
        <div className="flex items-center gap-6 md:gap-12">
          <Link href="/" className="flex items-center gap-2 touch-manipulation" onClick={() => setMenuOpen(false)}>
            <div className="h-2 w-2 bg-indigo-500 flex-shrink-0" />
            <span className="text-sm font-semibold tracking-[0.2em] uppercase text-zinc-50">
              NEXUS
            </span>
          </Link>
          <div className="hidden md:flex items-center gap-8 text-[11px] font-mono uppercase tracking-[0.1em] text-zinc-500">
            <Link href="/" className={`transition-colors hover:text-zinc-50 ${isActive("/") ? "text-zinc-300" : ""}`}>
              Core Index
            </Link>
            <Link href="/search" className={`transition-colors hover:text-zinc-50 ${isActive("/search") ? "text-zinc-300" : ""}`}>
              Active Workspace
            </Link>
          </div>
        </div>
        <div className="flex items-center gap-4 md:gap-6">
          <Link href="/upload" className={`hidden md:block text-[11px] font-mono uppercase tracking-[0.1em] transition-colors ${isActive("/upload") ? "text-indigo-300" : "text-indigo-400 hover:text-indigo-300"}`}>
            + Ingest
          </Link>
          <div className="hidden md:block h-6 w-px bg-white/10" />
          <div className="hidden md:flex h-6 w-6 rounded bg-white/10 items-center justify-center" aria-hidden="true" role="presentation">
            <span className="text-[10px] font-medium text-zinc-400">US</span>
          </div>
          {/* Mobile menu toggle */}
          <button
            className="md:hidden h-10 w-10 flex items-center justify-center text-zinc-400 hover:text-zinc-50 transition-colors touch-manipulation"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label={menuOpen ? "Close menu" : "Open menu"}
          >
            {menuOpen ? <X size={20} /> : <List size={20} />}
          </button>
        </div>
      </nav>

      {/* Mobile full-screen menu */}
      <AnimatePresence>
        {menuOpen && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
            className="md:hidden fixed top-14 inset-x-0 z-40 bg-[#050505]/98 backdrop-blur-xl border-b border-white/10 py-6 px-6 flex flex-col gap-5"
          >
            <Link href="/" onClick={() => setMenuOpen(false)} className={`text-sm font-mono uppercase tracking-[0.15em] py-2 border-b border-white/5 ${isActive("/") ? "text-zinc-50" : "text-zinc-400"}`}>
              Core Index
            </Link>
            <Link href="/search" onClick={() => setMenuOpen(false)} className={`text-sm font-mono uppercase tracking-[0.15em] py-2 border-b border-white/5 ${isActive("/search") ? "text-zinc-50" : "text-zinc-400"}`}>
              Active Workspace
            </Link>
            <Link href="/upload" onClick={() => setMenuOpen(false)} className={`text-sm font-mono uppercase tracking-[0.15em] py-2 text-indigo-400`}>
              + Ingest Document
            </Link>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
