"""Database-specific exception types for the project."""

from __future__ import annotations

import sqlite3
from typing import Any


class DatabaseError(Exception):
    """Base exception for database-related errors."""


class IntegrityError(DatabaseError):
    """Raised when a constraint violation occurs."""


class NotFoundError(DatabaseError):
    """Raised when a requested row cannot be found."""


def from_sqlite_error(error: sqlite3.Error) -> DatabaseError:
    """Map a raw sqlite3 error to a project-level DatabaseError.

    Converts sqlite3 exceptions to project-specific exception types.
    IntegrityError is mapped to IntegrityError, all others to DatabaseError.

    Args:
        error: SQLite exception to convert.

    Returns:
        DatabaseError or IntegrityError instance with error message.
    """
    if isinstance(error, sqlite3.IntegrityError):
        return IntegrityError(str(error))
    return DatabaseError(str(error))


def ensure_found(row: Any, message: str = "Row not found") -> Any:
    """Raise NotFoundError if a row is missing, otherwise return it.

    Helper for functions that expect a single row result. Raises NotFoundError
    if the row is None, otherwise returns the row unchanged.

    Args:
        row: Row result to check (may be None).
        message: Error message to use if row is None.

    Returns:
        The row value if it's not None.

    Raises:
        NotFoundError: If row is None.
    """
    if row is None:
        raise NotFoundError(message)
    return row


