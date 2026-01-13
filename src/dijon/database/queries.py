"""Basic query execution helpers.

These wrap low-level sqlite3 operations with logging and typed return
shapes used by higher-level CRUD helpers.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)


def execute_query(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple | dict | None = None,
) -> sqlite3.Cursor:
    """Execute a SQL query and return the cursor.

    Low-level helper that executes SQL with optional parameters and returns
    the cursor for result processing.

    Args:
        conn: Database connection.
        sql: SQL query string.
        params: Query parameters (tuple or dict). Defaults to empty tuple.

    Returns:
        SQLite cursor with query results.

    Raises:
        sqlite3.Error: If query execution fails.

    Logs:
        - DEBUG: "Executed query: {sql[:80]}" on success.
        - ERROR: "Query execution failed: {exc}" with exception details on failure.
    """
    try:
        cursor = conn.execute(sql, params or ())
        logger.debug("Executed query: %s", sql[:80])
        return cursor
    except sqlite3.Error as exc:
        logger.exception("Query execution failed: %s", exc)
        raise


def fetch_one(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple | dict | None = None,
) -> dict[str, Any] | None:
    """Execute query and return single row as dict, or None if no results.

    Executes a query expected to return at most one row. Returns None if
    no rows match.

    Args:
        conn: Database connection.
        sql: SQL query string.
        params: Query parameters (tuple or dict). Defaults to empty tuple.

    Returns:
        Dictionary with column names as keys, or None if no row found.

    Raises:
        sqlite3.Error: If query execution fails.
    """
    cursor = execute_query(conn, sql, params)
    row = cursor.fetchone()
    if row is None:
        return None
    return dict(row)


def fetch_all(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple | dict | None = None,
) -> list[dict[str, Any]]:
    """Execute query and return all rows as list of dicts.

    Executes a query and returns all matching rows as a list of dictionaries.

    Args:
        conn: Database connection.
        sql: SQL query string.
        params: Query parameters (tuple or dict). Defaults to empty tuple.

    Returns:
        List of dictionaries, one per row, with column names as keys.
        Empty list if no rows match.

    Raises:
        sqlite3.Error: If query execution fails.
    """
    cursor = execute_query(conn, sql, params)
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def execute_update(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple | dict | None = None,
) -> int:
    """Execute INSERT/UPDATE/DELETE and return number of affected rows.

    Executes a write operation (INSERT, UPDATE, or DELETE) and returns
    the number of rows affected.

    Args:
        conn: Database connection.
        sql: SQL statement (INSERT, UPDATE, or DELETE).
        params: Query parameters (tuple or dict). Defaults to empty tuple.

    Returns:
        Number of rows affected by the operation.

    Raises:
        sqlite3.Error: If statement execution fails.

    Logs:
        - DEBUG: "Update affected {rowcount} rows" on success.
    """
    cursor = execute_query(conn, sql, params)
    rowcount = cursor.rowcount
    logger.debug("Update affected %s rows", rowcount)
    return rowcount


