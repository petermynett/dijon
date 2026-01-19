"""CLI command for set operations."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ...global_config import PROJECT_ROOT
from ...pipeline.sets import populate_set_yaml
from ...utils.sets import resolve_set_path
from ..base import BaseCLI

app = typer.Typer(
    name="sets",
    help="Set operations",
)


@app.command("populate")
def populate_set(
    set_ref: Annotated[
        str,
        typer.Argument(help="Set reference (name like 'leading' or path like 'data/sets/leading.yaml')"),
    ],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate the operation without writing files"),
    ] = False,
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", help="Overwrite existing non-empty fields"),
    ] = False,
) -> None:
    """Populate set YAML items with metadata from manifests.

    Reads the set YAML file, loads manifests referenced by the `paths` field,
    and populates item fields (song_name, source_name, url) from manifest data.

    The set_ref can be:
    - A single word (e.g., "leading") → resolves to data/sets/<name>.yaml
    - A path (e.g., "data/sets/leading.yaml") → resolves relative to project root
    """
    cli = BaseCLI("sets")

    def _populate() -> dict:
        # Resolve set path
        set_path = resolve_set_path(set_ref, project_root=PROJECT_ROOT)

        # Call pipeline
        result = populate_set_yaml(
            set_path=set_path,
            project_root=PROJECT_ROOT,
            dry_run=dry_run,
            overwrite=overwrite,
        )
        return result

    cli.handle_cli_operation(
        operation="populate",
        op_callable=_populate,
        pre_message=f"Populating set from {set_ref}..." if not dry_run else None,
    )
