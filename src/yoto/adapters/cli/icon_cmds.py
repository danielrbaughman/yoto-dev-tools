"""`yoto icon` commands."""

from pathlib import Path
from typing import Annotated

import typer

from yoto.adapters.cli import presenters
from yoto.adapters.cli.deps import get_services
from yoto.adapters.cli.errors import handle_errors
from yoto.adapters.cli.output import emit, note
from yoto.adapters.cli.params import JsonOpt, verbose
from yoto.application import icons as icons_uc

icon_app = typer.Typer(help="16x16 display icons (public + private).")

MineOpt = Annotated[
    bool,
    typer.Option("--mine", help="Your uploaded icons instead of the public library."),
]


@icon_app.command("list")
@verbose()
@handle_errors
def icon_list(mine: MineOpt = False, json_: JsonOpt = False) -> None:
    """List icons (public library by default)."""
    icons = icons_uc.list_icons(get_services().icons, mine=mine)
    emit(icons, json_, presenters.show_icons)


@icon_app.command("search")
@verbose()
@handle_errors
def icon_search(
    query: Annotated[str, typer.Argument(help="Matched against title and tags.")],
    mine: MineOpt = False,
    json_: JsonOpt = False,
) -> None:
    """Search icons by title/tags (public library by default)."""
    icons = icons_uc.search_icons(get_services().icons, query, mine=mine)
    emit(icons, json_, presenters.show_icons)


@icon_app.command("upload")
@verbose()
@handle_errors
def icon_upload(
    file: Annotated[Path, typer.Argument(help="PNG or GIF; 16x16 unless converting.")],
    name: Annotated[
        str | None, typer.Option("--name", help="Filename to store it under.")
    ] = None,
    autoconvert: Annotated[
        bool,
        typer.Option(
            "--autoconvert/--no-autoconvert",
            help="Let Yoto resize/convert to 16x16 PNG. Animated GIFs are "
            "uploaded as-is automatically.",
        ),
    ] = True,
    json_: JsonOpt = False,
) -> None:
    """Upload a custom icon; reference it as display.icon16x16 = yoto:#<mediaId>."""
    icon, used_autoconvert = icons_uc.upload_icon(
        get_services().icons, file, filename=name, autoconvert=autoconvert
    )
    if autoconvert and not used_autoconvert:
        note("Animated GIF detected — uploaded without conversion.")
    emit(
        icon,
        json_,
        lambda i: presenters.show_kv({"mediaId": i.media_id, "ref": i.ref}),
    )
