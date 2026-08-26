"""Human-readable renderers (Rich tables) for domain entities."""

from typing import Any

from rich.table import Table

from yoto.adapters.cli.output import stdout_console
from yoto.domain.auth import UserInfo
from yoto.domain.content import Card
from yoto.domain.device import Device, DeviceDetails
from yoto.domain.library import LibraryGroup
from yoto.domain.media import FamilyImage, Icon, TranscodedAudio
from yoto.domain.player import PlaybackEvent, PlayerStatus


def fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return ""
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _table(*columns: str) -> Table:
    table = Table(show_edge=False, pad_edge=False)
    for column in columns:
        table.add_column(column)
    return table


def show_user(info: UserInfo) -> None:
    for label, value in [
        ("user", info.sub),
        ("name", info.name),
        ("email", info.email),
        ("scopes", info.scope),
    ]:
        if value:
            stdout_console.print(f"{label}: {value}", highlight=False)


def show_cards(cards: list[Card]) -> None:
    table = _table("ID", "Title", "Category", "Updated")
    for card in cards:
        category = card.metadata.category if card.metadata else None
        table.add_row(card.card_id, card.title, category, card.updated_at)
    stdout_console.print(table)
    stdout_console.print(f"{len(cards)} card(s)", style="dim")


def show_card(card: Card) -> None:
    stdout_console.print(f"[bold]{card.title}[/bold] ({card.card_id})")
    if card.metadata:
        meta = card.metadata
        for label, value in [
            ("category", meta.category),
            ("author", meta.author),
            ("description", meta.description),
        ]:
            if value:
                stdout_console.print(f"{label}: {value}", highlight=False)
        if meta.media and meta.media.duration:
            stdout_console.print(f"duration: {fmt_duration(meta.media.duration)}")
    chapters = card.content.chapters if card.content else []
    if not chapters:
        stdout_console.print("(no chapters — try without --json or fetch by id)")
        return
    table = _table("Chapter", "Title", "Tracks", "Duration")
    for chapter in chapters:
        duration = chapter.duration or sum(
            track.duration or 0 for track in chapter.tracks
        )
        table.add_row(
            chapter.key,
            chapter.title,
            str(len(chapter.tracks)),
            fmt_duration(duration),
        )
    stdout_console.print(table)


def show_upload(result: TranscodedAudio) -> None:
    info = result.transcoded_info
    line = f"uploaded: {result.track_url}"
    if info and info.duration is not None:
        line += f" ({fmt_duration(info.duration)})"
    stdout_console.print(line, highlight=False)


def show_icons(icons: list[Icon]) -> None:
    table = _table("Media ID", "Title", "Tags")
    for icon in icons:
        tags = ", ".join(icon.public_tags or [])
        table.add_row(icon.media_id, icon.title, tags)
    stdout_console.print(table)
    stdout_console.print(f"{len(icons)} icon(s)", style="dim")


def show_devices(devices: list[Device]) -> None:
    table = _table("ID", "Name", "Online", "Type")
    for device in devices:
        online = {True: "yes", False: "no"}.get(device.online, "?")
        table.add_row(device.device_id, device.name, online, device.device_type)
    stdout_console.print(table)


def show_device_details(details: DeviceDetails) -> None:
    stdout_console.print(f"[bold]{details.name}[/bold] ({details.device_id})")
    table = _table("Key", "Value")
    for key in sorted(details.config):
        table.add_row(key, str(details.config[key]))
    stdout_console.print(table)


def show_status(status: PlayerStatus) -> None:
    dumped = status.model_dump(by_alias=True, exclude_none=True)
    table = _table("Key", "Value")
    for key in sorted(dumped):
        table.add_row(key, str(dumped[key]))
    stdout_console.print(table)


def event_line(event: PlaybackEvent) -> str:
    position = fmt_duration(event.position) or "-"
    length = fmt_duration(event.track_length) or "-"
    track = " / ".join(
        part for part in [event.chapter_title, event.track_title] if part
    )
    return (
        f"{event.playback_status or '?':<8} {event.card_id or '-':<8} "
        f"{position}/{length}  vol={event.volume}  {track}"
    )


def show_groups(groups: list[LibraryGroup]) -> None:
    table = _table("ID", "Name", "Items")
    for group in groups:
        count = len(group.items) if group.items is not None else 0
        table.add_row(group.id, group.name, str(count))
    stdout_console.print(table)


def show_group(group: LibraryGroup) -> None:
    stdout_console.print(f"[bold]{group.name}[/bold] ({group.id})")
    table = _table("Content ID", "Title")
    titles: dict[str, str | None] = {
        card.card_id: card.title for card in group.cards or [] if card.card_id
    }
    for item in group.items or []:
        content_id = item.content_id or "?"
        table.add_row(content_id, titles.get(content_id))
    stdout_console.print(table)


def show_family_images(images: list[FamilyImage]) -> None:
    table = _table("Image ID", "URL")
    for image in images:
        table.add_row(image.image_id, image.url)
    stdout_console.print(table)


def show_kv(pairs: dict[str, Any]) -> None:
    for key, value in pairs.items():
        stdout_console.print(f"{key}: {value}", highlight=False)
