"""CLI commands for database management."""

from pathlib import Path
from typing import Annotated, Any

import typer

from ..base import BaseCLI
from ...database import delete_database, rebuild_database

db_app = typer.Typer(help="Database management commands.")


class DatabaseCLI(BaseCLI):
    """CLI helpers for database management."""

    def __init__(self) -> None:
        """Initialize DatabaseCLI with db domain name."""
        super().__init__("db")

    def delete_db(
        self,
        *,
        db_path: Path | None,
    ) -> dict[str, Any]:
        """Delete database using CLI operation handler.

        Safely deletes the database file and associated WAL/SHM files after
        attempting a clean shutdown (WAL checkpoint). Returns a standardized
        result dictionary.

        Args:
            db_path: Path to SQLite database. Defaults to global config.

        Returns:
            Standardized delete result dictionary with success status.

        User Output:
            - "Deleting database..." pre-message.
            - Formatted result via BaseCLI.handle_cli_operation.

        Logs:
            - Delegates to delete_database and handle_cli_operation.
        """
        return self.handle_cli_operation(
            operation="db delete",
            op_callable=lambda: self._delete_operation(db_path=db_path),
            pre_message="Deleting database...",
        )

    def rebuild_db(
        self,
        *,
        db_path: Path | None,
    ) -> dict[str, Any]:
        """Rebuild database using CLI operation handler.

        Deletes the existing database (if present) and creates a fresh one
        with schema and seed data. Returns a standardized result dictionary.

        Args:
            db_path: Path to SQLite database. Defaults to global config.

        Returns:
            Standardized rebuild result dictionary with success status.

        User Output:
            - "Rebuilding database..." pre-message.
            - Formatted result via BaseCLI.handle_cli_operation.

        Logs:
            - Delegates to rebuild_database and handle_cli_operation.
        """
        return self.handle_cli_operation(
            operation="db rebuild",
            op_callable=lambda: self._rebuild_operation(db_path=db_path),
            pre_message="Rebuilding database...",
        )

    def _delete_operation(self, *, db_path: Path | None) -> dict[str, Any]:
        """Internal delete operation that returns standardized result.

        Converts domain function result (None on success) to a standardized dict.
        Exceptions are handled by handle_cli_operation via handle_errors.

        Args:
            db_path: Path to SQLite database.

        Returns:
            Dictionary with success status and message.

        Raises:
            DatabaseLockedError: If database is in use (handled by handle_cli_operation).
            OSError: If deletion fails for other reasons (handled by handle_cli_operation).
        """
        delete_database(db_path=db_path)
        return {"success": True, "message": "Database deleted successfully"}

    def _rebuild_operation(self, *, db_path: Path | None) -> dict[str, Any]:
        """Internal rebuild operation that returns standardized result.

        Converts domain function result (None on success) to a standardized dict.
        Exceptions are handled by handle_cli_operation via handle_errors.

        Args:
            db_path: Path to SQLite database.

        Returns:
            Dictionary with success status and message.

        Raises:
            DatabaseLockedError: If database is in use (handled by handle_cli_operation).
            FileNotFoundError: If SQL files are missing (handled by handle_cli_operation).
            DatabaseError: If initialization fails (handled by handle_cli_operation).
        """
        rebuild_database(db_path=db_path)
        return {"success": True, "message": "Database rebuilt successfully"}


cli = DatabaseCLI()


@db_app.command("delete")
def delete_command(
    db_path: Annotated[
        Path | None,
        typer.Option(
            "--db-path",
            help="Path to SQLite database file (defaults to global config)",
        ),
    ] = None,
) -> None:
    """Safely delete the database and associated WAL/SHM files.

    Performs a best-effort clean shutdown by checkpointing the WAL, then
    deletes the database file and any associated WAL/SHM files. If deletion
    fails because the database is in use, exits with a clear error message
    instructing the user to close all processes using the database.

    Exits with code 1 if deletion fails (e.g., database is locked).
    """
    result = cli.delete_db(db_path=db_path)
    if not result.get("success"):
        raise typer.Exit(1)


@db_app.command("rebuild")
def rebuild_command(
    db_path: Annotated[
        Path | None,
        typer.Option(
            "--db-path",
            help="Path to SQLite database file (defaults to global config)",
        ),
    ] = None,
) -> None:
    """Delete and rebuild the database from scratch.

    Safely deletes the existing database (if present) and creates a fresh
    database with schema and seed data. The rebuild process:
    1. Deletes the database and WAL/SHM files (with clean shutdown)
    2. Creates a new database with WAL journal mode
    3. Applies schema.sql in a transaction
    4. Applies seed_data.sql in a transaction

    Exits with code 1 if rebuild fails (e.g., database is locked, SQL files
    missing, or SQL execution fails).
    """
    result = cli.rebuild_db(db_path=db_path)
    if not result.get("success"):
        raise typer.Exit(1)


app = db_app
