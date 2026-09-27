"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { List, X, User, Check, SignOut, Warning } from "@phosphor-icons/react";
import { useNexusSession } from "@/hooks/useNexusSession";
import { getDevUserId } from "@/services/apiClient";

// Dev test users — UUIDs are fixed and must stay in sync with backend/seed_test_data.py.
const DEV_TEST_USERS = [
  { label: "Alice — Admin",       id: "00000000-0000-0000-0000-000000000001" },
  { label: "Bob — Contributor",   id: "00000000-0000-0000-0000-000000000002" },
  { label: "Carol — Viewer",      id: "00000000-0000-0000-0000-000000000003" },
];

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function Navbar() {
  const pathname = usePathname();
  const { user, workspace, isReady, error, login, logout } = useNexusSession();

  const [menuOpen, setMenuOpen] = React.useState(false);
  const [authOpen, setAuthOpen] = React.useState(false);
  const [uuidInput, setUuidInput] = React.useState("");
  const [loginError, setLoginError] = React.useState<string | null>(null);
  const [isLoggingIn, setIsLoggingIn] = React.useState(false);

  // Pre-fill with whatever is already stored so returning users see it.
  React.useEffect(() => {
    if (authOpen) {
      setUuidInput(getDevUserId() ?? "");
      setLoginError(null);
    }
  }, [authOpen]);

  const isActive = (path: string) => {
    if (path === "/") return pathname === "/";
    return pathname?.startsWith(path);
  };

  const handleLogin = async (id: string) => {
    const trimmed = id.trim();
    if (!UUID_REGEX.test(trimmed)) {
      setLoginError("Please enter a valid UUID (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx).");
      return;
    }
    setLoginError(null);
    setIsLoggingIn(true);
    try {
      await login(trimmed);
      setAuthOpen(false);
    } catch {
      setLoginError("Login failed. Check that the backend is running and the UUID exists.");
    } finally {
      setIsLoggingIn(false);
    }
  };

  const isAuthenticated = !!user;

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

          {/* Dev Auth Button */}
          <button
            onClick={() => setAuthOpen(true)}
            className="hidden md:flex items-center gap-2 h-7 px-3 rounded bg-white/5 hover:bg-white/10 border border-white/10 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
            title={isAuthenticated ? `Signed in as ${user.name}` : "Dev Sign In"}
          >
            {isAuthenticated ? (
              <>
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 flex-shrink-0" />
                <span className="text-[10px] font-mono text-zinc-300 max-w-[120px] truncate">{user.name}</span>
              </>
            ) : (
              <>
                <User size={12} className="text-zinc-500" />
                <span className="text-[10px] font-mono text-zinc-500">Dev Login</span>
              </>
            )}
          </button>

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
            <Link href="/upload" onClick={() => setMenuOpen(false)} className="text-sm font-mono uppercase tracking-[0.15em] py-2 border-b border-white/5 text-indigo-400">
              + Ingest Document
            </Link>
            <button
              onClick={() => { setMenuOpen(false); setAuthOpen(true); }}
              className="text-left text-sm font-mono uppercase tracking-[0.15em] py-2 text-zinc-400 flex items-center gap-3"
            >
              <User size={14} />
              {isAuthenticated ? `Signed in: ${user.name}` : "Dev Login"}
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Dev Auth Modal */}
      <AnimatePresence>
        {authOpen && (
          <>
            <motion.div
              key="backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 z-[60] bg-black/60 backdrop-blur-sm"
              onClick={() => setAuthOpen(false)}
            />
            <motion.div
              key="modal"
              initial={{ opacity: 0, scale: 0.96, y: -8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: -8 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-x-4 top-20 md:inset-x-auto md:left-1/2 md:-translate-x-1/2 md:w-[480px] z-[61] bg-[#0A0A0A] border border-white/10 shadow-2xl"
            >
              {/* Modal header */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
                <div className="flex items-center gap-3">
                  <div className="h-1.5 w-1.5 bg-indigo-500" />
                  <span className="text-xs font-mono uppercase tracking-[0.2em] text-zinc-300">
                    Dev Auth
                  </span>
                  <span className="text-[9px] font-mono text-zinc-600 uppercase tracking-widest border border-zinc-800 px-1.5 py-0.5">
                    Sprint Mode
                  </span>
                </div>
                <button
                  onClick={() => setAuthOpen(false)}
                  className="text-zinc-500 hover:text-zinc-200 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 rounded"
                >
                  <X size={16} />
                </button>
              </div>

              <div className="px-6 py-5 space-y-5">
                {/* Current session info */}
                {isAuthenticated && (
                  <div className="flex items-start gap-3 border border-emerald-500/20 bg-emerald-500/5 px-4 py-3">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 mt-1.5 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-[10px] font-mono text-emerald-400 uppercase tracking-widest mb-0.5">Authenticated</p>
                      <p className="text-xs text-zinc-300 truncate">{user.name}</p>
                      <p className="text-[10px] font-mono text-zinc-500 truncate">{user.email}</p>
                      {workspace && (
                        <p className="text-[10px] font-mono text-zinc-600 mt-1 truncate">
                          Workspace: {workspace.name} ({workspace.role})
                        </p>
                      )}
                    </div>
                  </div>
                )}

                {/* Error display */}
                {(loginError || error) && (
                  <div className="flex items-start gap-3 border border-red-500/20 bg-red-500/5 px-4 py-3">
                    <Warning size={14} className="text-red-400 mt-0.5 flex-shrink-0" />
                    <p className="text-[11px] font-mono text-red-300">{loginError ?? error}</p>
                  </div>
                )}

                {/* Quick-select test users */}
                <div>
                  <p className="text-[9px] font-mono uppercase tracking-[0.2em] text-zinc-600 mb-2">Test Users</p>
                  <div className="space-y-1">
                    {DEV_TEST_USERS.map((u) => (
                      <button
                        key={u.id}
                        onClick={() => setUuidInput(u.id)}
                        className={`w-full flex items-center justify-between px-3 py-2.5 border text-left transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 ${
                          uuidInput === u.id
                            ? "border-indigo-500/40 bg-indigo-500/10 text-zinc-200"
                            : "border-white/5 bg-white/[0.02] text-zinc-400 hover:bg-white/5 hover:text-zinc-200"
                        }`}
                      >
                        <span className="text-[11px] font-mono">{u.label}</span>
                        <span className="text-[9px] font-mono text-zinc-600">{u.id.slice(-8)}</span>
                        {uuidInput === u.id && <Check size={12} className="text-indigo-400 ml-2 flex-shrink-0" />}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Manual UUID input */}
                <div>
                  <label className="text-[9px] font-mono uppercase tracking-[0.2em] text-zinc-600 block mb-2">
                    Or enter UUID manually
                  </label>
                  <input
                    type="text"
                    value={uuidInput}
                    onChange={(e) => { setUuidInput(e.target.value); setLoginError(null); }}
                    onKeyDown={(e) => { if (e.key === "Enter") handleLogin(uuidInput); }}
                    placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                    className="w-full bg-white/5 border border-white/10 px-3 py-2.5 text-[11px] font-mono text-zinc-200 placeholder-zinc-700 focus:outline-none focus:border-indigo-500/50 focus:bg-white/[0.07] transition-colors"
                    spellCheck={false}
                    autoComplete="off"
                  />
                </div>

                {/* Actions */}
                <div className="flex items-center gap-3 pt-1">
                  <button
                    onClick={() => handleLogin(uuidInput)}
                    disabled={isLoggingIn || !uuidInput.trim()}
                    className="flex-1 h-10 flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-[11px] font-mono uppercase tracking-widest transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
                  >
                    {isLoggingIn ? (
                      <>
                        <span className="h-1.5 w-1.5 rounded-full bg-white/60 animate-pulse" />
                        Connecting…
                      </>
                    ) : (
                      <>
                        <Check size={12} />
                        {isAuthenticated ? "Switch User" : "Sign In"}
                      </>
                    )}
                  </button>
                  {isAuthenticated && (
                    <button
                      onClick={() => { logout(); setAuthOpen(false); }}
                      className="h-10 px-4 flex items-center gap-2 border border-white/10 text-zinc-500 hover:text-zinc-200 hover:border-white/20 text-[11px] font-mono uppercase tracking-widest transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
                      title="Sign out"
                    >
                      <SignOut size={14} />
                      <span className="hidden sm:inline">Sign Out</span>
                    </button>
                  )}
                </div>

                {!isReady && !isLoggingIn && (
                  <p className="text-[9px] font-mono text-zinc-700 uppercase tracking-widest text-center animate-pulse">
                    Connecting to engine…
                  </p>
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
