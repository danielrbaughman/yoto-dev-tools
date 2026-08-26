import pytest

from tests.fakes.gateways import FakeMediaGateway, InMemoryContentGateway
from yoto.application.uploads import create_playlist_from_folder
from yoto.domain.errors import InputError
from yoto.domain.media import TranscodedAudio, TranscodedInfo


class PerFileMedia(FakeMediaGateway):
    """Returns a distinct sha per uploaded file (keyed off slot request order)."""

    def get_transcode(self, upload_id, *, loudnorm=False):
        index = len(self.slot_requests)
        return TranscodedAudio(
            transcoded_sha256=f"sha-{index}",
            transcoded_info=TranscodedInfo(duration=60, file_size=1000, format="aac"),
        )


@pytest.fixture
def album(tmp_path):
    folder = tmp_path / "album"
    folder.mkdir()
    for name in ["2 - Second.mp3", "10 - Tenth.mp3", "1 - First.mp3", "notes.txt"]:
        (folder / name).write_bytes(b"x")
    return folder


def test_folder_becomes_one_chapter_per_file_in_natural_order(album, clock):
    content = InMemoryContentGateway()
    card = create_playlist_from_folder(content, PerFileMedia(), clock, album)
    assert card.card_id is not None
    assert card.title == "album"
    assert card.content is not None
    chapters = card.content.chapters
    assert [chapter.title for chapter in chapters] == ["First", "Second", "Tenth"]
    assert [chapter.key for chapter in chapters] == ["01", "02", "03"]
    tracks = [chapter.tracks[0] for chapter in chapters]
    assert all(
        track.track_url and track.track_url.startswith("yoto:#") for track in tracks
    )
    assert all(track.key == "01" for track in tracks)
    assert card.metadata is not None and card.metadata.media is not None
    assert card.metadata.media.duration == 180


def test_icon_is_applied_to_chapters_and_tracks(album, clock):
    content = InMemoryContentGateway()
    card = create_playlist_from_folder(
        content, PerFileMedia(), clock, album, icon_media_id="icon123"
    )
    assert card.content is not None
    chapter = card.content.chapters[0]
    assert chapter.display is not None
    assert chapter.display.icon16x16 == "yoto:#icon123"
    assert chapter.tracks[0].display is not None
    assert chapter.tracks[0].display.icon16x16 == "yoto:#icon123"


def test_cover_is_uploaded_and_attached(album, tmp_path, clock):
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"jpg")
    media = PerFileMedia()
    card = create_playlist_from_folder(
        InMemoryContentGateway(), media, clock, album, title="My Album", cover=cover
    )
    assert card.title == "My Album"
    assert media.cover_calls[0]["cover_type"] == "default"
    assert card.metadata is not None and card.metadata.cover is not None
    assert card.metadata.cover.image_l == "https://cdn.test/cover.png"


def test_empty_folder_is_an_input_error(tmp_path, clock):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(InputError, match="No audio files"):
        create_playlist_from_folder(
            InMemoryContentGateway(), PerFileMedia(), clock, empty
        )


def test_missing_folder_is_an_input_error(tmp_path, clock):
    with pytest.raises(InputError, match="Not a directory"):
        create_playlist_from_folder(
            InMemoryContentGateway(), PerFileMedia(), clock, tmp_path / "nope"
        )
