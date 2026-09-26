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

## Rule 9 — asyncpg test isolation requires NullPool

When multiple async tests share a SQLAlchemy connection pool, a failed transaction on one
connection corrupts subsequent tests with `InterfaceError: cannot rollback; the transaction
is in error state`. The fix is `NullPool` per test:

```python
engine = create_async_engine(settings.database_url, poolclass=NullPool)
```

This creates and discards a fresh connection for every test. Use this pattern in every
`conftest_sprint*.py` file.

## Rule 10 — Seed data pattern: commit + explicit DELETE cleanup

The asyncpg SAVEPOINT rollback pattern is unreliable with SQLAlchemy asyncio. Instead:
1. Insert seed rows and `await session.commit()` so they are visible to all connections.
2. In the fixture's `finally` block, execute explicit `DELETE` statements and `commit()`.
3. Use `NullPool` (Rule 9) to ensure the cleanup session is also a fresh connection.

## Rule 12 — base conftest.py must never define a `client` fixture

Each sprint defines its own `client` fixture in `conftest_sprintN.py`.
If `conftest.py` also defines `client`, pytest gives it higher priority and silently uses it
instead of the sprint-specific one, wiping all per-sprint dependency overrides (including
`get_storage`). Base `conftest.py` must only contain fixtures that are genuinely sprint-agnostic
(e.g. a bare `db_session`). Sprint-specific HTTP client setup belongs exclusively in the
corresponding `conftest_sprintN.py`.

## Rule 13 — Inject test storage via FastAPI dependency override, not module patching

Patching `_doc_svc.storage = ts` at the module level doesn't work when the route captures
the storage reference at import time. Instead, expose a `get_storage` FastAPI dependency in
the route module and override it in tests:

```python
app.dependency_overrides[get_storage] = lambda: LocalStorage(str(tmp_path / "storage"))
```

The `tmp_path` fixture is function-scoped and shared automatically between the `client`
fixture and the test function when both are in the same test.

## Rule 11 — DATABASE_URL port may differ across environments

The `.env` file is gitignored and may be changed externally. Always verify the port in
`settings.database_url` matches the running Postgres instance before running migrations.
Run `alembic upgrade head` against every new DB target after the URL changes.
