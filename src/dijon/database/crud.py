"""Generic CRUD helpers built on top of the low-level query helpers.

These functions operate on table names and dict-like row data and are
intended to stay low-level and generic. They do *not* open or close
connections; callers are responsible for providing a connection and
managing transaction boundaries.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Any, Mapping

from ..utils.time import now_ts_utc_z

from . import queries
from .errors import from_sqlite_error

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """Return current UTC time as canonical instant string.

    Returns:
        Canonical instant string: YYYY-MM-DDTHH:MM:SSZ.
    """
    return now_ts_utc_z()


def _validate_identifier(name: str) -> None:
    """Validate SQL identifier to prevent injection.

    Checks that identifier contains only alphanumeric characters and
    underscores. This is a basic safeguard, not comprehensive protection.

    Args:
        name: SQL identifier (table or column name) to validate.

    Raises:
        ValueError: If identifier contains unsafe characters.
    """
    if not name.replace("_", "").isalnum():
        msg = f"Unsafe SQL identifier: {name!r}"
        raise ValueError(msg)


def insert(
    conn: sqlite3.Connection,
    table: str,
    data: Mapping[str, Any],
) -> dict[str, Any]:
    """Insert a single record into table and return the inserted data.

    Automatically adds created_at and updated_at timestamps if they are
    not present in data. Validates table name for safety.

    Args:
        conn: Database connection (caller manages transaction).
        table: Table name to insert into.
        data: Column name to value mapping for the new record.

    Returns:
        Dictionary containing the inserted data (including auto-added
        timestamps).

    Raises:
        ValueError: If table name is invalid.
        IntegrityError: If constraint violation occurs.
        DatabaseError: If database operation fails.

    Logs:
        - DEBUG: "Inserted record into {table}" on success.

    Side Effects:
        - Inserts row into database table.
    """
    _validate_identifier(table)
    payload = dict(data)
    now = _now_iso()
    payload.setdefault("created_at", now)
    payload.setdefault("updated_at", now)

    columns = ", ".join(payload.keys())
    placeholders = ", ".join("?" for _ in payload)
    sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"  # noqa: S608

    try:
        queries.execute_update(conn, sql, tuple(payload.values()))
        logger.debug("Inserted record into %s", table)
        # For now, return the payload we inserted; callers can re-query if needed.
        return payload
    except sqlite3.Error as exc:
        raise from_sqlite_error(exc) from exc


def select(
    conn: sqlite3.Connection,
    table: str,
    filters: Mapping[str, Any] | None = None,
    *,
    order_by: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Select rows from table using simple equality filters.

    Builds a SELECT query with WHERE clauses for each filter (ANDed together),
    optional ORDER BY, and optional LIMIT. All identifiers are validated.

    Args:
        conn: Database connection.
        table: Table name to query.
        filters: Column name to value mapping for WHERE clauses. All
            conditions are ANDed together with equality checks.
        order_by: Column name to sort by (optional).
        limit: Maximum number of rows to return (optional).

    Returns:
        List of dictionaries, one per row, with column names as keys.

    Raises:
        ValueError: If table, column names, or order_by are invalid.
        DatabaseError: If database operation fails.
    """
    _validate_identifier(table)
    where_clauses: list[str] = []
    params: list[Any] = []

    if filters:
        for col, value in filters.items():
            _validate_identifier(col)
            where_clauses.append(f"{col} = ?")
            params.append(value)

    sql = f"SELECT * FROM {table}"  # noqa: S608
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    if order_by:
        _validate_identifier(order_by)
        sql += f" ORDER BY {order_by}"

    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)

    try:
        return queries.fetch_all(conn, sql, tuple(params))
    except sqlite3.Error as exc:
        raise from_sqlite_error(exc) from exc


def update(
    conn: sqlite3.Connection,
    table: str,
    filters: Mapping[str, Any],
    values: Mapping[str, Any],
) -> int:
    """Update rows in table matching filters with values.

    Updates all rows matching the filter conditions. Automatically updates
    updated_at timestamp. Requires at least one filter to prevent accidental
    full-table updates.

    Args:
        conn: Database connection (caller manages transaction).
        table: Table name to update.
        filters: Column name to value mapping for WHERE clauses. Must not
            be empty.
        values: Column name to value mapping for SET clauses.

    Returns:
        Number of rows affected by the update.

    Raises:
        ValueError: If table/column names are invalid or filters is empty.
        DatabaseError: If database operation fails.

    Side Effects:
        - Updates matching rows in database.
        - Sets updated_at timestamp on all updated rows.
    """
    _validate_identifier(table)
    if not filters:
        msg = "Refusing to perform UPDATE with no filters"
        raise ValueError(msg)

    payload = dict(values)
    payload["updated_at"] = _now_iso()

    set_clauses: list[str] = []
    params: list[Any] = []
    for col, value in payload.items():
        _validate_identifier(col)
        set_clauses.append(f"{col} = ?")
        params.append(value)

    where_clauses: list[str] = []
    for col, value in filters.items():
        _validate_identifier(col)
        where_clauses.append(f"{col} = ?")
        params.append(value)

    sql = f"UPDATE {table} SET " + ", ".join(set_clauses)  # noqa: S608
    sql += " WHERE " + " AND ".join(where_clauses)

    try:
        return queries.execute_update(conn, sql, tuple(params))
    except sqlite3.Error as exc:
        raise from_sqlite_error(exc) from exc


