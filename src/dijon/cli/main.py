from __future__ import annotations

import typer

from .base import configure_logging
from .commands.acquire import app as acquire_app
from .commands.ingest import app as ingest_app
from .commands.reaper import app as reaper_app

configure_logging()
app = typer.Typer(
    help="Project CLI",
    context_settings={"help_option_names": ["-h", "--help"]},
)

app.add_typer(acquire_app, name="acquire")
app.add_typer(ingest_app, name="ingest")
app.add_typer(reaper_app, name="reaper")


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

