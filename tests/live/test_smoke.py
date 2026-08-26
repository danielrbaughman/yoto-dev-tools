"""Live smoke tests against the real Yoto API.

Excluded by default. Run with:

    YOTO_LIVE=1 uv run pytest -m live

Needs real credentials: either YOTO_ACCESS_TOKEN, or a prior `yoto auth login`.
The player test additionally needs YOTO_LIVE_DEVICE (id or name) and the
family:devices:control scope.
"""

import os

import pytest

from yoto.composition import build_services

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(os.environ.get("YOTO_LIVE") != "1", reason="YOTO_LIVE!=1"),
]


@pytest.fixture(scope="module")
def services():
    instance = build_services()
    yield instance
    instance.close()


def test_content_list(services):
    cards = services.content.list_cards()
    assert isinstance(cards, list)  # may be empty; must parse and not crash


def test_public_icons(services):
    icons = services.icons.list_public()
    assert len(icons) > 0
    assert any(icon.title for icon in icons)


def test_devices_and_mqtt_status(services):
    device_ref = os.environ.get("YOTO_LIVE_DEVICE")
    if not device_ref:
        pytest.skip("YOTO_LIVE_DEVICE not set")
    from yoto.application.devices import resolve_device

    device = resolve_device(services.devices, device_ref)
    assert device.device_id
    if not device.online:
        pytest.skip("device offline")
    player = services.player
    player.connect(device.device_id)
    try:
        status = player.request_status(device.device_id, timeout=15.0)
        assert status.to_api()  # got a non-empty report
    finally:
        player.close()