def delete(
    conn: sqlite3.Connection,
    table: str,
    filters: Mapping[str, Any],
) -> int:
    """Delete rows in table matching filters.

    Deletes all rows matching the filter conditions. Requires at least one
    filter to prevent accidental full-table deletes.

    Args:
        conn: Database connection (caller manages transaction).
        table: Table name to delete from.
        filters: Column name to value mapping for WHERE clauses. Must not
            be empty.

    Returns:
        Number of rows deleted.

    Raises:
        ValueError: If table/column names are invalid or filters is empty.
        DatabaseError: If database operation fails.

    Side Effects:
        - Deletes matching rows from database.
    """
    _validate_identifier(table)
    if not filters:
        msg = "Refusing to perform DELETE with no filters"
        raise ValueError(msg)

    where_clauses: list[str] = []
    params: list[Any] = []
    for col, value in filters.items():
        _validate_identifier(col)
        where_clauses.append(f"{col} = ?")
        params.append(value)

    sql = f"DELETE FROM {table} WHERE " + " AND ".join(where_clauses)  # noqa: S608

    try:
        return queries.execute_update(conn, sql, tuple(params))
    except sqlite3.Error as exc:
        raise from_sqlite_error(exc) from exc


def log_import_run(
    conn: sqlite3.Connection,
    *,
    operation: str,
    source: str | None = None,
    tables_written: list[str],
    data_range_start: str | None = None,
    data_range_end: str | None = None,
    started_at: str,
    ended_at: str | None = None,
    status: str = "success",
    rows_inserted: int | None = None,
    rows_updated: int | None = None,
    rows_deleted: int | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Log an import run or internal process execution to import_run_log table.

    This function records metadata about import operations (transactions, receipts,
    screentime, etc.) and internal processes (dedupe, clean, calculate) that
    modify data in the database. Use this to track when data was imported, what
    date ranges are covered, and which tables were affected.

    Example usage:
        from . import get_connection, transaction, log_import_run
        from datetime import UTC, datetime
        import uuid

        started = datetime.now(UTC).isoformat()
        # ... perform import operation ...
        ended = datetime.now(UTC).isoformat()

        with transaction() as conn:
            log_import_run(
                conn,
                operation="import",
                source="transactions",
                tables_written=["transactions", "accounts"],
                data_range_start="2025-01-01",
                data_range_end="2025-01-31",
                started_at=started,
                ended_at=ended,
                status="success",
                rows_inserted=150,
            )

    Args:
        conn: Database connection (caller manages transaction).
        operation: Type of operation: 'import', 'dedupe', 'clean', 'calculate'.
        source: Data source identifier (e.g., 'transactions', 'receipts',
            'screentime'). NULL for internal-only operations.
        tables_written: List of table names that were modified. Stored as JSON array.
        data_range_start: ISO-8601 date (YYYY-MM-DD) of earliest record in batch.
        data_range_end: ISO-8601 date (YYYY-MM-DD) of latest record in batch.
        started_at: ISO-8601 datetime when operation began.
        ended_at: ISO-8601 datetime when operation finished. NULL if still
            in-progress or crashed.
        status: Operation status: 'success', 'failed', 'partial'. Defaults to 'success'.
        rows_inserted: Number of rows inserted (optional).
        rows_updated: Number of rows updated (optional).
        rows_deleted: Number of rows deleted, useful for dedupe/cleanup ops (optional).
        meta: Additional context as dictionary, stored as JSON (optional).

    Returns:
        Dictionary containing the logged import run data.

    Raises:
        ValueError: If operation or status values are invalid.
        DatabaseError: If database operation fails.

    Logs:
        - DEBUG: "Logged import run: {operation} from {source}" on success.

    Side Effects:
        - Inserts row into import_run_log table.
    """
    if operation not in ("import", "dedupe", "clean", "calculate"):
        msg = f"Invalid operation: {operation}. Must be one of: import, dedupe, clean, calculate"
        raise ValueError(msg)

    if status not in ("success", "failed", "partial"):
        msg = f"Invalid status: {status}. Must be one of: success, failed, partial"
        raise ValueError(msg)

    log_entry = {
        "id": str(uuid.uuid4()),
        "operation": operation,
        "source": source,
        "tables_written": json.dumps(tables_written),
        "data_range_start": data_range_start,
        "data_range_end": data_range_end,
        "started_at": started_at,
        "ended_at": ended_at,
        "status": status,
        "rows_inserted": rows_inserted,
        "rows_updated": rows_updated,
        "rows_deleted": rows_deleted,
        "meta": json.dumps(meta) if meta else None,
        "created_at": _now_iso(),
    }

    try:
        result = insert(conn, "import_run_log", log_entry)
        logger.debug("Logged import run: %s from %s", operation, source or "internal")
        return result
    except sqlite3.Error as exc:
        raise from_sqlite_error(exc) from exc


