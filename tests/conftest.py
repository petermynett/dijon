from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def app_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Forces test mode. Application code can use this to refuse dangerous behaviors.
    Automatically applied to all tests.
    """
    monkeypatch.setenv("APP_ENV", "test")


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """
    A dedicated temp root directory for each test.
    All filesystem writes in tests should be under this root (or tmp_path directly).
    """
    root = tmp_path / "proj"
    (root / "data" / "in").mkdir(parents=True)
    (root / "data" / "out").mkdir(parents=True)
    return root


@pytest.fixture(autouse=True)
def chdir_to_project_root(project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Automatically change working directory to project_root for all tests.
    This ensures relative-path operations go into the temp directory by default.
    """
    monkeypatch.chdir(project_root)


@pytest.fixture
def sqlite_path(project_root: Path) -> Path:
    """
    On-disk SQLite DB under the temp project root (more realistic than :memory:).
    """
    return project_root / "data" / "out" / "test.sqlite"


@pytest.fixture
def db_conn(sqlite_path: Path, project_root: Path) -> sqlite3.Connection:
    """
    A SQLite connection that is always closed after each test.

    Safety enforcement:
    - Path assertion: DB must be under project_root (prevents touching real DBs)
    - Safety pragmas:
      - foreign_keys: catch relational bugs early
      - journal_mode=WAL: closer to real-world usage
      - synchronous=NORMAL: good balance for tests
      - busy_timeout: helps avoid flaky "database is locked" errors
    """
    # Assert DB path is under project_root (fail fast if misconfigured)
    try:
        sqlite_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        raise AssertionError(
            f"SQLite path {sqlite_path} is not under project_root {project_root}. "
            "This prevents accidental writes to real databases."
        )

    conn = sqlite3.connect(sqlite_path)
    try:
        # Safety and performance pragmas
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 2000;")
        yield conn
    finally:
        conn.close()