import json
from pathlib import Path

import pytest

from tests.fakes.gateways import FakeMediaGateway, InMemoryContentGateway
from yoto.application.downloads import (
    download_playlist,
    extension_for,
    safe_filename,
)
from yoto.domain.content import (
    Card,
    CardContent,
    CardMetadata,
    Chapter,
    Cover,
    Track,
    TrackDisplay,
)
from yoto.domain.errors import InputError, NotFoundError


class ResolvingContentGateway(InMemoryContentGateway):
    """Serves the seeded card plain, and a separately seeded playable copy."""

    def __init__(self) -> None:
        super().__init__()
        self.playable: dict[str, Card] = {}
        self.calls: list[tuple[str, bool]] = []

    def get_card(self, card_id: str, *, playable: bool = False) -> Card:
        self.calls.append((card_id, playable))
        if playable and card_id in self.playable:
            return self.playable[card_id]
        return super().get_card(card_id)


def track(title: str, url: str, fmt: str = "opus", icon: str | None = None) -> Track:
    display = TrackDisplay(icon16x16=icon) if icon else None
    return Track(key="01", title=title, track_url=url, format=fmt, display=display)


@pytest.fixture
def gateways():
    content = ResolvingContentGateway()
    media = FakeMediaGateway()
    plain = Card(
        card_id="abc12",
        title="Bedtime: Stories/Vol 1",
        metadata=CardMetadata(cover=Cover(image_l="https://cdn.test/cover.jpg")),
        content=CardContent(
            chapters=[
                Chapter(key="01", title="Moon", tracks=[track("Moon", "yoto:#m")]),
                Chapter(key="02", title="Stars", tracks=[track("Stars", "yoto:#s")]),
                Chapter(key="03", title="Sun", tracks=[track("Sun", "yoto:#u")]),
            ]
        ),
    )
    content.seed(plain)
    content.playable["abc12"] = plain.model_copy(
        update={
            "content": CardContent(
                chapters=[
                    Chapter(
                        key="01",
                        title="Moon",
                        display=TrackDisplay(icon16x16="https://cdn.test/i/01.png"),
                        tracks=[track("Moon", "https://media.test/m?sig=1")],
                    ),
                    Chapter(
                        key="02",
                        title="Stars",
                        tracks=[track("Stars", "https://media.test/s?sig=2", "aac")],
                    ),
                    Chapter(key="03", title="Sun", tracks=[track("Sun", "yoto:#u")]),
                ]
            )
        }
    )
    media.objects = {
        "https://media.test/m?sig=1": b"moon-audio",
        "https://media.test/s?sig=2": b"stars",
        "https://cdn.test/cover.jpg": b"jpeg",
        "https://cdn.test/i/01.png": b"png",
    }
    return content, media


def test_downloads_tracks_cover_icons_and_card_json(gateways, tmp_path):
    content, media = gateways
    result = download_playlist(content, media, "abc12", tmp_path / "out")
    out = tmp_path / "out"
    assert (out / "01 - Moon.opus").read_bytes() == b"moon-audio"
    assert (out / "02 - Stars.aac").read_bytes() == b"stars"
    assert (out / "cover.jpg").read_bytes() == b"jpeg"
    assert (out / "icons" / "01.png").read_bytes() == b"png"
    assert result.skipped == ["Sun"]
    # cover and icons are fetched first so the folder is browsable early
    assert [f.kind for f in result.files] == ["cover", "icon", "audio", "audio", "card"]
    # card.json is the plain fetch: no signed URLs leak to disk
    card = json.loads((out / "card.json").read_text())
    assert card["content"]["chapters"][0]["tracks"][0]["trackUrl"] == "yoto:#m"
    assert content.calls == [("abc12", False), ("abc12", True)]
    assert not list(out.glob("*.part"))


def test_default_directory_is_sanitized_title(gateways, tmp_path, monkeypatch):
    content, media = gateways
    monkeypatch.chdir(tmp_path)
    result = download_playlist(content, media, "abc12", cover=False, icons=False)
    assert result.directory == "Bedtime Stories Vol 1"
    assert (tmp_path / "Bedtime Stories Vol 1" / "01 - Moon.opus").exists()


def test_existing_files_are_skipped_unless_overwrite(gateways, tmp_path):
    content, media = gateways
    out = tmp_path / "out"
    out.mkdir()
    (out / "01 - Moon.opus").write_bytes(b"old")
    download_playlist(content, media, "abc12", out, cover=False, icons=False)
    assert (out / "01 - Moon.opus").read_bytes() == b"old"
    assert "https://media.test/m?sig=1" not in media.get_calls
    download_playlist(
        content, media, "abc12", out, cover=False, icons=False, overwrite=True
    )
    assert (out / "01 - Moon.opus").read_bytes() == b"moon-audio"


def test_dest_that_is_a_file_is_input_error(gateways, tmp_path):
    content, media = gateways
    target = tmp_path / "file"
    target.write_text("x")
    with pytest.raises(InputError, match="Not a directory"):
        download_playlist(content, media, "abc12", target)


def test_safe_filename_and_extension_helpers():
    assert safe_filename("  A/B:C?  ") == "A B C"
    assert safe_filename("...") == "untitled"
    assert extension_for("OPUS", "https://x/y") == "opus"
    assert extension_for(None, "https://x/y.mp3?sig=1") == "mp3"
    assert extension_for(None, "https://x/y") == "bin"


def test_failed_transfer_aborts_and_removes_partials(gateways, tmp_path):
    content, media = gateways
    del media.objects["https://media.test/s?sig=2"]  # second track 404s
    with pytest.raises(NotFoundError):
        download_playlist(content, media, "abc12", tmp_path / "out", concurrency=2)
    assert not list((tmp_path / "out").rglob("*.part"))


def test_serial_download_matches_concurrent(gateways, tmp_path):
    content, media = gateways
    serial = download_playlist(content, media, "abc12", tmp_path / "a", concurrency=1)
    parallel = download_playlist(content, media, "abc12", tmp_path / "b", concurrency=8)
    assert [(f.kind, Path(f.path).name, f.bytes) for f in serial.files] == [
        (f.kind, Path(f.path).name, f.bytes) for f in parallel.files
    ]
