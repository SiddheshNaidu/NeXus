# NEXUS — Frontend Build State

Tracks sprint-by-sprint progress for the frontend (`/frontend`).
Mirrors discipline used in the root `BUILD_STATE.md`.

---

## Sprint 0 — UI Initialization & Dev Auth

**Status:** ✅ COMPLETE

### What was built

| File | Change |
|------|--------|
| `src/services/apiClient.ts` | Migrated auth storage from `sessionStorage` to `localStorage` for persistence across tab closes and page refreshes. Added `clearDevUserId()` to atomically wipe both the user ID and active workspace ID keys on logout. |
| `src/hooks/useNexusSession.ts` | Added a `trigger` counter so the bootstrap `useEffect` can be re-run on demand without a full page reload. Exposed `login(userId: string)` — saves the UUID and fires a re-bootstrap that re-fetches `/me` and `/workspaces`. Exposed `logout()` — calls `clearDevUserId()` and immediately resets all session state to unauthenticated. |
| `src/components/ui/navbar.tsx` | Replaced the static `"US"` avatar placeholder with a fully functional **Dev Login Modal**. Features: authenticated state banner (name, email, workspace, role); quick-select buttons for three hardcoded test users; manual UUID input with regex validation and `Enter`-key submit; Sign In / Switch User and Sign Out actions; error display for both login failures and session bootstrap errors; mobile hamburger menu integration. |
| `src/components/immersive/NEXsequence.tsx` | Tightened the `audio.play()` rejection handler to inspect `err.name` before logging. `NotSupportedError` (`.mp3` file absent) and `AbortError` (playback interrupted by a rapid subsequent call) are now swallowed silently — the speech synthesis fallback still runs. Only truly unexpected error names emit `console.warn`, eliminating the terminal spam seen when audio assets are not yet generated. |

### Why these changes were needed

- The backend's mock auth system requires an `X-Dev-User-ID` header on every request. With no login UI and credentials only living in `sessionStorage`, any tab refresh left the app in an unauthenticated state, causing the upload page to show _"No workspace available. Ensure you are authenticated."_
- `sessionStorage` is scoped to a single browsing-session tab; `localStorage` is the correct store for a developer credential that should survive refreshes.
- The audio `.mp3` files are intentionally gitignored (generated via ElevenLabs — see `public/audio/README.md`). Without them, every click on the NEX hero sequence threw an unhandled `NotSupportedError` into the browser console, obscuring real errors.

---

## Sprint 0.1 — UUID Contract & Seed Alignment

**Status:** ✅ COMPLETE

### What was built

| File | Change |
|------|--------|
| `src/components/ui/navbar.tsx` | Tightened the `DEV_TEST_USERS` comment to make the UUID contract explicit: values must stay in sync with `backend/seed_test_data.py`. |
| `../backend/seed_test_data.py` | Replaced `uuid.uuid4()` random generation with fixed UUIDs matching the frontend. Switched conflict strategy to `ON CONFLICT (email) DO UPDATE SET id = EXCLUDED.id` — see Sprint 0.1a below for the full story. Added Carol (viewer), Workspace Gamma, and two extra memberships. Added `--reset` flag. |
| `../dev.sh` | Auto-seeds the DB before the backend starts on every launch (idempotent, `SKIP_SEED=1` to bypass). |
| `../dev.bat` | Same auto-seed step for Windows. |

### Why these changes were needed

- The frontend navbar has three hardcoded UUIDs (`00000000-…-0001/0002/0003`). The old seed script used `uuid.uuid4()`, producing different IDs on every run. The backend's `security.py` does a strict `SELECT … WHERE id = ?` and raises `401` for any UUID not in the database — so clicking any test user always returned 401 and the workspace list stayed empty.
- Making the seed idempotent and wiring it into the dev launchers ensures the DB is always in the correct state the moment the servers start, with no manual step required.

### Fixed UUID reference table

| Identity | UUID | Workspace memberships |
|---|---|---|
| Alice | `00000000-0000-0000-0000-000000000001` | Alpha (admin), Gamma (contributor) |
| Bob | `00000000-0000-0000-0000-000000000002` | Alpha (contributor), Beta (contributor) |
| Carol | `00000000-0000-0000-0000-000000000003` | Alpha (viewer) |

---

## Sprint 0.1a — Seed Idempotency Fix (email unique-index trap)

**Status:** ✅ COMPLETE

### What broke and why

Running the Sprint 0.1 seed against a database that already contained the old random-UUID rows caused a `UniqueViolationError` on `ix_users_email`, not the primary key:

```
psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint "ix_users_email"
DETAIL:  Key (email)=(alice@nexus.local) already exists.
```

**Root cause:** `ON CONFLICT (id) DO NOTHING` only catches collisions on the `id` primary key. When Postgres evaluated the new row it saw the fixed UUID `…0001` — no ID conflict — and proceeded to insert. The insert then hit the `email` unique index which *was* occupied by the old random-UUID row. `DO NOTHING` never fires for a constraint it wasn't told to watch.

### What was changed

| File | Change |
|------|--------|
| `../backend/seed_test_data.py` | Changed the User upsert from `ON CONFLICT (id) DO NOTHING` to `ON CONFLICT (email) DO UPDATE SET id = EXCLUDED.id, name = EXCLUDED.name`. Email is the stable natural key — conflicting on it and overwriting the `id` column atomically replaces any stale random UUID with the correct fixed one in a single SQL statement. No DELETE required, no two-pass logic. |
| `../backend/seed_test_data.py` — `reset()` | Extended the User delete to match on `id IN (…) OR email IN (…)` so `--reset` also purges orphaned old-UUID rows whose IDs no longer match the fixed constants. |

### Idempotency contract going forward

| Table | Conflict target | Action |
|---|---|---|
| `users` | `email` | `DO UPDATE SET id, name` — repairs stale UUIDs |
| `workspaces` | `id` | `DO NOTHING` — id is the only unique key |
| `workspace_members` | `(workspace_id, user_id)` | `DO NOTHING` |

---

## Next Sprint

_Awaiting definition — candidates: workspace switcher in search page, evidence viewer polish, production auth handoff._
