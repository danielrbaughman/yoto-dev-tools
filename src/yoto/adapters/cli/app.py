"""Root Typer app and entry point."""

import contextlib
import logging
import sys
from typing import Annotated

import typer

from yoto import __version__
from yoto.adapters.cli import playlists_cmds
from yoto.adapters.cli.auth_cmds import auth_app
from yoto.adapters.cli.devices_cmds import devices_app
from yoto.adapters.cli.icons_cmds import icons_app
from yoto.adapters.cli.library_cmds import family_app, library_app
from yoto.adapters.cli.player_cmds import player_app
from yoto.adapters.cli.playlists_cmds import playlists_app

app = typer.Typer(
    help="Interact with the Yoto API — MYO playlists, uploads, icons, "
    "players, and the family library.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# rich_help_panel controls --help grouping/order (bare commands would always
# list before subcommand groups, which is also why the canonical home of
# upload is `playlists upload` — the bare `yoto upload` stays as a hidden alias).
app.add_typer(auth_app, name="auth", rich_help_panel="Auth")
app.add_typer(playlists_app, name="playlists", rich_help_panel="User Content")
app.command("upload", hidden=True)(playlists_cmds.upload)
app.add_typer(icons_app, name="icons", rich_help_panel="User Content")
app.add_typer(devices_app, name="devices", rich_help_panel="Players")
app.add_typer(player_app, name="player", rich_help_panel="Players")
app.add_typer(library_app, name="library", rich_help_panel="Family library")
app.add_typer(family_app, name="family", rich_help_panel="Family library")


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
