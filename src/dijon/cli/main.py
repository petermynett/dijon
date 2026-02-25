from __future__ import annotations

import typer

from .base import configure_logging
from .commands.acquire import app as acquire_app
from .commands.beats import app as beats_app
from .commands.chromagram import app as chromagram_app
from .commands.clean import app as clean_app
from .commands.ingest import app as ingest_app
from .commands.meter import app as meter_app
from .commands.novelty import app as novelty_app
from .commands.reaper import app as reaper_app
from .commands.sets import app as sets_app
from .commands.tempogram import app as tempogram_app

configure_logging()
app = typer.Typer(
    help="Project CLI",
    context_settings={"help_option_names": ["-h", "--help"]},
)

app.add_typer(acquire_app, name="acquire")
app.add_typer(beats_app, name="beats")
app.add_typer(chromagram_app, name="chromagram")
app.add_typer(clean_app, name="clean")
app.add_typer(ingest_app, name="ingest")
app.add_typer(meter_app, name="meter")
app.add_typer(novelty_app, name="novelty")
app.add_typer(reaper_app, name="reaper")
app.add_typer(sets_app, name="sets")
app.add_typer(tempogram_app, name="tempogram")


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

