#!/usr/bin/env bash
# =============================================================================
# dev.sh — NEXUS unified dev launcher (Linux / macOS / Arch)
#
# Starts the FastAPI backend + Next.js frontend in parallel.
# Auto-detects the Python virtual environment regardless of how it was named.
#
# Usage:
#   ./dev.sh          — starts both servers
#   ./dev.sh --stop   — kills both servers started by a previous run
# =============================================================================

set -euo pipefail

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[nexus]${RESET} $*"; }
success() { echo -e "${GREEN}[nexus]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[nexus]${RESET} $*"; }
die()     { echo -e "${RED}[nexus] ERROR:${RESET} $*" >&2; exit 1; }

# ── Resolve the repo root (the directory this script lives in) ────────────────
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"
PID_FILE="$REPO_ROOT/.dev_pids"

# ── --stop handler ─────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--stop" ]]; then
  if [[ ! -f "$PID_FILE" ]]; then
    warn "No PID file found — nothing to stop."
    exit 0
  fi
  while IFS= read -r pid; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" && info "Killed PID $pid"
    fi
  done < "$PID_FILE"
  rm -f "$PID_FILE"
  success "All dev processes stopped."
  exit 0
fi

# ── Sanity-check directories ───────────────────────────────────────────────────
[[ -d "$BACKEND_DIR" ]]  || die "backend/ directory not found at $BACKEND_DIR"
[[ -d "$FRONTEND_DIR" ]] || die "frontend/ directory not found at $FRONTEND_DIR"

# ── Detect Python virtual environment ─────────────────────────────────────────
# Search order: backend/.venv, root-level venv, any *venv*/.../activate found
# under the repo root (catches .env, env, venv, .venv, my_venv, etc.)
find_venv_activate() {
  local candidates=(
    "$BACKEND_DIR/.venv/bin/activate"
    "$BACKEND_DIR/venv/bin/activate"
    "$BACKEND_DIR/.env/bin/activate"
    "$BACKEND_DIR/env/bin/activate"
    "$REPO_ROOT/.venv/bin/activate"
    "$REPO_ROOT/venv/bin/activate"
    "$REPO_ROOT/.env/bin/activate"
    "$REPO_ROOT/env/bin/activate"
  )

  # Check explicit well-known paths first (fastest)
  for path in "${candidates[@]}"; do
    if [[ -f "$path" ]]; then
      echo "$path"
      return 0
    fi
  done

  # Fallback: glob-search for any activate script one level deep under repo root
  # This catches names like my_venv, nexus_env, project-venv, etc.
  while IFS= read -r found; do
    echo "$found"
    return 0
  done < <(find "$REPO_ROOT" -maxdepth 3 -name "activate" \
             -path "*/bin/activate" \
             ! -path "*/.git/*" \
             ! -path "*/node_modules/*" \
             2>/dev/null | sort)

  return 1
}

VENV_ACTIVATE=""
if VENV_ACTIVATE="$(find_venv_activate)"; then
  success "Found virtual environment: ${BOLD}$(dirname "$(dirname "$VENV_ACTIVATE")")${RESET}"
else
  die "No Python virtual environment found.\n\n  Expected one of:\n    backend/.venv/  backend/venv/  .venv/  venv/  (or any */bin/activate within 3 levels)\n\n  Create one with:  python -m venv backend/.venv"
fi

# ── Check that required tools exist ───────────────────────────────────────────
check_cmd() {
  command -v "$1" &>/dev/null || die "'$1' not found. Install it and retry."
}
check_cmd node
check_cmd npm

# ── Ensure frontend dependencies are installed ────────────────────────────────
if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  info "node_modules not found — running npm install..."
  npm install --prefix "$FRONTEND_DIR" || die "npm install failed"
fi

# ── Copy .env.example → .env if .env is absent ───────────────────────────────
BACKEND_ENV="$BACKEND_DIR/.env"
if [[ ! -f "$BACKEND_ENV" ]] && [[ -f "$BACKEND_DIR/.env.example" ]]; then
  cp "$BACKEND_DIR/.env.example" "$BACKEND_ENV"
  warn ".env was missing — copied from .env.example. Edit $BACKEND_ENV with real credentials."
fi

# ── Seed the database with deterministic dev users ───────────────────────────
# Runs every startup but is fully idempotent (ON CONFLICT DO NOTHING).
# Pass SKIP_SEED=1 to skip — e.g. SKIP_SEED=1 ./dev.sh
if [[ "${SKIP_SEED:-0}" != "1" ]]; then
  info "Seeding dev users into the database (idempotent)..."
  (
    # shellcheck disable=SC1090
    source "$VENV_ACTIVATE"
    cd "$BACKEND_DIR"
    python seed_test_data.py
  ) && success "Database seed OK." || warn "Seed failed — backend may be starting without test users. Is the DB running?"
fi

# ── Launch backend ─────────────────────────────────────────────────────────────
info "Starting ${BOLD}FastAPI backend${RESET} on http://localhost:8000 ..."
(
  # shellcheck disable=SC1090
  source "$VENV_ACTIVATE"
  cd "$BACKEND_DIR"
  exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
) > "$REPO_ROOT/.backend.log" 2>&1 &
BACKEND_PID=$!

# ── Launch frontend ────────────────────────────────────────────────────────────
info "Starting ${BOLD}Next.js frontend${RESET} on http://localhost:3000 ..."
(
  cd "$FRONTEND_DIR"
  exec npm run dev
) > "$REPO_ROOT/.frontend.log" 2>&1 &
FRONTEND_PID=$!

# ── Persist PIDs so --stop can clean up ───────────────────────────────────────
printf '%s\n%s\n' "$BACKEND_PID" "$FRONTEND_PID" > "$PID_FILE"

# ── Wait a moment then confirm both processes are alive ──────────────────────
sleep 2
FAILED=0
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
  warn "Backend failed to start. Last log lines:"
  tail -20 "$REPO_ROOT/.backend.log" >&2
  FAILED=1
fi
if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
  warn "Frontend failed to start. Last log lines:"
  tail -20 "$REPO_ROOT/.frontend.log" >&2
  FAILED=1
fi
[[ $FAILED -eq 1 ]] && die "One or more processes failed. Check logs above."

echo ""
echo -e "${BOLD}${GREEN}  ✓ NEXUS is running${RESET}"
echo -e "    Frontend  →  ${CYAN}http://localhost:3000${RESET}"
echo -e "    Backend   →  ${CYAN}http://localhost:8000/docs${RESET}"
echo ""
echo -e "    Logs:  ${YELLOW}.backend.log${RESET}  |  ${YELLOW}.frontend.log${RESET}"
echo -e "    Stop:  ${BOLD}./dev.sh --stop${RESET}   or   ${BOLD}Ctrl+C${RESET}"
echo ""

# ── Forward Ctrl+C to both children ──────────────────────────────────────────
trap 'info "Shutting down..."; kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null; rm -f "$PID_FILE"; exit 0' INT TERM

# ── Tail both logs interleaved so the terminal stays useful ──────────────────
tail -f "$REPO_ROOT/.backend.log" "$REPO_ROOT/.frontend.log" &
TAIL_PID=$!

wait "$BACKEND_PID" "$FRONTEND_PID"
kill "$TAIL_PID" 2>/dev/null
rm -f "$PID_FILE"
