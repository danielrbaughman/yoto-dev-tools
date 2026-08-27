"""`yoto player` CLI against fake gateways: validation logic + MQTT wiring."""

import pytest
from typer.testing import CliRunner

from tests.fakes.gateways import FakeDeviceGateway, FakePlayerGateway
from yoto.adapters.cli import deps
from yoto.adapters.cli.app import app
from yoto.composition import build_services
from yoto.domain.device import Device, DeviceDetails
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
