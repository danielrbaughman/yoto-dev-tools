"""`yoto player` CLI against fake gateways: validation logic + MQTT wiring."""

import json

import pytest
from typer.testing import CliRunner

from tests.fakes.gateways import FakeDeviceGateway, FakePlayerGateway
from yoto.adapters.cli import deps
from yoto.adapters.cli.app import app
from yoto.composition import build_services
from yoto.domain.device import Device, DeviceDetails
from yoto.domain.player import PlaybackEvent
from yoto.settings import YotoSettings

runner = CliRunner()


@pytest.fixture
def player() -> FakePlayerGateway:
    services = build_services(YotoSettings(access_token="tok"))
    services.devices = FakeDeviceGateway(
        [Device(device_id="dev-1", name="Kitchen", online=True)],
        details=DeviceDetails(
            device_id="dev-1", name="Kitchen", config={"maxVolumeLimit": "16"}
        ),
    )
    gateway = FakePlayerGateway()
    services._player = gateway
    deps.set_services(services)
    return gateway


# --- light: input validation happens before any connection ---


@pytest.mark.parametrize(
    "argv",
    [
        ["player", "light", "Kitchen"],  # nothing given
        ["player", "light", "Kitchen", "1", "2", "3", "--off"],  # two forms at once
        ["player", "light", "Kitchen", "--hex", "12345"],  # wrong length
        ["player", "light", "Kitchen", "--hex", "zzzzzz"],  # not hex digits
        ["player", "light", "Kitchen", "1", "2"],  # not three values
        ["player", "light", "Kitchen", "1", "2", "300"],  # out of range
    ],
    ids=["none", "two-forms", "short-hex", "bad-hex", "two-values", "out-of-range"],
)
def test_light_rejects_bad_input(player, argv):
    result = runner.invoke(app, argv)
    assert result.exit_code == 5
    assert player.sent == []


def test_light_hex_parses_channels(player):
    result = runner.invoke(app, ["player", "light", "Kitchen", "--hex", "#20A0Ff"])
    assert result.exit_code == 0
    assert player.sent == [("dev-1", "ambients/set", {"r": 32, "g": 160, "b": 255})]


def test_light_rgb_arguments(player):
    result = runner.invoke(app, ["player", "light", "Kitchen", "10", "20", "30"])
    assert result.exit_code == 0
    assert player.sent == [("dev-1", "ambients/set", {"r": 10, "g": 20, "b": 30})]


def test_light_off_sends_zeroes(player):
    result = runner.invoke(app, ["player", "light", "Kitchen", "--off"])
    assert result.exit_code == 0
    assert player.sent == [("dev-1", "ambients/set", {"r": 0, "g": 0, "b": 0})]


# --- sleep: SECONDS xor --off ---


def test_sleep_requires_exactly_one_form(player):
    assert runner.invoke(app, ["player", "sleep", "Kitchen"]).exit_code == 5
    assert (
        runner.invoke(app, ["player", "sleep", "Kitchen", "90", "--off"]).exit_code == 5
    )
    assert player.sent == []


def test_sleep_seconds_and_off(player):
    assert runner.invoke(app, ["player", "sleep", "Kitchen", "90"]).exit_code == 0
    assert runner.invoke(app, ["player", "sleep", "Kitchen", "--off"]).exit_code == 0
    assert player.sent == [
        ("dev-1", "sleep-timer/set", {"seconds": 90}),
        ("dev-1", "sleep-timer/set", {"seconds": 0}),
    ]


# --- the rest of the command surface, against the fakes ---


def test_status_renders_and_json_round_trips(player):
    human = runner.invoke(app, ["player", "status", "Kitchen"])
    assert human.exit_code == 0
    as_json = runner.invoke(app, ["player", "status", "Kitchen", "--json"])
    assert as_json.exit_code == 0
    assert json.loads(as_json.stdout)["volume"] == 8


def test_play_builds_full_request(player):
    result = runner.invoke(
        app,
        [
            "player",
            "play",
            "Kitchen",
            "abc12",
            "--chapter",
            "02",
            "--track",
            "01",
            "--seconds-in",
            "5",
            "--cutoff",
            "60",
            "--any-button-stop",
        ],
    )
    assert result.exit_code == 0
    assert player.sent == [
        (
            "dev-1",
            "card/start",
            {
                "uri": "https://yoto.io/abc12",
                "chapterKey": "02",
                "trackKey": "01",
                "secondsIn": 5,
                "cutOff": 60,
                "anyButtonStop": True,
            },
        )
    ]


def test_pause_resume_stop(player):
    for command in ("pause", "resume", "stop"):
        assert runner.invoke(app, ["player", command, "Kitchen"]).exit_code == 0
    assert [topic for _, topic, _ in player.sent] == [
        "card/pause",
        "card/resume",
        "card/stop",
    ]
    assert player.connected == ["dev-1"] * 3
    assert player.closed == 3  # every connection is closed again


def test_volume_get_and_set(player):
    read = runner.invoke(app, ["player", "volume", "Kitchen", "--json"])
    assert read.exit_code == 0
    assert json.loads(read.stdout) == {"volume": 8, "userVolume": 8}
    assert player.sent == []  # reading never sends a command
    assert runner.invoke(app, ["player", "volume", "Kitchen", "50"]).exit_code == 0
    assert player.sent == [("dev-1", "volume/set", {"volume": 50})]


def test_failed_ack_warns_but_exits_zero(player):
    player.ok = False
    result = runner.invoke(app, ["player", "pause", "Kitchen"])
    assert result.exit_code == 0
    assert "FAIL" in result.output


def test_watch_json_emits_one_line_per_event(player):
    player.event_stream = [
        PlaybackEvent(card_id="abc12", playback_status="playing", position=1),
        PlaybackEvent(card_id="abc12", playback_status="paused", position=2),
    ]
    result = runner.invoke(app, ["player", "watch", "Kitchen", "--json"])
    assert result.exit_code == 0
    lines = [json.loads(line) for line in result.stdout.splitlines() if line]
    assert [line["playbackStatus"] for line in lines] == ["playing", "paused"]


def test_watch_human_prints_event_lines(player):
    player.event_stream = [
        PlaybackEvent(
            card_id="abc12",
            track_title="Moon",
            playback_status="playing",
            position=3,
            track_length=60,
        )
    ]
    result = runner.invoke(app, ["player", "watch", "Kitchen"])
    assert result.exit_code == 0
    assert "Moon" in result.stdout


def test_config_get_shows_details(player):
    result = runner.invoke(app, ["player", "config", "get", "Kitchen", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["config"] == {"maxVolumeLimit": "16"}


def test_config_set_merges_pairs(player):
    result = runner.invoke(
        app, ["player", "config", "set", "Kitchen", "nightTime=19:00"]
    )
    assert result.exit_code == 0
