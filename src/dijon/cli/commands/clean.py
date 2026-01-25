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
def clean_pyc_command() -> None:
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
        result = clean_pyc(directories=directories)
        return result

    cli.handle_cli_operation(
        operation="clean pyc",
        op_callable=_clean,
        pre_message="Cleaning Python cache files from src/ and scripts/...",
    )


@app.command("reaper")
def clean_reaper_command() -> None:
    """Remove Reaper-generated artifacts and temporary files.

    Removes:
    - All *reapeaks files recursively in reaper/
    - Folders named "peaks" that contain reapeaks files
    - Backups/ and Media/ directories in reaper/examples/ and reaper/markers/
    - *.rpp files in reaper/ (root) and reaper/markers/ but NOT in reaper/examples/
    """
    cli = BaseCLI("clean")

    def _clean() -> dict:
        result = clean_reaper()
        return result

    cli.handle_cli_operation(
        operation="clean reaper",
        op_callable=_clean,
        pre_message="Cleaning Reaper artifacts...",
    )
