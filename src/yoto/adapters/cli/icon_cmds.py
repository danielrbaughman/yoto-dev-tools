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

QueryArg = Annotated[str, typer.Argument(help="Matched against title and tags.")]

list_app = typer.Typer(help="List icons.", no_args_is_help=True)
icon_app.add_typer(list_app, name="list")

search_app = typer.Typer(help="Search icons by title/tags.", no_args_is_help=True)
icon_app.add_typer(search_app, name="search")


@list_app.command("public")
@verbose()
@handle_errors
def icon_list_public(json_: JsonOpt = False) -> None:
    """List Yoto's public icon library."""
    icons = icons_uc.list_icons(get_services().icons, scope="public")
    emit(icons, json_, presenters.show_icons)


@list_app.command("private")
@verbose()
@handle_errors
def icon_list_private(json_: JsonOpt = False) -> None:
    """List the icons you have uploaded."""
    icons = icons_uc.list_icons(get_services().icons, scope="private")
    emit(icons, json_, presenters.show_icons)


@list_app.command("all")
@verbose()
@handle_errors
def icon_list_all(json_: JsonOpt = False) -> None:
    """List your icons and the public library together."""
    icons = icons_uc.list_icons(get_services().icons, scope="all")
    emit(icons, json_, presenters.show_icons)


@search_app.command("public")
@verbose()
@handle_errors
def icon_search_public(query: QueryArg, json_: JsonOpt = False) -> None:
    """Search Yoto's public icon library."""
    icons = icons_uc.search_icons(get_services().icons, query, scope="public")
    emit(icons, json_, presenters.show_icons)


@search_app.command("private")
@verbose()
@handle_errors
def icon_search_private(query: QueryArg, json_: JsonOpt = False) -> None:
    """Search the icons you have uploaded."""
    icons = icons_uc.search_icons(get_services().icons, query, scope="private")
    emit(icons, json_, presenters.show_icons)


@search_app.command("all")
@verbose()
@handle_errors
def icon_search_all(query: QueryArg, json_: JsonOpt = False) -> None:
    """Search your icons and the public library together."""
    icons = icons_uc.search_icons(get_services().icons, query, scope="all")
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
    """Upload a custom icon."""
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
