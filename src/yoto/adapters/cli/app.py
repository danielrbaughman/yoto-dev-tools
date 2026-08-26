"""Root Typer app and entry point."""

import contextlib
import logging
import sys
from typing import Annotated

import typer

from yoto import __version__
from yoto.adapters.cli import content_cmds
from yoto.adapters.cli.auth_cmds import auth_app
from yoto.adapters.cli.content_cmds import content_app, covers_app
from yoto.adapters.cli.devices_cmds import devices_app
from yoto.adapters.cli.icons_cmds import icons_app
from yoto.adapters.cli.library_cmds import family_app, library_app
from yoto.adapters.cli.player_cmds import player_app

app = typer.Typer(
    help="Interact with the Yoto API — MYO playlists, uploads, icons, "
    "players, and the family library.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

app.add_typer(auth_app, name="auth")
app.add_typer(content_app, name="content")
app.command("upload")(content_cmds.upload)
app.add_typer(covers_app, name="covers")
app.add_typer(icons_app, name="icons")
app.add_typer(devices_app, name="devices")
app.add_typer(player_app, name="player")
app.add_typer(library_app, name="library")
app.add_typer(family_app, name="family")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"yoto {__version__}")
        raise typer.Exit()


def _configure_logging() -> None:
    """typer-verbose only flips levels; give the yoto loggers a stderr handler."""
    logger = logging.getLogger("yoto")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)


@app.callback()
def _root(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Print the version and exit.",
        ),
    ] = False,
) -> None:
    _configure_logging()


def main() -> None:
    try:
        app()
    except BrokenPipeError:
        # e.g. `yoto content list | head`; exit cleanly without a traceback
        with contextlib.suppress(OSError, ValueError):
            sys.stdout.close()
        sys.exit(0)


if __name__ == "__main__":
    main()
