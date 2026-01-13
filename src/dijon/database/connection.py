"""Database connection helpers.

This module provides a small, synchronous API for obtaining SQLite
connections configured for local, single-user workloads that may
still involve large tables (millions of rows).
"""

from __future__ import annotations

import contextlib
import logging
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .. import global_config as g

logger = logging.getLogger(__name__)


def _ensure_parent_dir(db_path: Path) -> None:
    """Ensure the parent directory for a database file exists.

    Args:
        db_path: Path to database file whose parent directory should exist.

    Side Effects:
        - Creates parent directory if it doesn't exist (with parents=True).
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)


def _configure_connection(conn: sqlite3.Connection) -> None:
    """Apply standard pragmas and row factory to a new connection.

    Configures the connection for use with the project by:
    - Setting row_factory to sqlite3.Row for dict-like access
    - Enabling foreign key constraints

    Args:
        conn: SQLite connection to configure.

    Side Effects:
        - Modifies connection settings (row_factory, pragmas).
    """
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Using default DELETE journal mode (no WAL) since this is single-user.
    # WAL mode would create .sqlite-wal and .sqlite-shm files which aren't needed.


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Return a configured SQLite connection.

    Creates a new SQLite connection with standard configuration (row factory,
    foreign keys enabled). Ensures parent directory exists before creating
    the database file.

    Args:
        db_path: Path to SQLite database file. Defaults to
            global_config.DB_DIR / "<project_name>-dev.sqlite".

    Returns:
        Configured SQLite connection ready for use.

    Logs:
        - DEBUG: "Opening SQLite database at {path}" when creating connection.

    Side Effects:
        - Creates parent directory if it doesn't exist.
        - Creates database file if it doesn't exist.
    """
    resolved = db_path or (g.DB_DIR / "{g.PROJECT_NAME}-dev.sqlite")
    if not isinstance(resolved, Path):
        resolved = Path(resolved)

    _ensure_parent_dir(resolved)
    logger.debug("Opening SQLite database at %s", resolved)
    conn = sqlite3.connect(str(resolved))
    _configure_connection(conn)
    return conn


@contextlib.contextmanager
def transaction(
    db_path: Path | None = None,
    existing_connection: sqlite3.Connection | None = None,
) -> Iterator[sqlite3.Connection]:
    """Context manager for a transactional connection block.

    Manages transaction boundaries (commit on success, rollback on error).
    If an existing connection is provided, it is reused and not closed.
    Otherwise, creates and closes a new connection.

    Args:
        db_path: Path to database file (only used if existing_connection
            is None). Defaults to global config.
        existing_connection: Existing connection to reuse. If None, creates
            a new connection that will be closed on exit.

    Yields:
        SQLite connection ready for database operations.

    Logs:
        - DEBUG: "Beginning transaction" at start
        - DEBUG: "Transaction committed" on success
        - ERROR: "Transaction rolled back due to error" on failure
        - DEBUG: "Connection closed" when closing owned connection.

    Side Effects:
        - Commits transaction on successful exit.
        - Rolls back transaction on exception.
        - Closes connection if it was created by this function.
    """
    owns_connection = existing_connection is None
    conn = existing_connection or get_connection(db_path=db_path)

    try:
        logger.debug("Beginning transaction")
        yield conn
        conn.commit()
        logger.debug("Transaction committed")
    except Exception:
        logger.exception("Transaction rolled back due to error")
        conn.rollback()
        raise
    finally:
        if owns_connection:
            conn.close()
            logger.debug("Connection closed")


def execute_script(conn: sqlite3.Connection, sql: str, *, description: str) -> None:
    """Execute a multi-statement SQL script with logging.

    Executes SQL that may contain multiple statements separated by semicolons.
    Primarily intended for schema initialization and seed data scripts.

    Args:
        conn: Database connection to execute script on.
        sql: Multi-statement SQL script to execute.
        description: Human-readable description for logging purposes.

    Raises:
        sqlite3.Error: If script execution fails.

    Logs:
        - INFO: "Executing SQL script: {description}" before execution.
        - ERROR: "Failed while executing SQL script: {description}" with
            exception details on failure.

    Side Effects:
        - Executes SQL statements against the database.
    """
    logger.info("Executing SQL script: %s", description)
    try:
        conn.executescript(sql)
    except sqlite3.Error:
        logger.exception("Failed while executing SQL script: %s", description)
        raise


