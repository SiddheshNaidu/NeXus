# AGENTS.md — NEXUS Backend Engineering Rules

This file captures reusable engineering rules discovered during development.
Follow the sprint loop: READ PRD → inspect code → implement sprint scope → test → update BUILD_STATE.md → update AGENTS.md if a new rule is discovered → stop.

---

## Rule 1 — Do not guess; verify

Read the PRD section for the current sprint before writing a single line of code.
Read existing files before editing them.
If a behavior is unspecified, mark it as a blocker in BUILD_BLOCKERS.md rather than guessing.

## Rule 2 — Database URL driver split

The app runtime uses `postgresql+asyncpg://` (async driver via SQLAlchemy asyncio).
Alembic migrations use `postgresql+psycopg2://` (sync driver).
Derive the sync URL automatically: `settings.database_url.replace("+asyncpg", "+psycopg2")`.
Never hard-code the migration URL separately.

## Rule 3 — Test fixtures: fresh engine per test

Sharing a single SQLAlchemy `AsyncSession` across multiple test functions causes
`InterfaceError: cannot rollback; the transaction is in error state`.
Each test must get its own `AsyncSession` from a fresh session factory.
The `client` fixture in `conftest.py` creates a per-test engine and disposes of it on teardown.

## Rule 4 — Alembic autogenerate requires model import

Alembic's `--autogenerate` only detects tables whose models have been imported before
`Base.metadata` is inspected. The `env.py` must `import app.db.models` (the package `__init__.py`)
to register every ORM class with the metadata before autogenerate runs.

## Rule 5 — PYTHONPATH for tests

Add `pythonpath = .` to `pytest.ini` so the `app` package is importable without setting
`PYTHONPATH` manually. Do not rely on environment variables for test discovery.

## Rule 6 — Sprint boundary enforcement

Never create a module before its sprint requires it.
The `processing/`, `retrieval/`, `generation/`, `workers/`, and `services/` directories
are created only when the corresponding sprint begins.
Sprint 0 directories: `app/core/`, `app/db/`, `app/schemas/`, `app/api/v1/`, `app/providers/`, `app/storage/`.

## Rule 7 — Error responses never expose internals

All unhandled exceptions are caught by `unhandled_exception_handler` in `app/core/errors.py`.
The response is always `{"error": {"code": "INTERNAL_ERROR", "message": "..."}}`.
Stack traces are never returned to callers.

## Rule 8 — pgvector is a Sprint 3 concern

The `document_chunks.embedding` column is added by a separate migration in Sprint 3.
Sprint 0 models must not reference the vector type; the local Postgres install may not have
the `vector` extension. Standard column types only until Sprint 3.
