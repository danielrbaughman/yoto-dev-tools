"""Download use case: pull a playlist's audio (plus cover, icons, and the
card JSON) into a local folder.

The API hands out short-lived signed URLs when a card is fetched with
``playable=true``; those are streamed with the unauthenticated media client
(the signature is the auth). The card JSON written to disk comes from a plain
fetch so it stays free of expiring signatures.
"""

import json
import re
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

from yoto.application.ports import ContentGateway, MediaGateway
from yoto.domain.base import ApiModel
from yoto.domain.content import Card
from yoto.domain.errors import InputError

Progress = Callable[[str], None]

CARD_FILENAME = "card.json"
ICONS_DIRNAME = "icons"
_FORMAT_EXTENSIONS = {"opus": "opus", "mp3": "mp3", "aac": "aac", "wav": "wav"}


def _noop_progress(_: str) -> None:
    pass


class DownloadedFile(ApiModel):
    kind: str  # audio | cover | icon | card
    path: str
    bytes: int
    title: str | None = None


class DownloadResult(ApiModel):
    card_id: str | None
    title: str | None
    directory: str
    files: list[DownloadedFile]
    skipped: list[str]
    """Track titles whose URL could not be resolved (nothing downloadable)."""


def is_http_url(value: str | None) -> bool:
    return value is not None and value.startswith(("http://", "https://"))


def safe_filename(name: str, fallback: str = "untitled") -> str:
    """Strip path separators/control chars so a title is a plain filename."""
    cleaned = re.sub(r"[\x00-\x1f/\\:*?\"<>|]+", " ", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned[:150] or fallback


def extension_for(fmt: str | None, url: str) -> str:
    if fmt and fmt.lower() in _FORMAT_EXTENSIONS:
        return _FORMAT_EXTENSIONS[fmt.lower()]
    suffix = Path(urlparse(url).path).suffix.lstrip(".")
    return suffix or (fmt.lower() if fmt else "bin")


class TransferProgress(ApiModel):
    """Byte-level progress of one file within a playlist download."""

    name: str
    index: int  # 1-based position among all files being fetched
    total: int  # number of files being fetched
    written: int
    size: int | None  # None until/unless the server reports Content-Length
    done: bool = False


Transfer = Callable[[TransferProgress], None]


def _noop_transfer(_: TransferProgress) -> None:
    pass


class _Job(ApiModel):
    kind: str
    url: str
    path: str
    title: str | None = None


def _write(
    media: MediaGateway,
    job: _Job,
    index: int,
    total: int,
    *,
    overwrite: bool,
    on_progress: Progress,
    on_transfer: Transfer,
) -> int:
    dest = Path(job.path)
    if dest.exists() and not overwrite:
        on_progress(f"  exists, skipping: {dest.name}")
        size = dest.stat().st_size
        on_transfer(
            TransferProgress(
                name=dest.name,
                index=index,
                total=total,
                written=size,
                size=size,
                done=True,
            )
        )
        return size
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".part")

    def on_chunk(written: int, size: int | None) -> None:
        on_transfer(
            TransferProgress(
                name=dest.name, index=index, total=total, written=written, size=size
            )
        )

    with partial.open("wb") as sink:
        size = media.get_object(job.url, sink, on_chunk)
    partial.replace(dest)
    on_transfer(
        TransferProgress(
            name=dest.name, index=index, total=total, written=size, size=size, done=True
        )
    )
    return size


