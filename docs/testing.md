# Testing (Agent Protocol)

This project uses `pytest`. This document is the source of truth for test creation and testing workflows.

## Non-Negotiables (Safety / Isolation)

By default, tests MUST:
- Write files ONLY under pytest temp directories (e.g. `tmp_path`), never under `./data/` or any real project directories.
- Use ONLY temporary SQLite databases (prefer on-disk DBs created under `tmp_path`).
- Never connect to or modify any persistent on-disk database outside the test temp directory.
- Never require network access. API calls must be mocked/stubbed unless explicitly marked as a live/integration test (opt-in).

Guardrail convention:
- `APP_ENV=test` is automatically set for all tests (via autouse fixture).
- Working directory is automatically changed to `project_root` for all tests (via autouse fixture).
- Application code SHOULD refuse dangerous actions unless explicitly configured for non-test environments.

## Test Types (Markers)

Markers are defined in `pyproject.toml`:
- `unit`: pure logic, no I/O (default / most tests)
- `integration`: filesystem and/or sqlite (opt-in where appropriate; keep small in count)
- `slow`: intentionally slow (never default)

Policy:
- Prefer `unit` tests when the behavior can be validated without I/O.
- Use `integration` tests to validate SQLite schema/constraints, transactions, and pipeline wiring.
- `slow` tests must be explicitly marked and must not run in the normal loop.

## Default Commands (Agent Runbook)

Fast loop (recommended after non-trivial change):
- `pytest -q`

Narrow scope:
- `pytest -q tests/path/to/test_file.py`
- `pytest -q -k keyword_or_expr`

By marker:
- `pytest -q -m unit`
- `pytest -q -m integration`
- `pytest -q -m "not slow"`

Rerun failures:
- `pytest -q --lf`

Stop early (debug):
- `pytest -q -x`
- `pytest -q --maxfail=1`

Show skip/xfail summaries:
- `pytest -q -ra`

## Fixtures (Required Pattern)

Use fixtures to enforce isolation and make tests deterministic.

Required baseline fixtures (via `tests/conftest.py`):
- `app_env`: automatically sets `APP_ENV=test` for all tests (autouse)
- `chdir_to_project_root`: automatically changes working directory to `project_root` for all tests (autouse)
- `project_root`: a temp root directory for the test (all files must live under it)
- `sqlite_path`: the temp SQLite file path under `project_root`
- `db_conn`: a SQLite connection to the temp DB with enforced safety checks and pragmas

Enforced defaults:
- `APP_ENV=test` is set automatically (no need to request `app_env` fixture)
- Working directory is set to `project_root` automatically (relative paths go to temp dir)
- SQLite DB path is validated to be under `project_root` (prevents touching real databases)
- SQLite pragmas are automatically applied:
  - `foreign_keys = ON`: catch relational bugs early
  - `journal_mode = WAL`: closer to real-world usage
  - `synchronous = NORMAL`: good balance for tests
  - `busy_timeout = 2000`: helps avoid flaky "database is locked" errors

Rules:
- If a test needs a filesystem path, it must use `project_root` or `tmp_path`.
- If a test needs a database, it must use `db_conn` (or a fixture built on top of it).
- Never hardcode absolute paths or refer to any real DB file.

## API Testing Policy

Default: no network.

Recommended approach:
- Unit test the API client by mocking the HTTP layer.
- Validate request construction (URL, method, headers, body) and response parsing.
- Only add live API tests if explicitly requested; mark them and keep them opt-in.

## Output / Reporting Convention

When completing a task that changes code:
- `Tests: PASSED` + exact command(s) run
- `Tests: FAILED` + exact command(s) run + brief failure summary
- `Tests: NOT RUN` + why + exact command(s) to run

Do not claim tests passed unless they were executed.