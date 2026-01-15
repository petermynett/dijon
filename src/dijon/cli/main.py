from __future__ import annotations

from typing import Annotated

import typer

from .base import configure_logging, format_result
from .commands.acquire import app as acquire_app
from .commands.db import app as db_app
from .commands.example import app as example_app
from .commands.tree import tree_command

configure_logging()
app = typer.Typer(
    help="Project CLI",
    context_settings={"help_option_names": ["-h", "--help"]},
)

app.add_typer(acquire_app, name="acquire")
app.add_typer(db_app, name="db")
app.add_typer(example_app, name="example")


@app.command("tree")
def tree(
    filter_verb: Annotated[
        str | None,
        typer.Option(
            "-f",
            "--filter",
            help="Filter by verb (e.g., 'acquire', 'load', 'sources')",
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show descriptions and options"),
    ] = False,
) -> None:
    """Display all CLI commands in a hierarchical tree.

    Shows the complete command structure of the CLI in a tree format.
    By default shows only command names (compact mode). Use --verbose to see
    descriptions and options. Supports filtering by verb (e.g., 'acquire', 'load')
    or showing only source commands (use '-f sources').

    Args:
        filter_verb: Optional verb to filter by (e.g., 'acquire', 'load', 'sources').
        verbose: If True, show help text and options (default is compact mode).
    """
    tree_command(typer_app=app, filter_verb=filter_verb, verbose=verbose)


def main() -> None:
    """Main entry point for package CLI.

    Invokes the Typer application, which handles command parsing and
    execution.

    Side Effects:
        - Processes CLI arguments and executes commands.
        - May exit with non-zero code on errors.
    """
    app()


if __name__ == "__main__":
    main()

