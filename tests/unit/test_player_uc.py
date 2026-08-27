"""Player use cases: each command maps to its MQTT topic + payload contract."""

import pytest

from tests.fakes.gateways import FakePlayerGateway
from yoto.application import player as player_uc
from yoto.domain.player import PlayRequest, card_uri


@pytest.mark.parametrize(
    ("send", "topic", "payload"),
    [
        (lambda g: player_uc.pause(g, "d1"), "card/pause", {}),
        (lambda g: player_uc.resume(g, "d1"), "card/resume", {}),
        (lambda g: player_uc.stop(g, "d1"), "card/stop", {}),
        (lambda g: player_uc.set_volume(g, "d1", 9), "volume/set", {"volume": 9}),
        (
            lambda g: player_uc.set_ambient(g, "d1", 1, 2, 3),
            "ambients/set",
            {"r": 1, "g": 2, "b": 3},
        ),
        (
            lambda g: player_uc.set_sleep_timer(g, "d1", 90),
            "sleep-timer/set",
            {"seconds": 90},
        ),
    ],
    ids=["pause", "resume", "stop", "volume", "ambient", "sleep"],
)
def test_commands_map_to_topics(send, topic, payload):
    gateway = FakePlayerGateway()
    ack = send(gateway)
    assert ack.ok is True
    assert gateway.sent == [("d1", topic, payload)]


def test_play_sends_card_start_with_camelcase_payload():
    gateway = FakePlayerGateway()
    request = PlayRequest(
        uri=card_uri("abc12"),
        chapter_key="02",
        track_key="01",
        seconds_in=5,
        cut_off=60,
        any_button_stop=True,
    )
    player_uc.play(gateway, "d1", request)
    device_id, topic, payload = gateway.sent[0]
    assert (device_id, topic) == ("d1", "card/start")
    assert payload == {
        "uri": "https://yoto.io/abc12",
        "chapterKey": "02",
        "trackKey": "01",
        "secondsIn": 5,
        "cutOff": 60,
        "anyButtonStop": True,
    }


def test_get_status_and_watch_events_delegate_to_gateway():
    gateway = FakePlayerGateway()
    assert player_uc.get_status(gateway, "d1").volume == 8
    assert list(player_uc.watch_events(gateway, "d1")) == []
