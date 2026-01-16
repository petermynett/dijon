"""CLI command for ingestion operations."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ...global_config import ACQUISITION_DIR, DATA_DIR, RAW_DIR
from ...pipeline.ingest.youtube import ingest
from ..base import BaseCLI

app = typer.Typer(
    name="ingest",
    help="Ingestion operations",
)


@app.command("youtube")
def ingest_youtube(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate the operation without writing files"),
    ] = False,
) -> None:
    """Ingest YouTube acquisition MP3s into the raw layer.

    Scans YouTube acquisition files and copies MP3s to data/raw/audio/
    with manifest entries. This command is idempotent: re-running will
    skip already-ingested files.
    """
    cli = BaseCLI("youtube")

    def _ingest() -> dict:
        acquisition_dir = ACQUISITION_DIR / "youtube"
        raw_dir = RAW_DIR / "audio"
        raw_manifest_path = raw_dir / "manifest.csv"
        acquisition_manifest_path = acquisition_dir / "manifest.csv"

        result = ingest(
            acquisition_dir=acquisition_dir,
            raw_dir=raw_dir,
            raw_manifest_path=raw_manifest_path,
            acquisition_manifest_path=acquisition_manifest_path,
            data_dir=DATA_DIR,
            dry_run=dry_run,
        )
        return result

    cli.handle_cli_operation(
        operation="ingest",
        op_callable=_ingest,
        pre_message="Ingesting YouTube MP3s into raw layer..." if not dry_run else None,
    )
