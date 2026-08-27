import hashlib
import os

import pytest

from tests.fakes.gateways import FakeMediaGateway, InMemoryContentGateway
from yoto.application.uploads import (
    MAX_AUDIO_BYTES,
    natural_key,
    set_cover,
    title_from_stem,
    upload_audio,
)
from yoto.domain.content import Card
from yoto.domain.errors import ApiError, InputError, OperationTimeout
from yoto.domain.media import TranscodedAudio, TranscodedInfo, UploadSlot


def ready(sha="deadbeef"):
    return TranscodedAudio(
        transcoded_sha256=sha,
        transcoded_info=TranscodedInfo(duration=10, file_size=1000, format="aac"),
    )


@pytest.fixture
def audio_file(tmp_path):
    path = tmp_path / "song.mp3"
    path.write_bytes(b"fake-audio-bytes")
    return path


def test_happy_path_hashes_uploads_and_polls(audio_file, clock):
    media = FakeMediaGateway()
    media.transcode_results = [None, None, ready()]
    result = upload_audio(media, clock, audio_file)
    assert result.track_url == "yoto:#deadbeef"
    expected_sha = hashlib.sha256(b"fake-audio-bytes").hexdigest()
    assert media.slot_requests == [{"sha256": expected_sha, "filename": "song.mp3"}]
    put = media.put_calls[0]
    assert put["url"] == "https://s3.test/put"
    assert put["bytes"] == b"fake-audio-bytes"
    assert put["content_type"] == "audio/mpeg"
    assert len(clock.sleeps) == 2  # slept between the two not-ready polls


def test_deduplicated_upload_skips_the_put(audio_file, clock):
    media = FakeMediaGateway()
    media.slot = media.slot.model_copy(update={"upload_url": None})
    media.transcode_results = [ready()]
    result = upload_audio(media, clock, audio_file)
    assert result.transcoded_sha256 == "deadbeef"
    assert media.put_calls == []


def test_poll_exhaustion_times_out(audio_file, clock):
    media = FakeMediaGateway()  # never ready
    with pytest.raises(OperationTimeout, match="song.mp3"):
        upload_audio(media, clock, audio_file, poll_attempts=3, poll_interval=0.5)
    assert len(media.poll_calls) == 3


def test_oversized_file_is_rejected_before_any_network(tmp_path, clock):
    path = tmp_path / "huge.mp3"
    path.touch()
    os.truncate(path, MAX_AUDIO_BYTES + 1)  # sparse; no real disk usage
    media = FakeMediaGateway()
    with pytest.raises(InputError, match="1 GB"):
        upload_audio(media, clock, path)
    assert media.slot_requests == []


def test_missing_file_is_input_error(tmp_path, clock):
    with pytest.raises(InputError, match="Not a file"):
        upload_audio(FakeMediaGateway(), clock, tmp_path / "nope.mp3")


def test_loudnorm_flag_is_passed_to_polls(audio_file, clock):
    media = FakeMediaGateway()
    media.transcode_results = [ready()]
    upload_audio(media, clock, audio_file, loudnorm=True)
    assert media.poll_calls[0]["loudnorm"] is True


def test_natural_key_sorts_numerically():
    names = ["10 - b.mp3", "2 - a.mp3", "1 - z.mp3", "Intro.mp3"]
    assert sorted(names, key=natural_key) == [
        "1 - z.mp3",
        "2 - a.mp3",
        "10 - b.mp3",
        "Intro.mp3",
    ]


def test_title_from_stem_strips_track_numbers():
    assert title_from_stem("01 - The Moon") == "The Moon"
    assert title_from_stem("02_the_stars") == "the stars"
    assert title_from_stem("42") == "42"  # never empty


def test_slot_without_upload_id_is_api_error(audio_file, clock):
    media = FakeMediaGateway()
    media.slot = UploadSlot(upload_url="https://s3.test/put", upload_id=None)
    with pytest.raises(ApiError, match="uploadId"):
        upload_audio(media, clock, audio_file)


def test_set_cover_uploads_and_merges_into_card(tmp_path):
    content = InMemoryContentGateway()
    content.seed(Card(card_id="abc12", title="Tales"))
    media = FakeMediaGateway()
    image = tmp_path / "cover.png"
    image.write_bytes(b"png-bytes")
    card = set_cover(content, media, "abc12", image, cover_type="myo")
    assert media.cover_calls[0]["cover_type"] == "myo"
    assert media.cover_calls[0]["bytes"] == b"png-bytes"
    assert card.metadata is not None and card.metadata.cover is not None
    assert card.metadata.cover.image_l == "https://cdn.test/cover.png"
    assert content.upserted[-1] is card  # persisted via upsert
