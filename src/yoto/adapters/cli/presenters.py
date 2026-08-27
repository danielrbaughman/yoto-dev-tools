"""Human-readable renderers (Rich tables) for domain entities.

API-supplied strings are always wrapped in ``Text`` so a stray ``[`` in a
title is rendered literally rather than parsed as Rich markup.
"""

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich import box
from rich.filesize import decimal as fmt_bytes
from rich.table import Table
from rich.text import Text

from yoto.adapters.cli.output import stdout_console
from yoto.application.downloads import DownloadResult
from yoto.domain.auth import UserInfo
from yoto.domain.content import Card
from yoto.domain.device import Device, DeviceDetails
from yoto.domain.library import LibraryGroup
from yoto.domain.media import FamilyImage, Icon, TranscodedAudio
from yoto.domain.player import PlaybackEvent, PlayerStatus

_STATUS_STYLES = {"playing": "ok", "paused": "warn"}


def fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return ""
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _cell(value: Any, style: str = "") -> Text:
    """Markup-safe table cell; None renders as empty."""
    return Text("" if value is None else str(value), style=style)


def _table(*columns: str | dict[str, Any]) -> Table:
    """Columns are names, or dicts of ``Table.add_column`` kwargs."""
    table = Table(
        box=box.SIMPLE_HEAD, header_style="bold", show_edge=False, pad_edge=False
    )
    for column in columns:
        if isinstance(column, str):
            table.add_column(column)
        else:
            table.add_column(**column)
    return table


_ID = {"header": "ID", "style": "id", "no_wrap": True}
_NUM = {"justify": "right"}