def download_playlist(
    content: ContentGateway,
    media: MediaGateway,
    card_id: str,
    directory: Path | None = None,
    *,
    cover: bool = True,
    icons: bool = True,
    overwrite: bool = False,
    on_progress: Progress = _noop_progress,
    on_transfer: Transfer = _noop_transfer,
) -> DownloadResult:
    """Download every track of a playlist as ``NN - Title.ext`` files.

    ``on_progress`` receives one human line per file; ``on_transfer`` receives
    byte-level ``TransferProgress`` updates (for progress bars).
    """
    card = content.get_card(card_id)
    playable = content.get_card(card_id, playable=True)
    directory = directory or Path(safe_filename(card.title or card_id, card_id))
    if directory.exists() and not directory.is_dir():
        raise InputError(f"Not a directory: {directory}")
    directory.mkdir(parents=True, exist_ok=True)

    # Plan every file first so progress reporting knows the total up front.
    # Small assets (cover, icons) go first so the folder is browsable while
    # the audio is still transferring.
    jobs: list[tuple[str, _Job]] = []  # (progress line, job)
    if cover:
        jobs.extend(_plan_cover(card, directory))
    if icons:
        jobs.extend(_plan_icons(playable, directory))
    skipped: list[str] = []
    chapters = playable.content.chapters if playable.content else []
    tracks = [(chapter, track) for chapter in chapters for track in chapter.tracks]
    width = max(2, len(str(len(tracks))))
    for index, (chapter, track) in enumerate(tracks, start=1):
        title = track.title or chapter.title or track.key or str(index)
        url = track.track_url
        if not is_http_url(url):
            on_progress(f"[{index}/{len(tracks)}] {title}: no playable URL, skipping")
            skipped.append(title)
            continue
        assert url is not None
        dest = directory / (
            f"{index:0{width}d} - {safe_filename(title)}.{extension_for(track.format, url)}"
        )
        line = f"[{index}/{len(tracks)}] {dest.name}"
        jobs.append((line, _Job(kind="audio", url=url, path=str(dest), title=title)))
    files: list[DownloadedFile] = []
    for index, (line, job) in enumerate(jobs, start=1):
        on_progress(line)
        size = _write(
            media,
            job,
            index,
            len(jobs),
            overwrite=overwrite,
            on_progress=on_progress,
            on_transfer=on_transfer,
        )
        files.append(
            DownloadedFile(kind=job.kind, path=job.path, bytes=size, title=job.title)
        )

    card_path = directory / CARD_FILENAME
    card_path.write_text(
        json.dumps(card.to_api(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    files.append(
        DownloadedFile(kind="card", path=str(card_path), bytes=card_path.stat().st_size)
    )
    return DownloadResult(
        card_id=card.card_id,
        title=card.title,
        directory=str(directory),
        files=files,
        skipped=skipped,
    )


def _plan_cover(card: Card, directory: Path) -> list[tuple[str, _Job]]:
    url = card.metadata.cover.image_l if card.metadata and card.metadata.cover else None
    if not is_http_url(url):
        return []
    assert url is not None
    ext = Path(urlparse(url).path).suffix.lstrip(".") or "jpg"
    dest = directory / f"cover.{ext}"
    return [(f"cover: {dest.name}", _Job(kind="cover", url=url, path=str(dest)))]


def _plan_icons(playable: Card, directory: Path) -> list[tuple[str, _Job]]:
    """Icons only download when the playable fetch resolved them to URLs;
    unresolved ``yoto:#`` references are silently left alone."""
    seen: dict[str, str] = {}  # url -> chapter key
    chapters = playable.content.chapters if playable.content else []
    for chapter in chapters:
        candidates = [chapter.display] + [track.display for track in chapter.tracks]
        for display in candidates:
            if display is None:
                continue
            for url in (display.icon16x16, display.icon_url16x16):
                if is_http_url(url) and url not in seen:
                    assert url is not None
                    seen[url] = chapter.key or str(len(seen) + 1)
    jobs: list[tuple[str, _Job]] = []
    for url, key in seen.items():
        ext = Path(urlparse(url).path).suffix.lstrip(".") or "png"
        dest = directory / ICONS_DIRNAME / f"{safe_filename(key)}.{ext}"
        jobs.append((f"icon: {dest.name}", _Job(kind="icon", url=url, path=str(dest))))
    return jobs
