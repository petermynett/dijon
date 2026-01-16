"""CLI commands for Reaper project operations."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ...reaper.markers_session import create_markers_session, read_all_markers, read_markers
from ..base import BaseCLI, handle_errors

app = typer.Typer(
    name="reaper",
    help="Reaper project operations",
)


@app.command("create-markers")
def create_markers_command(
    audio_file: Annotated[
        Path,
        typer.Argument(help="Path to source RAW audio file"),
    ],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate the operation without writing files"),
    ] = False,
    open_session: Annotated[
        bool,
        typer.Option("--open/--no-open", help="Open the session in REAPER after creation"),
    ] = True,
) -> None:
    """Create a new Reaper markers session from a RAW audio file.

    Generates a new Reaper project file at markers/<audio-stem>_markers.RPP
    that references the original audio file via absolute path (no copying).
    """
    cli = BaseCLI("reaper")

    def _create() -> dict:
        result = create_markers_session(
            audio_file=audio_file,
            dry_run=dry_run,
            open_session=open_session and not dry_run,
        )
        return result

    cli.handle_cli_operation(
        operation="create-markers",
        op_callable=_create,
        pre_message=f"Creating markers session for {audio_file.name}..." if not dry_run else None,
    )


@app.command("read-markers")
def read_markers_command(
    rpp_file: Annotated[
        Path | None,
        typer.Argument(help="Path to Reaper project (.RPP) file. If not provided, processes all RPP files in reaper/markers"),
    ] = None,
) -> None:
    """Read marker data from Reaper project file(s).

    If rpp_file is provided, parses markers from that file.
    If not provided, searches reaper/markers for all *.RPP files and processes each.
    Writes JSON output to data/audio-markers (overwrites existing files).
    """
    cli = BaseCLI("reaper")

    def _read() -> dict:
        if rpp_file is None:
            result = read_all_markers()
        else:
            result = read_markers(rpp_file=rpp_file)
        return result

    if rpp_file is None:
        pre_message = "Reading markers from all RPP files in markers directory..."
    else:
        pre_message = f"Reading markers from {rpp_file.name}..."

    cli.handle_cli_operation(
        operation="read-markers",
        op_callable=_read,
        pre_message=pre_message,
    )
