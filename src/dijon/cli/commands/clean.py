"""CLI command for cleaning operations."""

from __future__ import annotations

import typer

from ...global_config import PROJECT_ROOT
from ...pipeline.clean import clean_pyc, clean_reaper
from ..base import BaseCLI

app = typer.Typer(
    name="clean",
    help="Cleaning operations",
)


@app.command("pyc")
def clean_pyc_command(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be deleted without actually deleting files",
    ),
) -> None:
    """Remove all __pycache__ directories and *.pyc files.

    Recursively finds and deletes Python cache artifacts from the src/ and
    scripts/ directories. This command only affects files under these directories.
    """
    cli = BaseCLI("clean")

    def _clean() -> dict:
        directories = [
            PROJECT_ROOT / "src",
            PROJECT_ROOT / "scripts",
        ]
        result = clean_pyc(directories=directories, dry_run=dry_run)
        return result

    pre_message = (
        "Checking what would be cleaned (dry-run)..." if dry_run
        else "Cleaning Python cache files from src/ and scripts/..."
    )
    cli.handle_cli_operation(
        operation="clean pyc",
        op_callable=_clean,
        pre_message=pre_message,
    )


@app.command("reaper")
def clean_reaper_command(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be deleted without actually deleting files",
    ),
) -> None:
    """Remove Reaper-generated artifacts and temporary files.

    Removes:
    - All *reapeaks files recursively in reaper/
    - Folders named "peaks" that contain reapeaks files
    - Backups/ and Media/ directories in reaper/examples/ and reaper/markers/
    - *.rpp files in reaper/ (root) and reaper/markers/ but NOT in reaper/examples/
    """
    cli = BaseCLI("clean")

    def _clean() -> dict:
        result = clean_reaper(dry_run=dry_run)
        return result

    pre_message = (
        "Checking what would be cleaned (dry-run)..." if dry_run
        else "Cleaning Reaper artifacts..."
    )
    cli.handle_cli_operation(
        operation="clean reaper",
        op_callable=_clean,
        pre_message=pre_message,
    )
