"""Public interface for the database package.

This module exposes the main primitives needed by the rest of the
project: connection helpers, initialization entrypoints, and generic
CRUD utilities.
"""

from .connection import get_connection, transaction
from .init import (
    CURRENT_SCHEMA_VERSION,
    DatabaseLockedError,
    delete_database,
    initialize_database,
    rebuild_database,
)
from .crud import delete, insert, log_import_run, select, update

__all__ = [
    "get_connection",
    "transaction",
    "initialize_database",
    "delete_database",
    "rebuild_database",
    "DatabaseLockedError",
    "CURRENT_SCHEMA_VERSION",
    "insert",
    "select",
    "update",
    "delete",
    "log_import_run",
]


