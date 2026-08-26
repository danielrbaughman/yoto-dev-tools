"""Domain model behavior: lenient parsing + lossless round-trip."""

from typing import Any

from tests.conftest import load_fixture
from yoto.application.auth import decode_jwt_claims, user_info_from_token
from yoto.domain.content import Card
from yoto.domain.media import Icon
from yoto.domain.player import PlayRequest, card_uri


def strip_nulls(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: strip_nulls(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [strip_nulls(item) for item in value]
    return value


def test_card_round_trip_preserves_unknown_fields_at_every_level():
    raw = load_fixture("card_full.json")
    card = Card.model_validate(raw)
    # to_api drops explicit nulls (documented), so compare against the
    # null-stripped original.
    assert card.to_api() == strip_nulls(raw)


def test_card_parses_typed_fields():
    card = Card.model_validate(load_fixture("card_full.json"))
    assert card.card_id == "abc12"
    assert card.content is not None
    assert card.content.config is not None
    assert card.content.config.autoadvance == "next"
    assert card.content.config.shuffle is not None
    assert card.content.config.shuffle[0].limit == 3
    chapter = card.content.chapters[0]
    assert chapter.display is not None and chapter.display.icon16x16 is not None
    track = chapter.tracks[0]
    assert track.track_url is not None and track.track_url.startswith("yoto:#")
    assert card.metadata is not None and card.metadata.min_age == 3


def test_loose_channels_types_are_accepted():
    card = Card.model_validate(load_fixture("card_full.json"))
    assert card.content is not None
    first = card.content.chapters[0].tracks[0]
    second = card.content.chapters[1].tracks[0]
    assert first.channels == "2"  # string preserved
    assert second.channels == 2  # int preserved


def test_missing_documented_required_fields_do_not_crash():
    card = Card.model_validate({"weird": {"nested": [1, 2]}})
    assert card.title is None
    assert card.to_api() == {"weird": {"nested": [1, 2]}}


def test_icon_url_empty_object_becomes_none():
    icon = Icon.model_validate({"mediaId": "m1", "url": {}})
    assert icon.url is None
    assert icon.ref == "yoto:#m1"


def test_play_request_payload_skips_unset_fields():
    assert PlayRequest(uri=card_uri("abc12")).to_payload() == {
        "uri": "https://yoto.io/abc12"
    }
    full = PlayRequest(
        uri="u",
        chapter_key="02",
        track_key="01",
        seconds_in=5,
        cut_off=60,
        any_button_stop=True,
    ).to_payload()
    assert full == {
        "uri": "u",
        "chapterKey": "02",
        "trackKey": "01",
        "secondsIn": 5,
        "cutOff": 60,
        "anyButtonStop": True,
    }


def test_decode_jwt_claims():
    # header.payload.signature with payload {"sub":"u1","exp":123,"scope":"a b"}
    token = "e30.eyJzdWIiOiJ1MSIsImV4cCI6MTIzLCJzY29wZSI6ImEgYiJ9.sig"
    claims = decode_jwt_claims(token)
    assert claims == {"sub": "u1", "exp": 123, "scope": "a b"}
    info = user_info_from_token(token)
    assert info.sub == "u1"
    assert info.expires_at == 123


def test_decode_jwt_claims_tolerates_garbage():
    assert decode_jwt_claims("not-a-jwt") == {}
    assert decode_jwt_claims("a.!!!.c") == {}
