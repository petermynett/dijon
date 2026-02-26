"""CLI command for novelty function computation."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ...global_config import RAW_AUDIO_DIR
from ...pipeline.novelty import NOVELTY_OUTPUT_DIR, run_novelty
from ..base import BaseCLI

app = typer.Typer(
    name="novelty",
    help="Compute novelty functions from raw audio and write .npy to data/derived/novelty",
)


@app.callback(invoke_without_command=True)
def novelty(
    files: Annotated[
        list[Path],
        typer.Argument(
            help="Audio file(s) to process. If omitted, all .wav files in data/datasets/raw/audio are used.",
        ),
    ] = [],
    type: Annotated[
        str,
        typer.Option("--type", "-t", help="Novelty type: spectrum, energy, phase, complex. Default: spectrum."),
    ] = "spectrum",
    n: Annotated[
        int | None,
        typer.Option("--n", "-N", help="Window/FFT size N. Uses type default if not set."),
    ] = None,
    h: Annotated[
        int | None,
        typer.Option("--h", "-H", help="Hop size H. Uses type default if not set."),
    ] = None,
    gamma: Annotated[
        float | None,
        typer.Option("--gamma", "-g", help="Log compression gamma. Uses type default if not set."),
    ] = None,
    m: Annotated[
        int | None,
        typer.Option("--m", "-M", help="Local average context M. Uses type default if not set."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be written without writing files."),
    ] = False,
    no_log: Annotated[
        bool,
        typer.Option("--no-log", help="Do not write a log file to data/logs/derived."),
    ] = False,
    start_marker: Annotated[
        str | None,
        typer.Option("--start-marker", "-s", help="Start marker name. Default: earliest marker."),
    ] = None,
    end_marker: Annotated[
        str | None,
        typer.Option("--end-marker", "-e", help="End marker name. Default: END."),
    ] = None,
) -> None:
    """Compute novelty functions from raw audio and write to data/derived/novelty.

    By default, trims to the musical region (earliest marker → END) using Reaper
    marker JSONs. Use --start-marker and --end-marker to override.

    Output filenames: <track-name>_novelty_<type>_<N>-<H>-<gamma>-<M>.npy
    Same parameters overwrite; different parameters produce different files.
    """
    cli = BaseCLI("novelty")

    # Normalize: empty list of files means "use default folder"
    audio_list = list(files) if files else None

    def _run() -> dict:
        return run_novelty(
            audio_files=audio_list,
            output_dir=NOVELTY_OUTPUT_DIR,
            raw_audio_dir=RAW_AUDIO_DIR,
            ntype=type.lower(),
            N=n,
            H=h,
            gamma=gamma,
            M=m,
            dry_run=dry_run,
            start_marker=start_marker,
            end_marker=end_marker,
        )

    pre_message = (
        "Computing novelty (dry-run; no files will be written)..."
        if dry_run
        else f"Computing {type} novelty for "
        + (f"{len(audio_list)} file(s)..." if audio_list else "all audio in raw folder...")
    )
    inputs_desc = (
        str([str(p) for p in audio_list]) if audio_list
        else f"all .wav in {RAW_AUDIO_DIR}"
    )
    cli.handle_cli_operation(
        operation="novelty",
        op_callable=_run,
        pre_message=pre_message,
        log_module="novelty",
        log_method=type.lower(),
        log_dry_run=dry_run,
        enable_log=not no_log,
        log_context={
            "inputs": inputs_desc,
            "output_dir": str(NOVELTY_OUTPUT_DIR),
        },
    )
