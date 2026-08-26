"""`yoto playlist` commands (incl. `create from-dir` and `upload audio|cover`)."""

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

playlist_app = typer.Typer(help="MYO playlists")

FileOpt = Annotated[
    str,
    typer.Option(
        "--file",
        "-f",
        help="Path to a JSON card (or '-' to read stdin).",
    ),
]

# Rendered verbatim in --help (a paragraph containing only \b marks the next
# paragraph as no-rewrap; paragraphs are separated by blank lines).
_CARD_JSON_HELP = """

\b
The JSON card schema (only "title" and one chapter/track are required; unknown fields are passed through untouched):

\b
{
  "title": "My Playlist",                    // required, 1-140 chars
  "content": {
    "chapters": [                            // 1+ chapters
      {
        "key": "01",
        "title": "Chapter One",
        "display": {"icon16x16": "yoto:#<mediaId>"},   // see `yoto icon`
        "tracks": [                          // 1+ tracks per chapter
          {
            "key": "01",
            "title": "Track One",
            "trackUrl": "yoto:#<sha256>",    // from `playlist upload audio`,
            "type": "audio",                 //   or a URL with type "stream"
            "format": "opus",                // opus | mp3 | aac | wav | ...
            "duration": 185,                 // seconds (optional)
            "fileSize": 2960000              // bytes (optional)
          }
        ]
      }
    ],
    "config": {"autoadvance": "next"}        // next | repeat | none
  },
  "metadata": {
    "cover": {"imageL": "https://..."},      // from `playlist upload cover`
    "description": "...",
    "author": "...",
    "category": "stories",  // stories|music|radio|podcast|sfx|activities|none
    "languages": ["en"],
    "minAge": 3,
    "maxAge": 8
  }
}

\b
Tip: `yoto playlist get <id> --json` prints a real card in exactly this shape, ready to edit and feed back in.
"""


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


@playlist_app.command("list")
@verbose()
@handle_errors
def playlist_list(json_: JsonOpt = False) -> None:
    """Show all playlists."""
    cards = content_uc.list_cards(get_services().content)
    emit(cards, json_, presenters.show_cards)


@playlist_app.command("get")
@verbose()
@handle_errors
def playlist_get(
    card_id: Annotated[str, typer.Argument(help="Card/playlist id.")],
    playable: Annotated[
        bool,
        typer.Option("--playable", help="Include signed, playable track URLs."),
    ] = False,
    json_: JsonOpt = False,
) -> None:
    """Show one playlist."""
    card = content_uc.get_card(get_services().content, card_id, playable=playable)
    emit(card, json_, presenters.show_card)


upload_app = typer.Typer(help="Upload media for playlists.")
playlist_app.add_typer(upload_app, name="upload")


@playlist_app.command(
    "create",
    help="Create a playlist." + _CARD_JSON_HELP,
)
@verbose()
@handle_errors
def playlist_create(
    file: Annotated[
        str,
        typer.Option(
            "--file",
            "-f",
            help="A JSON card ('-' to read stdin), or a directory of audio files.",
        ),
    ],
    title: Annotated[
        str | None,
        typer.Option(help="Directory mode: playlist title (default: dir name)."),
    ] = None,
    cover: Annotated[
        Path | None,
        typer.Option(help="Directory mode: cover image to upload and attach."),
    ] = None,
    icon: Annotated[
        str | None,
        typer.Option(
            help="Directory mode: icon mediaId for every chapter (see `yoto icon`)."
        ),
    ] = None,
    loudnorm: Annotated[
        bool,
        typer.Option(
            "--loudnorm", help="Directory mode: ask Yoto to loudness-normalize."
        ),
    ] = False,
    json_: JsonOpt = False,
) -> None:
    """Create a playlist."""
    services = get_services()
    if file != "-" and Path(file).is_dir():
        card = uploads_uc.create_playlist_from_folder(
            services.content,
            services.media,
            services.clock,
            Path(file),
            title=title,
            cover=cover,
            icon_media_id=icon,
            loudnorm=loudnorm,
            on_progress=note,
        )
    else:
        if title is not None or cover is not None or icon is not None or loudnorm:
            raise InputError(
                "--title/--cover/--icon/--loudnorm only apply when --file "
                "is a directory."
            )
        card = content_uc.create_card(services.content, read_json_input(file))
    emit(card, json_, presenters.show_card)


@playlist_app.command(
    "update",
    help="Update a playlist." + _CARD_JSON_HELP,
)
@verbose()
@handle_errors
def playlist_update(
    card_id: Annotated[str, typer.Argument(help="Card/playlist id.")],
    file: FileOpt,
    json_: JsonOpt = False,
) -> None:
    """Update a playlist."""
    card = content_uc.update_card(
        get_services().content, card_id, read_json_input(file)
    )
    emit(card, json_, presenters.show_card)


@playlist_app.command("delete")
@verbose()
@handle_errors
def playlist_delete(
    card_id: Annotated[str, typer.Argument(help="Card/playlist id.")],
    yes: YesOpt = False,
) -> None:
    """Delete a playlist."""
    if not yes:
        typer.confirm(f"Delete card {card_id}?", abort=True, err=True)
    content_uc.delete_card(get_services().content, card_id)
    note(f"Deleted {card_id}.")


@upload_app.command("audio")
@verbose()
@handle_errors
def upload_audio(
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


@upload_app.command("cover")
@verbose()
@handle_errors
def upload_cover(
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
