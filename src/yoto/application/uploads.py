"""Media upload use cases: audio, covers, whole-folder playlists."""

import hashlib
import mimetypes
import re
from collections.abc import Callable
from pathlib import Path

from yoto.application.ports import Clock, ContentGateway, MediaGateway
from yoto.domain.content import (
    Card,
    CardContent,
    CardMetadata,
    Chapter,
    Cover,
    MediaInfo,
    Track,
    TrackDisplay,
)
from yoto.domain.errors import ApiError, InputError, OperationTimeout
from yoto.domain.media import CoverImage, TranscodedAudio

MAX_AUDIO_BYTES = 1_073_741_824  # 1 GB, per yoto.dev
AUDIO_EXTENSIONS = {
    ".aac",
    ".aif",
    ".aiff",
    ".flac",
    ".m4a",
    ".mp3",
    ".ogg",
    ".opus",
    ".wav",
}
_CHUNK = 1024 * 1024

Progress = Callable[[str], None]


def _noop_progress(_: str) -> None:
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def guess_content_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def upload_audio(
    media: MediaGateway,
    clock: Clock,
    path: Path,
    *,
    loudnorm: bool = False,
    poll_attempts: int = 120,
    poll_interval: float = 0.5,
    on_progress: Progress = _noop_progress,
) -> TranscodedAudio:
    """Full audio flow: hash -> upload slot -> (PUT unless deduped) -> poll."""
    if not path.is_file():
        raise InputError(f"Not a file: {path}")
    size = path.stat().st_size
    if size > MAX_AUDIO_BYTES:
        raise InputError(
            f"{path.name} is {size} bytes; the Yoto API limit is 1 GB per file."
        )
    on_progress(f"Hashing {path.name}…")
    sha256 = sha256_file(path)
    slot = media.request_upload_slot(sha256=sha256, filename=path.name)
    if slot.upload_id is None:
        raise ApiError("Upload slot response did not include an uploadId.")
    if slot.upload_url is None:
        on_progress(f"{path.name} already uploaded (deduplicated); skipping transfer.")
    else:
        on_progress(f"Uploading {path.name} ({size} bytes)…")
        with path.open("rb") as handle:
            media.put_object(
                slot.upload_url, handle, content_type=guess_content_type(path)
            )
    on_progress("Waiting for transcoding…")
    for _ in range(poll_attempts):
        result = media.get_transcode(slot.upload_id, loudnorm=loudnorm)
        if result is not None and result.transcoded_sha256:
            return result
        clock.sleep(poll_interval)
    raise OperationTimeout(
        f"Transcoding of {path.name} did not finish within "
        f"{poll_attempts * poll_interval:.0f}s (uploadId {slot.upload_id})."
    )


def upload_cover(
    media: MediaGateway,
    path: Path,
    *,
    cover_type: str = "default",
    autoconvert: bool = True,
) -> CoverImage:
    if not path.is_file():
        raise InputError(f"Not a file: {path}")
    return media.upload_cover(
        path.read_bytes(),
        content_type=guess_content_type(path),
        cover_type=cover_type,
        autoconvert=autoconvert,
    )


def set_cover(
    content: ContentGateway,
    media: MediaGateway,
    card_id: str,
    image: Path,
    *,
    cover_type: str = "default",
) -> Card:
    cover = upload_cover(media, image, cover_type=cover_type)
    card = content.get_card(card_id)
    metadata = card.metadata or CardMetadata()
    metadata.cover = Cover(image_l=cover.media_url)
    card.metadata = metadata
    return content.upsert_card(card)


def natural_key(name: str) -> list[object]:
    """Case-insensitive sort key with numeric awareness ("2" < "10")."""
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", name)
    ]


def title_from_stem(stem: str) -> str:
    """Human title from a filename stem: strip leading track numbers, tidy."""
    cleaned = re.sub(r"^\s*\d+[\s._-]+", "", stem)
    cleaned = cleaned.replace("_", " ").strip()
    return cleaned or stem


def find_audio_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        raise InputError(f"Not a directory: {folder}")
    files = [
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    ]
    return sorted(files, key=lambda path: natural_key(path.name))


def create_playlist_from_folder(
    content: ContentGateway,
    media: MediaGateway,
    clock: Clock,
    folder: Path,
    *,
    title: str | None = None,
    cover: Path | None = None,
    icon_media_id: str | None = None,
    loudnorm: bool = False,
    on_progress: Progress = _noop_progress,
) -> Card:
    """Upload every audio file in a folder and create one playlist from them
    (one chapter per file, natural sort order)."""
    files = find_audio_files(folder)
    if not files:
        raise InputError(
            f"No audio files found in {folder} "
            f"(looked for {', '.join(sorted(AUDIO_EXTENSIONS))})."
        )
    display = (
        TrackDisplay(icon16x16=f"yoto:#{icon_media_id}") if icon_media_id else None
    )
    chapters: list[Chapter] = []
    total_duration = 0.0
    total_size = 0
    for index, path in enumerate(files, start=1):
        on_progress(f"[{index}/{len(files)}] {path.name}")
        transcoded = upload_audio(
            media, clock, path, loudnorm=loudnorm, on_progress=on_progress
        )
        info = transcoded.transcoded_info
        track = Track(
            key="01",
            title=title_from_stem(path.stem),
            track_url=transcoded.track_url,
            type="audio",
            format=info.format if info else None,
            duration=info.duration if info else None,
            file_size=info.file_size if info else None,
            display=display,
        )
        chapters.append(
            Chapter(
                key=f"{index:02d}",
                title=track.title,
                tracks=[track],
                display=display,
            )
        )
        if info and info.duration:
            total_duration += float(info.duration)
        if info and info.file_size:
            total_size += int(info.file_size)
    metadata = CardMetadata(
        media=MediaInfo(duration=round(total_duration), file_size=total_size)
    )
    if cover is not None:
        on_progress(f"Uploading cover {cover.name}…")
        cover_image = upload_cover(media, cover, cover_type="default")
        metadata.cover = Cover(image_l=cover_image.media_url)
    card = Card(
        title=title or folder.name,
        content=CardContent(chapters=chapters),
        metadata=metadata,
    )
    on_progress("Creating playlist…")
    return content.upsert_card(card)
