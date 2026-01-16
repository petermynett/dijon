"""Example CLI commands demonstrating the acquire→ingest→load pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ...pipeline.acquire.example import acquire
from ...pipeline.ingest.example import ingest
from ...pipeline.load.example import load
from ...sources.example import get_source
from ..base import BaseCLI, format_result, handle_errors

app = typer.Typer(
    name="example",
    help="Example source commands (acquire, ingest, load)",
)


@app.command("acquire")
def acquire_command(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate the operation without writing files"),
    ] = False,
) -> None:
    """Acquire upstream data for the example source.
    
    Fetches data from upstream and writes it to the acquisition layer.
    """
    cli = BaseCLI("example")
    
    def _acquire() -> dict:
        source = get_source()
        acquisition_dir = source.get_acquisition_dir()
        
        result = acquire(
            source_key=source.source_key,
            acquisition_dir=acquisition_dir,
            dry_run=dry_run,
        )
        return result
    
    cli.handle_cli_operation(
        operation="acquire",
        op_callable=_acquire,
        pre_message="Acquiring data for example source..." if not dry_run else None,
    )


@app.command("ingest")
def ingest_command(
    acquisition_file: Annotated[
        Path,
        typer.Argument(help="Path to acquisition file to ingest"),
    ],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate the operation without writing files"),
    ] = False,
) -> None:
    """Ingest an acquisition file into the canonical raw layer.
    
    Canonicalizes acquisition data and writes it to raw/ with a manifest entry.
    This command is idempotent: re-running with the same acq_sha256 will no-op.
    """
    cli = BaseCLI("example")
    
    def _ingest() -> dict:
        source = get_source()
        raw_dir = source.get_raw_dir()
        manifest_path = source.get_manifest_path()
        
        result = ingest(
            source_key=source.source_key,
            dataset_code=source.dataset_code,
            acquisition_file=acquisition_file,
            raw_dir=raw_dir,
            manifest_path=manifest_path,
            dry_run=dry_run,
        )
        
        # Handle idempotent no-op case
        if result.get("already_ingested"):
            typer.echo(f"✓ {result.get('message', 'already ingested')}")
            return result
        
        return result
    
    with handle_errors("ingest", logger=cli.logger):
        result = _ingest()
        typer.echo(format_result(result, operation="ingest"))


@app.command("load")
def load_command(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate the operation without reading files"),
    ] = False,
) -> None:
    """Load and validate canonical raw files for the example source.
    
    Resolves effective raw files (raw + overriding annotations precedence) and validates
    manifest integrity. Does not write canonical data.
    """
    cli = BaseCLI("example")
    
    def _load() -> dict:
        source = get_source()
        raw_dir = source.get_raw_dir()
        annotations_dir = source.get_annotations_dir()
        manifest_path = source.get_manifest_path()
        
        result = load(
            source_key=source.source_key,
            raw_dir=raw_dir,
            annotations_dir=annotations_dir,
            manifest_path=manifest_path,
            dry_run=dry_run,
        )
        return result
    
    cli.handle_cli_operation(
        operation="load",
        op_callable=_load,
        pre_message="Loading and validating files for example source..." if not dry_run else None,
    )

