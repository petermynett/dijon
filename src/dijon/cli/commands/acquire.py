"""CLI command for acquisition operations."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ...global_config import ACQUISITION_DIR, DATA_DIR
from ...pipeline.acquire.youtube import acquire
from ..base import BaseCLI

app = typer.Typer(
    name="acquire",
    help="Acquisition operations",
)


@app.command("youtube")
def acquire_youtube(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate the operation without writing files, showing what would be processed"),
    ] = False,
) -> None:
    """Acquire manifest entries for YouTube bundles.

    Scans already-downloaded YouTube files in data/acquisition/youtube/ and
    creates manifest entries for each asset (mp3, jpg, json, optional mp4).
    """
    cli = BaseCLI("youtube")

    def _acquire() -> dict:
        acquisition_dir = ACQUISITION_DIR / "youtube"
        manifest_path = acquisition_dir / "manifest.csv"

        result = acquire(
            acquisition_dir=acquisition_dir,
            manifest_path=manifest_path,
            data_dir=DATA_DIR,
            dry_run=dry_run,
        )
        return result

    cli.handle_cli_operation(
        operation="acquire",
        op_callable=_acquire,
        pre_message="[DRY RUN] Would acquire manifest entries for YouTube bundles..." if dry_run else "Acquiring manifest entries for YouTube bundles...",
    )
