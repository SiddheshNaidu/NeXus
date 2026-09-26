"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

export function Navbar() {
  const pathname = usePathname();
  
  const isActive = (path: string) => {
    if (path === "/") return pathname === "/";
    return pathname?.startsWith(path);
  };

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between h-16 px-6 bg-[#050505]/80 backdrop-blur-md border-b border-white/5">
      <div className="flex items-center gap-12">
        <Link href="/" className="flex items-center gap-2">
          <div className="h-2 w-2 bg-indigo-500" />
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
      <div className="flex items-center gap-6">
        <Link href="/upload" className={`text-[11px] font-mono uppercase tracking-[0.1em] transition-colors ${isActive("/upload") ? "text-indigo-300" : "text-indigo-400 hover:text-indigo-300"}`}>
          + Ingest
        </Link>
        <div className="h-6 w-px bg-white/10" />
        <div className="h-6 w-6 rounded bg-white/10 flex items-center justify-center" aria-hidden="true" role="presentation">
          <span className="text-[10px] font-medium text-zinc-400">US</span>
        </div>
      </div>
    </nav>
  );
}