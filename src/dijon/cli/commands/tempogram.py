"""CLI command for tempogram computation from novelty .npy files."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ...pipeline.tempogram import NOVELTY_DIR, TEMPOGRAM_OUTPUT_DIR, run_tempogram
from ..base import BaseCLI

app = typer.Typer(
    name="tempogram",
    help="Compute tempograms from novelty .npy and write to data/derived/tempogram",
)


@app.callback(invoke_without_command=True)
def tempogram(
    files: Annotated[
        list[Path],
        typer.Argument(
            help="Novelty .npy file(s) to process. If omitted, all .npy in data/derived/novelty are used.",
        ),
    ] = [],
    type: Annotated[
        str,
        typer.Option("--type", "-t", help="Tempogram type: fourier, autocorr, cyclic. Default: fourier."),
    ] = "fourier",
    n: Annotated[
        int | None,
        typer.Option("--n", "-N", help="Window length N (novelty samples). Uses type default if not set."),
    ] = None,
    h: Annotated[
        int | None,
        typer.Option("--h", "-H", help="Hop size H. Uses type default if not set."),
    ] = None,
    theta_min: Annotated[
        int | None,
        typer.Option("--theta-min", help="Minimum tempo (BPM). Default 40."),
    ] = None,
    theta_max: Annotated[
        int | None,
        typer.Option("--theta-max", help="Maximum tempo (BPM). Default 320."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be written without writing files."),
    ] = False,
) -> None:
    """Compute tempograms for novelty files (assumed 100 Hz) and write to data/derived/tempogram.

    Output filenames: <track_name>_tempogram_<type>_<N>-<H>-<theta_min>-<theta_max>.npy
    Cyclic type is computed from fourier tempogram in the same run.
    """
    cli = BaseCLI("tempogram")

    novelty_list = list(files) if files else None

    def _run() -> dict:
        return run_tempogram(
            novelty_files=novelty_list,
            output_dir=TEMPOGRAM_OUTPUT_DIR,
            novelty_dir=NOVELTY_DIR,
            ntype=type.lower(),
            N=n,
            H=h,
            theta_min=theta_min,
            theta_max=theta_max,
            dry_run=dry_run,
        )

    pre_message = (
        "Computing tempogram (dry-run; no files will be written)..."
        if dry_run
        else f"Computing {type} tempogram for "
        + (f"{len(novelty_list)} file(s)..." if novelty_list else "all novelty files in folder...")
    )
    cli.handle_cli_operation(
        operation="tempogram",
        op_callable=_run,
        pre_message=pre_message,
    )
