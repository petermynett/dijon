"""CLI command for meter computation from beat times."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ...pipeline.meter import (
    BEATS_DIR,
    METER_OUTPUT_DIR,
    run_meter,
)
from ..base import BaseCLI

app = typer.Typer(
    name="meter",
    help="Compute meter labels from beats .npy and write to data/derived/meter",
)


@app.callback(invoke_without_command=True)
def meter(
    files: Annotated[
        list[Path],
        typer.Argument(
            help="Beats .npy file(s) to process. If omitted, all .npy in data/derived/beats are used.",
        ),
    ] = [],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be written without writing files."),
    ] = False,
) -> None:
    """Compute meter labels for beat files and write to data/derived/meter.

    Tracks without HEAD_IN_START marker are skipped. Output: <track_name>_meter.npy
    """
    cli = BaseCLI("meter")

    beats_list = list(files) if files else None

    def _run() -> dict:
        return run_meter(
            beats_files=beats_list,
            output_dir=METER_OUTPUT_DIR,
            beats_dir=BEATS_DIR,
            dry_run=dry_run,
        )

    pre_message = (
        "Computing meter (dry-run; no files will be written)..."
        if dry_run
        else f"Computing meter for "
        + (f"{len(beats_list)} file(s)..." if beats_list else "all beats files in folder...")
    )
    cli.handle_cli_operation(
        operation="meter",
        op_callable=_run,
        pre_message=pre_message,
    )
