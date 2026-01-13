"""Database initialization using schema and seed SQL files.

This module is responsible for creating a fresh database (or ensuring
an existing one is compatible) by executing `sql/schema.sql` and
optionally `sql/seed_data.sql`, and for maintaining a minimal
`schema_meta` table with a `schema_version` value.
"""

from __future__ import annotations

import logging
import sqlite3
import os
from pathlib import Path

from .. import global_config as g

from .connection import execute_script, get_connection
from .errors import DatabaseError, from_sqlite_error

logger = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION = 1


def _schema_path() -> Path:
    """Return path to schema.sql file.

    Returns:
        Path to schema.sql in the SQL directory.
    """
    return g.SQL_DIR / "schema.sql"


def _seed_path() -> Path:
    """Return path to seed_data.sql file.

    Returns:
        Path to seed_data.sql in the SQL directory.
    """
    return g.SQL_DIR / "seed_data.sql"


def _ensure_schema_meta(conn: sqlite3.Connection) -> None:
    """Ensure the `schema_meta` table exists.

    Creates the schema_meta table if it doesn't exist. This table stores
    metadata about the database schema, including the schema version.

    Args:
        conn: Database connection.

    Side Effects:
        - Creates schema_meta table if it doesn't exist.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    """Upsert the schema_version entry in schema_meta.

    Sets or updates the schema_version value in the schema_meta table.
    Ensures schema_meta table exists before updating.

    Args:
        conn: Database connection.
        version: Schema version number to record.

    Side Effects:
        - Creates schema_meta table if needed.
        - Inserts or updates schema_version entry.
    """
    _ensure_schema_meta(conn)
    conn.execute(
        """
        INSERT INTO schema_meta (key, value)
        VALUES ('schema_version', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(version),),
    )


def initialize_database(
    db_path: Path | None = None,
    *,
    with_seed: bool = False,
) -> None:
    """Initialize the database using `schema.sql` and optional `seed_data.sql`.

    Executes schema.sql to create all tables and optionally runs seed_data.sql
    to populate initial data. Records the schema version in schema_meta.
    Safe to run on a new database or re-run on existing databases with
    idempotent schema SQL.

    Args:
        db_path: Path to SQLite database file. Defaults to global config.
        with_seed: If True, also execute seed_data.sql after schema.sql.

    Raises:
        FileNotFoundError: If schema.sql doesn't exist, or if with_seed=True
            and seed_data.sql doesn't exist.
        DatabaseError: If SQL execution fails.

    Logs:
        - INFO: "Initializing database (with_seed={with_seed})" at start.
        - INFO: "Database initialization complete (schema_version={version})"
            on success.

    Side Effects:
        - Creates database file if it doesn't exist.
        - Executes schema.sql to create/update tables.
        - Executes seed_data.sql if with_seed=True.
        - Records schema version in schema_meta table.
        - Commits all changes.
    """
    schema_file = _schema_path()
    seed_file = _seed_path()

    if not schema_file.exists():
        msg = f"Schema file not found: {schema_file}"
        raise FileNotFoundError(msg)

    if with_seed and not seed_file.exists():
        msg = f"Seed data file not found: {seed_file}"
        raise FileNotFoundError(msg)

    logger.info("Initializing database (with_seed=%s)", with_seed)

    schema_sql = schema_file.read_text(encoding="utf-8")
    seed_sql = seed_file.read_text(encoding="utf-8") if with_seed else None

    conn = get_connection(db_path=db_path)
    try:
        execute_script(conn, schema_sql, description="schema.sql")
        if seed_sql:
            execute_script(conn, seed_sql, description="seed_data.sql")
        _set_schema_version(conn, CURRENT_SCHEMA_VERSION)
        conn.commit()
        logger.info("Database initialization complete (schema_version=%s)", CURRENT_SCHEMA_VERSION)
    except sqlite3.Error as exc:
        conn.rollback()
        raise from_sqlite_error(exc) from exc
    finally:
        conn.close()


class DatabaseLockedError(DatabaseError):
    """Raised when database deletion fails because the database is in use."""


