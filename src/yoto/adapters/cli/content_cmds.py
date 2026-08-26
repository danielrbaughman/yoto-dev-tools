"""`yoto content`, `yoto covers`, and the top-level `yoto upload`."""

import json
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from yoto.adapters.cli import presenters
from yoto.adapters.cli.deps import get_services
from yoto.adapters.cli.errors import handle_errors
from yoto.adapters.cli.output import emit, note, print_json
from yoto.adapters.cli.params import JsonOpt, YesOpt, verbose
from yoto.application import content as content_uc
from yoto.application import uploads as uploads_uc
from yoto.domain.errors import InputError

content_app = typer.Typer(help="MYO playlists (a.k.a. cards).")
covers_app = typer.Typer(help="Cover images for playlists.")

FileOpt = Annotated[
    str,
    typer.Option(
        "--file",
        "-f",
        help="Path to a JSON card (or '-' to read stdin). Accepts a bare card "
        'object or {"card": {...}}.',
    ),
]


def read_json_input(source: str) -> Any:
    if source == "-":
        raw = sys.stdin.read()
        label = "stdin"
    else:
        path = Path(source)
        if not path.is_file():
            raise InputError(f"Not a file: {source}")
        raw = path.read_text(encoding="utf-8")
        label = source
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise InputError(f"Invalid JSON from {label}: {exc}") from exc


@content_app.command("list")
@verbose()
@handle_errors
def content_list(json_: JsonOpt = False) -> None:
    """List your MYO playlists (chapters are omitted here — use `get`)."""
    cards = content_uc.list_cards(get_services().content)
    emit(cards, json_, presenters.show_cards)


@content_app.command("get")
@verbose()
@handle_errors
def content_get(
    card_id: Annotated[str, typer.Argument(help="Card/playlist id.")],
    playable: Annotated[
        bool,
        typer.Option("--playable", help="Include signed, playable track URLs."),
    ] = False,
    json_: JsonOpt = False,
) -> None:
    """Show one playlist in full."""
    card = content_uc.get_card(get_services().content, card_id, playable=playable)
    emit(card, json_, presenters.show_card)


@content_app.command("create")
@verbose()
@handle_errors
def content_create(file: FileOpt, json_: JsonOpt = False) -> None:
    """Create a playlist from a JSON document."""
    card = content_uc.create_card(get_services().content, read_json_input(file))
    emit(card, json_, presenters.show_card)


@content_app.command("update")
@verbose()
@handle_errors
def content_update(
    card_id: Annotated[str, typer.Argument(help="Card/playlist id.")],
    file: FileOpt,
    json_: JsonOpt = False,
) -> None:
    """Update a playlist: the JSON is merged onto the current card, so partial
    patches never clobber fields you did not mention."""
    card = content_uc.update_card(
        get_services().content, card_id, read_json_input(file)
    )
    emit(card, json_, presenters.show_card)


@content_app.command("delete")
@verbose()
@handle_errors
def content_delete(
    card_id: Annotated[str, typer.Argument(help="Card/playlist id.")],
    yes: YesOpt = False,
) -> None:
    """Delete a playlist."""
    if not yes:
        typer.confirm(f"Delete card {card_id}?", abort=True, err=True)
    content_uc.delete_card(get_services().content, card_id)
    note(f"Deleted {card_id}.")


@content_app.command("create-from-dir")
@verbose()
@handle_errors
def content_create_from_dir(
    folder: Annotated[
        Path, typer.Argument(help="Directory of audio files (one chapter each).")
    ],
    title: Annotated[
        str | None, typer.Option(help="Playlist title (default: folder name).")
    ] = None,
    cover: Annotated[
        Path | None, typer.Option(help="Cover image to upload and attach.")
    ] = None,
    icon: Annotated[
        str | None,
        typer.Option(help="Icon mediaId to use for every chapter (see `yoto icons`)."),
    ] = None,
    loudnorm: Annotated[
        bool, typer.Option("--loudnorm", help="Ask Yoto to loudness-normalize.")
    ] = False,
    json_: JsonOpt = False,
) -> None:
    """Upload a folder of audio and create one playlist from it (files sorted
    naturally: 2 before 10)."""
    services = get_services()
    card = uploads_uc.create_playlist_from_folder(
        services.content,
        services.media,
        services.clock,
        folder,
        title=title,
        cover=cover,
        icon_media_id=icon,
        loudnorm=loudnorm,
        on_progress=note,
    )
    emit(card, json_, presenters.show_card)


@verbose()
@handle_errors
def upload(
    files: Annotated[
        list[Path], typer.Argument(help="Audio files (mp3, m4a, ogg, ...).")
    ],
    loudnorm: Annotated[
        bool, typer.Option("--loudnorm", help="Ask Yoto to loudness-normalize.")
    ] = False,
    json_: JsonOpt = False,
) -> None:
    """Upload audio files and print their yoto:# track URLs (for trackUrl)."""
    services = get_services()
    results = []
    for path in files:
        result = uploads_uc.upload_audio(
            services.media, services.clock, path, loudnorm=loudnorm, on_progress=note
        )
        results.append({"file": str(path), **result.to_api()})
        if not json_:
            presenters.show_upload(result)
    if json_:
        print_json(results)


@covers_app.command("upload")
@verbose()
@handle_errors
def covers_upload(
    file: Annotated[Path, typer.Argument(help="Image file.")],
    type_: Annotated[
        str,
        typer.Option(
            "--type",
            help="Cover type: default, myo, stories, music, podcast, radio, "
            "activities, sfx.",
        ),
    ] = "default",
    json_: JsonOpt = False,
) -> None:
    """Upload a cover image; use the returned mediaUrl as metadata.cover.imageL."""
    cover = uploads_uc.upload_cover(get_services().media, file, cover_type=type_)
    emit(
        cover,
        json_,
        lambda c: presenters.show_kv({"mediaId": c.media_id, "mediaUrl": c.media_url}),
    )