def _kv(pairs: list[tuple[str, Any]]) -> None:
    """Aligned ``label  value`` block; falsy values are skipped."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="label")
    grid.add_column()
    for label, value in pairs:
        if value not in (None, ""):
            grid.add_row(label, _cell(value))
    if grid.row_count:
        stdout_console.print(grid)


def _heading(title: str | None, ident: str | None) -> None:
    parts: list[Any] = []
    if title:
        parts.append((title, "title"))
    if ident:
        parts.append((f" ({ident})" if title else ident, "id"))
    stdout_console.print(Text.assemble(*parts))


def _footer(count: int, noun: str) -> None:
    if count == 0:
        stdout_console.print(f"no {noun}s", style="empty", highlight=False)
    else:
        stdout_console.print(f"{count} {noun}(s)", style="muted", highlight=False)


def show_user(info: UserInfo) -> None:
    _kv(
        [
            ("user", info.sub),
            ("name", info.name),
            ("email", info.email),
            ("scopes", info.scope),
        ]
    )


def show_cards(cards: list[Card]) -> None:
    if cards:
        table = _table(_ID, "Title", "Category", "Updated")
        for card in cards:
            category = card.metadata.category if card.metadata else None
            table.add_row(
                _cell(card.card_id),
                _cell(card.title),
                _cell(category),
                _cell(card.updated_at, "muted"),
            )
        stdout_console.print(table)
    _footer(len(cards), "card")


def show_card(card: Card) -> None:
    _heading(card.title, card.card_id)
    if card.metadata:
        meta = card.metadata
        duration = meta.media.duration if meta.media else None
        _kv(
            [
                ("category", meta.category),
                ("author", meta.author),
                ("description", meta.description),
                ("duration", fmt_duration(duration) if duration else None),
            ]
        )
    chapters = card.content.chapters if card.content else []
    if not chapters:
        stdout_console.print(
            "(no chapters — try without --json or fetch by id)",
            style="empty",
            highlight=False,
        )
        return
    table = _table(
        {"header": "Chapter", "style": "id", "no_wrap": True},
        "Title",
        {"header": "Tracks", **_NUM},
        {"header": "Duration", **_NUM},
    )
    for chapter in chapters:
        duration = chapter.duration or sum(
            track.duration or 0 for track in chapter.tracks
        )
        table.add_row(
            _cell(chapter.key),
            _cell(chapter.title),
            _cell(len(chapter.tracks)),
            _cell(fmt_duration(duration)),
        )
    stdout_console.print(table)


def show_upload(result: TranscodedAudio) -> None:
    info = result.transcoded_info
    line = Text.assemble(("uploaded: ", "label"), (result.track_url or "", "id"))
    if info and info.duration is not None:
        line.append(f" ({fmt_duration(info.duration)})", style="muted")
    stdout_console.print(line)


def show_download(result: DownloadResult) -> None:
    stdout_console.print(
        Text.assemble(
            (result.title or "", "title"),
            (f" ({result.card_id})", "id"),
            " → ",
            (result.directory, "bold"),
        )
    )
    table = _table("Kind", "File", {"header": "Size", **_NUM})
    for file in result.files:
        table.add_row(
            _cell(file.kind, "muted"),
            _cell(Path(file.path).name),
            _cell(fmt_bytes(file.bytes)),
        )
    stdout_console.print(table)
    audio = sum(1 for file in result.files if file.kind == "audio")
    line = Text(f"{audio} track(s) downloaded", style="muted")
    if result.skipped:
        line.append(f", {len(result.skipped)} skipped (no playable URL)", style="warn")
    stdout_console.print(line)


def show_icons(icons: list[Icon]) -> None:
    if icons:
        table = _table({**_ID, "header": "Media ID"}, "Title", "Tags")
        for icon in icons:
            tags = ", ".join(icon.public_tags or [])
            table.add_row(_cell(icon.media_id), _cell(icon.title), _cell(tags, "muted"))
        stdout_console.print(table)
    _footer(len(icons), "icon")


def show_devices(devices: list[Device]) -> None:
    if not devices:
        _footer(0, "player")
        return
    table = _table(_ID, "Name", "Online", "Type")
    for device in devices:
        online = {True: Text("yes", "ok"), False: Text("no", "muted")}.get(
            device.online, Text("?", "muted")
        )
        table.add_row(
            _cell(device.device_id),
            _cell(device.name),
            online,
            _cell(device.device_type, "muted"),
        )
    stdout_console.print(table)


def _kv_from_mapping(mapping: dict[str, Any]) -> None:
    _kv([(key, mapping[key]) for key in sorted(mapping)])


def show_device_details(details: DeviceDetails) -> None:
    # The live config endpoint omits `name`; fall back to the id alone.
    _heading(details.name, details.device_id)
    _kv_from_mapping(details.config)


def show_status(status: PlayerStatus) -> None:
    _kv_from_mapping(status.model_dump(by_alias=True, exclude_none=True))


EVENT_COLUMNS: list[dict[str, Any]] = [
    {"header": "Time", "style": "muted", "no_wrap": True},
    {"header": "State", "no_wrap": True},
    {"header": "Card", "style": "id", "no_wrap": True},
    {"header": "Position", "justify": "right", "no_wrap": True},
    {"header": "Vol", "justify": "right", "no_wrap": True},
    {"header": "Source", "style": "muted", "no_wrap": True},
    {"header": "Chapter"},
    {"header": "Track"},
]


def _event_time(event: PlaybackEvent) -> str:
    stamp = event.event_utc if event.event_utc else time.time()
    return (
        datetime.fromtimestamp(float(stamp), tz=UTC).astimezone().strftime("%H:%M:%S")
    )


def event_row(event: PlaybackEvent) -> list[Text]:
    """One table row per playback event (same cells as ``event_line``)."""
    state = event.playback_status or "?"
    card = event.card_id if event.card_id and event.card_id != "none" else "-"
    position = fmt_duration(event.position) or "-"
    length = fmt_duration(event.track_length) or "-"
    return [
        Text(_event_time(event)),
        Text(state, style=_STATUS_STYLES.get(state, "muted")),
        Text(card),
        Text(f"{position} / {length}" if length != "-" else position),
        Text(str(event.volume) if event.volume is not None else "-"),
        Text(event.source or ""),
        Text(event.chapter_title or ""),
        Text(event.track_title or ""),
    ]


def event_table(rows: list[list[Text]]) -> Table:
    """Table for the Live view of ``player watch``."""
    table = _table(*EVENT_COLUMNS)
    for row in rows:
        table.add_row(*row)
    return table


_EVENT_WIDTHS = [8, 8, 8, 15, 4, 7]


def event_line(event: PlaybackEvent) -> Text:
    """Fixed-width single line (used when stdout is not a terminal)."""
    cells = event_row(event)
    line = Text()
    for cell, width in zip(cells, _EVENT_WIDTHS, strict=False):
        cell.pad_right(width - cell.cell_len + 2)
        line.append_text(cell)
    line.append_text(cells[6])
    if cells[7].plain and cells[7].plain != cells[6].plain:
        line.append(" / ").append_text(cells[7])
    line.rstrip()
    return line


def show_groups(groups: list[LibraryGroup]) -> None:
    if groups:
        table = _table(_ID, "Name", {"header": "Items", **_NUM})
        for group in groups:
            count = len(group.items) if group.items is not None else 0
            table.add_row(_cell(group.id), _cell(group.name), _cell(count))
        stdout_console.print(table)
    _footer(len(groups), "group")


def show_group(group: LibraryGroup) -> None:
    _heading(group.name, group.id)
    table = _table({**_ID, "header": "Content ID"}, "Title")
    titles: dict[str, str | None] = {
        card.card_id: card.title for card in group.cards or [] if card.card_id
    }
    for item in group.items or []:
        content_id = item.content_id or "?"
        table.add_row(_cell(content_id), _cell(titles.get(content_id)))
    if table.row_count:
        stdout_console.print(table)
    else:
        stdout_console.print("no items", style="empty", highlight=False)


def show_family_images(images: list[FamilyImage]) -> None:
    if images:
        table = _table({**_ID, "header": "Image ID"}, "URL")
        for image in images:
            table.add_row(_cell(image.image_id), _cell(image.url))
        stdout_console.print(table)
    _footer(len(images), "image")


def show_kv(pairs: dict[str, Any]) -> None:
    _kv(list(pairs.items()))