def delete_database(db_path: Path | None = None) -> None:
    """Safely delete a SQLite database and its WAL/SHM files.

    Performs a best-effort clean shutdown by opening a connection, checkpointing
    the WAL, then closing. Then deletes the database file and any associated
    WAL/SHM files in the correct order. If deletion fails due to locks, raises
    DatabaseLockedError with a clear message.

    Args:
        db_path: Path to SQLite database file. Defaults to global config.

    Raises:
        DatabaseLockedError: If any file deletion fails because the database
            is locked or in use. Includes instructions for the user.
        OSError: If deletion fails for other reasons (permissions, etc.).

    Logs:
        - INFO: "Attempting to delete database at {path}" at start.
        - DEBUG: "Checkpointing WAL before deletion" when checkpointing.
        - INFO: "Database deleted successfully" on success.
        - ERROR: "Failed to delete database file" with details on failure.

    Side Effects:
        - Opens and closes a database connection to checkpoint WAL.
        - Deletes .db, .db-wal, and .db-shm files if they exist.
    """
    resolved = db_path or (g.DB_DIR / f"{g.PROJECT_NAME}-dev.sqlite")
    if not isinstance(resolved, Path):
        resolved = Path(resolved)

    logger.info("Attempting to delete database at %s", resolved)

    # Step A: Best-effort clean shutdown
    # Open connection, checkpoint WAL, then close
    # Only attempt if database file exists
    if resolved.exists():
        try:
            logger.debug("Checkpointing WAL before deletion")
            conn = sqlite3.connect(str(resolved), timeout=5.0)
            try:
                # Set journal mode to WAL if not already set (best effort)
                conn.execute("PRAGMA journal_mode=WAL")
                # Checkpoint the WAL (TRUNCATE merges WAL into main DB and truncates WAL)
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error:
            # If checkpoint fails, continue with deletion attempt anyway
            logger.warning("Failed to checkpoint WAL, proceeding with deletion")
    else:
        # Database doesn't exist - idempotent success
        logger.info("Database does not exist (already deleted)")
        return

    # Step B: Delete files in order (.db, -wal, -shm)
    files_to_delete = [
        resolved,
        resolved.with_suffix(resolved.suffix + "-wal"),
        resolved.with_suffix(resolved.suffix + "-shm"),
    ]

    deleted_files = []
    failed_files = []

    for file_path in files_to_delete:
        if not file_path.exists():
            continue

        try:
            file_path.unlink()
            deleted_files.append(file_path)
            logger.debug("Deleted %s", file_path)
        except OSError as exc:
            # Check if error is due to file being locked/in use
            if exc.errno == os.errno.EBUSY or "locked" in str(exc).lower():
                failed_files.append((file_path, "locked"))
                logger.error("Failed to delete %s: database is locked", file_path)
            else:
                failed_files.append((file_path, str(exc)))
                logger.error("Failed to delete %s: %s", file_path, exc)

    if failed_files:
        locked_files = [f for f, reason in failed_files if reason == "locked"]
        if locked_files:
            msg = (
                "Database is in use; close all processes using it "
                "(Cursor, scripts, sqlite browser) and retry."
            )
            raise DatabaseLockedError(msg)

        # Other errors
        error_details = "; ".join(f"{f.name}: {reason}" for f, reason in failed_files)
        raise OSError(f"Failed to delete database files: {error_details}")

    logger.info("Database deleted successfully (%d file(s) removed)", len(deleted_files))


def init_database_for_rebuild(db_path: Path | None = None) -> None:
    """Initialize a fresh database with WAL mode, schema, and seed data.

    Creates a new database file, sets required SQLite pragmas (WAL journal mode,
    busy timeout, foreign keys), then applies schema.sql and seed_data.sql each
    in their own transaction. If either step fails, the database is left in a
    failed state (transaction rolled back).

    Args:
        db_path: Path to SQLite database file. Defaults to global config.

    Raises:
        FileNotFoundError: If schema.sql or seed_data.sql doesn't exist.
        DatabaseError: If SQL execution fails.

    Logs:
        - INFO: "Initializing database for rebuild" at start.
        - INFO: "Database rebuild initialization complete" on success.

    Side Effects:
        - Creates database file if it doesn't exist.
        - Sets SQLite pragmas (WAL mode, busy timeout, foreign keys).
        - Executes schema.sql in a transaction.
        - Executes seed_data.sql in a transaction.
        - Records schema version in schema_meta table.
    """
    resolved = db_path or (g.DB_DIR / f"{g.PROJECT_NAME}-dev.sqlite")
    if not isinstance(resolved, Path):
        resolved = Path(resolved)

    schema_file = _schema_path()
    seed_file = _seed_path()

    if not schema_file.exists():
        msg = f"Schema file not found: {schema_file}"
        raise FileNotFoundError(msg)

    if not seed_file.exists():
        msg = f"Seed data file not found: {seed_file}"
        raise FileNotFoundError(msg)

    logger.info("Initializing database for rebuild")

    schema_sql = schema_file.read_text(encoding="utf-8")
    seed_sql = seed_file.read_text(encoding="utf-8")

    # Ensure parent directory exists
    resolved.parent.mkdir(parents=True, exist_ok=True)

    # Create connection and set construction-time pragmas
    conn = sqlite3.connect(str(resolved), timeout=5.0)
    try:
        # Set required pragmas explicitly (do not rely on defaults)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")  # 5 seconds
        conn.row_factory = sqlite3.Row

        # Apply schema in a transaction
        logger.info("Applying schema.sql")
        try:
            conn.execute("BEGIN")
            execute_script(conn, schema_sql, description="schema.sql")
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            logger.error("Failed to apply schema.sql")
            raise from_sqlite_error(exc) from exc

        # Apply seed data in a transaction
        logger.info("Applying seed_data.sql")
        try:
            conn.execute("BEGIN")
            execute_script(conn, seed_sql, description="seed_data.sql")
            _set_schema_version(conn, CURRENT_SCHEMA_VERSION)
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            logger.error("Failed to apply seed_data.sql")
            raise from_sqlite_error(exc) from exc

        logger.info("Database rebuild initialization complete (schema_version=%s)", CURRENT_SCHEMA_VERSION)
    finally:
        conn.close()


def rebuild_database(db_path: Path | None = None) -> None:
    """Delete and rebuild a database from scratch.

    Performs a safe deletion (with WAL checkpoint) followed by initialization
    with schema and seed data. This is the atomic rebuild operation that ensures
    a clean, fresh database.

    Args:
        db_path: Path to SQLite database file. Defaults to global config.

    Raises:
        DatabaseLockedError: If deletion fails because database is in use.
        FileNotFoundError: If schema.sql or seed_data.sql doesn't exist.
        DatabaseError: If initialization fails.

    Logs:
        - INFO: "Rebuilding database" at start.
        - Delegates to delete_database and init_database_for_rebuild for detailed logging.

    Side Effects:
        - Deletes existing database files (.db, -wal, -shm).
        - Creates fresh database with schema and seed data.
    """
    logger.info("Rebuilding database")
    delete_database(db_path=db_path)
    init_database_for_rebuild(db_path=db_path)


