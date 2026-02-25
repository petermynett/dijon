"""CLI command for beat tracking from tempogram and novelty .npy files."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ...pipeline.beats import (
    BEATS_OUTPUT_DIR,
    NOVELTY_DIR,
    TEMPOGRAM_DIR,
    run_beats,
)
from ..base import BaseCLI

app = typer.Typer(
    name="beats",
    help="Compute beat times from tempogram and novelty .npy and write to data/derived/beats",
)


@app.callback(invoke_without_command=True)
def beats(
    files: Annotated[
        list[Path],
        typer.Argument(
            help="Tempogram .npy file(s) to process. If omitted, all .npy in data/derived/tempogram are used.",
        ),
    ] = [],
    factor: Annotated[
        float,
        typer.Option("--factor", "-f", help="DP penalty factor. Default: 1.0."),
    ] = 1.0,
    theta_min: Annotated[
        int | None,
        typer.Option("--theta-min", help="Minimum tempo (BPM). Default: 40."),
    ] = None,
    theta_max: Annotated[
        int | None,
        typer.Option("--theta-max", help="Maximum tempo (BPM). Default: 320."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be written without writing files."),
    ] = False,
) -> None:
    """Compute beat times from tempogram and novelty files and write to data/derived/beats.

    For each tempogram, finds matching novelty by track name. Output: <track_name>_beats.npy
    """
    cli = BaseCLI("beats")

    tempogram_list = list(files) if files else None

    def _run() -> dict:
        return run_beats(
            tempogram_files=tempogram_list,
            output_dir=BEATS_OUTPUT_DIR,
            tempogram_dir=TEMPOGRAM_DIR,
            novelty_dir=NOVELTY_DIR,
            factor=factor,
            theta_min=theta_min,
            theta_max=theta_max,
            dry_run=dry_run,
        )

    pre_message = (
        "Computing beats (dry-run; no files will be written)..."
        if dry_run
        else f"Computing beats for "
        + (f"{len(tempogram_list)} file(s)..." if tempogram_list else "all tempogram files in folder...")
    )
    cli.handle_cli_operation(
        operation="beats",
        op_callable=_run,
        pre_message=pre_message,
    )
