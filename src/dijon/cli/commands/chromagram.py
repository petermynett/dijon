"""CLI command for metric chromagram computation from audio and meter maps."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ...pipeline.chromagram import (
    CHROMAGRAM_OUTPUT_DIR,
    METER_DIR,
    run_chromagram,
)
from ...global_config import RAW_AUDIO_DIR
from ..base import BaseCLI

app = typer.Typer(
    name="chromagram",
    help="Compute metric chromagrams from audio + meter maps and write to data/derived/chromagram",
)


@app.callback(invoke_without_command=True)
def chromagram(
    files: Annotated[
        list[Path],
        typer.Argument(
            help="Audio .wav file(s) to process. If omitted, all .wav in data/datasets/raw/audio are used.",
        ),
    ] = [],
    chroma_type: Annotated[
        str,
        typer.Option("--chroma-type", "-t", help='Chroma backend: "cqt" or "stft". Default: cqt.'),
    ] = "cqt",
    hop_length: Annotated[
        int,
        typer.Option("--hop-length", "-H", help="Feature hop length in samples. Default: 256."),
    ] = 256,
    bpm_threshold: Annotated[
        float,
        typer.Option("--bpm-threshold", help="Adaptive subdivision threshold in BPM. Default: 180.0."),
    ] = 180.0,
    aggregate: Annotated[
        str,
        typer.Option("--aggregate", "-a", help='Aggregation mode: "mean" or "median". Default: mean.'),
    ] = "mean",
    accent_mode: Annotated[
        str,
        typer.Option(
            "--accent-mode",
            help='Accent handling: "preserve", "normalize", or "weighted". Default: preserve.',
        ),
    ] = "preserve",
    weight_source: Annotated[
        str,
        typer.Option("--weight-source", help='Weight source for weighted mode: "rms" or "onset". Default: rms.'),
    ] = "rms",
    weight_power: Annotated[
        float,
        typer.Option("--weight-power", help="Weight exponent for weighted mode. Default: 1.0."),
    ] = 1.0,
    min_frames_per_bin: Annotated[
        int,
        typer.Option("--min-frames-per-bin", help="Minimum frames required per subdivision bin. Default: 2."),
    ] = 2,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be written without writing files."),
    ] = False,
) -> None:
    """Compute metric chromagrams and write to data/derived/chromagram.

    Expects meter maps in data/derived/meter named <track_name>_meter.npy.
    Output filenames encode the main chromagram parameters.
    """
    cli = BaseCLI("chromagram")

    audio_list = list(files) if files else None

    def _run() -> dict:
        return run_chromagram(
            audio_files=audio_list,
            output_dir=CHROMAGRAM_OUTPUT_DIR,
            raw_audio_dir=RAW_AUDIO_DIR,
            meter_dir=METER_DIR,
            hop_length=hop_length,
            bpm_threshold=bpm_threshold,
            chroma_type=chroma_type.lower(),
            aggregate=aggregate.lower(),
            accent_mode=accent_mode.lower(),
            weight_source=weight_source.lower(),
            weight_power=weight_power,
            min_frames_per_bin=min_frames_per_bin,
            dry_run=dry_run,
        )

    pre_message = (
        "Computing chromagram (dry-run; no files will be written)..."
        if dry_run
        else "Computing metric chromagram for "
        + (f"{len(audio_list)} file(s)..." if audio_list else "all audio in raw folder...")
    )
    cli.handle_cli_operation(
        operation="chromagram",
        op_callable=_run,
        pre_message=pre_message,
    )
