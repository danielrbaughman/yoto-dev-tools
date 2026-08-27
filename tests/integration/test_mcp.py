"""MCP adapter tests: in-memory fastmcp client -> tools -> fake gateways.

These pin the MCP contract: tool names/annotations, camelCase structured
output identical to the CLI's --json, error mapping.
"""

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from tests.conftest import load_fixture
from tests.fakes.gateways import (
    FakeDeviceGateway,
    FakeIconGateway,
    FakeLibraryGateway,
    FakeMediaGateway,
    FakePlayerGateway,
    InMemoryContentGateway,
)
from yoto.adapters.mcp import _common
from yoto.adapters.mcp.server import build_server
from yoto.composition import build_services
from yoto.domain.content import Card
from yoto.domain.device import Device, DeviceDetails
from yoto.domain.media import Icon, TranscodedAudio, TranscodedInfo
from yoto.settings import YotoSettings


class Harness:
    def __init__(self) -> None:
        self.services = build_services(YotoSettings(access_token="static-token"))
        self.content = InMemoryContentGateway()
        self.media = FakeMediaGateway()
        self.icons = FakeIconGateway(
            public=[Icon(media_id="pub-1", title="Moon", public_tags=["sky"])],
            mine=[Icon(media_id="mine-1", title="Mine")],
        )
        self.devices = FakeDeviceGateway(
            [Device(device_id="dev-1", name="Kitchen", online=True)],
            details=DeviceDetails(
                device_id="dev-1", name="Kitchen", config={"maxVolumeLimit": "16"}
            ),
        )
        self.library = FakeLibraryGateway()
        self.player = FakePlayerGateway()
        self.services.content = self.content
        self.services.media = self.media
        self.services.icons = self.icons
        self.services.devices = self.devices
        self.services.library = self.library
        self.services._player = self.player
        self.server = build_server()

    def open(self) -> None:
        """One session for the harness's lifetime (like a real MCP client)."""
        self.loop = asyncio.new_event_loop()
        self.client = Client(self.server)
        self.loop.run_until_complete(self.client.__aenter__())

    def close(self) -> None:
        self.loop.run_until_complete(self.client.__aexit__(None, None, None))
        self.loop.close()

    def call(self, tool: str, /, **arguments: Any) -> Any:
        result = self.loop.run_until_complete(self.client.call_tool(tool, arguments))
        return result.structured_content

    def list_tools(self) -> dict[str, Any]:
        tools = self.loop.run_until_complete(self.client.list_tools())
        return {tool.name: tool for tool in tools}


@pytest.fixture
def harness() -> Iterator[Harness]:
    h = Harness()
    _common.set_services(h.services)
    h.open()
    yield h
    h.close()
    _common.set_services(None)


def test_tool_inventory_and_annotations(harness):
    tools = harness.list_tools()
    assert len(tools) == 33
    assert tools["playlist_list"].annotations.readOnlyHint is True
    assert tools["playlist_delete"].annotations.destructiveHint is True
    assert "trackUrl" in tools["playlist_create"].description
    assert "login" not in tools and "logout" not in tools


def test_playlist_get_matches_cli_json_contract(harness):
    card = Card.model_validate(load_fixture("card_full.json"))
    harness.content.seed(card)
    result = harness.call("playlist_get", card_id=card.card_id)
    assert result == card.to_api()
    assert result["sortkey"] == "zz-unknown-top-level"  # unknown fields survive
    assert result["content"]["chapters"][0]["display"]["icon16x16"].startswith("yoto:#")
    assert "slug" not in result or result["slug"] is not None  # no explicit nulls


def test_playlist_list_returns_list(harness):
    harness.content.seed(Card(card_id="abc12", title="A"))
    assert harness.call("playlist_list") == {
        "result": [{"cardId": "abc12", "title": "A"}]
    }


def test_playlist_update_merges_patch(harness):
    harness.content.seed(Card.model_validate(load_fixture("card_full.json")))
    result = harness.call(
        "playlist_update",
        card_id="abc12",
        patch={"title": "Renamed", "metadata": {"author": "Me"}},
    )
    assert result["title"] == "Renamed"
    assert result["metadata"]["author"] == "Me"
    assert result["metadata"]["description"] == "Two calm stories."  # merged
    assert result["sortkey"] == "zz-unknown-top-level"


def test_playlist_create_and_delete(harness):
    created = harness.call("playlist_create", card={"title": "New"})
    assert created["cardId"] == "c0001"
    assert harness.call("playlist_delete", card_id="c0001") == {"deleted": "c0001"}
    assert harness.content.deleted == ["c0001"]


def test_upload_audio_reports_track_url(harness, tmp_path):
    audio = tmp_path / "01 Intro.mp3"
    audio.write_bytes(b"ID3fake")
    harness.media.last_result = TranscodedAudio(
        transcoded_sha256="abc",
        transcoded_info=TranscodedInfo(format="opus", duration=10),
    )
    result = harness.call("upload_audio", paths=[str(audio)])
    entry = result["result"][0]
    assert entry["trackUrl"] == "yoto:#abc"
    assert entry["transcodedInfo"]["format"] == "opus"
    assert harness.media.put_calls[0]["content_type"] == "audio/mpeg"


def test_not_found_maps_to_tool_error(harness):
    with pytest.raises(ToolError, match=r"^not_found: Card zzzzz"):
        harness.call("playlist_get", card_id="zzzzz")


def test_invalid_input_maps_to_tool_error(harness):
    with pytest.raises(ToolError, match=r"^invalid: Not a file"):
        harness.call("upload_cover", path="/nope/missing.png")


def test_auth_error_hints_at_login(harness):
    _common.set_services(build_services(YotoSettings()))  # no token anywhere
    with pytest.raises(ToolError, match=r"auth_required: .*yoto auth login"):
        harness.call("auth_whoami")


def test_player_play_resolves_name_and_sends_payload(harness):
    result = harness.call(
        "player_play", device="kitchen", card_id="abc12", chapter="02"
    )
    assert result == {"ok": True, "resource": "card/start"}
    assert harness.player.connected == ["dev-1"]
    assert harness.player.closed == 1
    assert harness.player.sent == [
        ("dev-1", "card/start", {"uri": "https://yoto.io/abc12", "chapterKey": "02"})
    ]


def test_player_set_volume_validates_range(harness):
    with pytest.raises(ToolError):
        harness.call("player_set_volume", device="dev-1", level=101)
    assert harness.call("player_set_volume", device="dev-1", level=50)["ok"] is True
    assert harness.player.sent[-1][2] == {"volume": 50}


def test_player_status_and_volume_read(harness):
    assert harness.call("player_status", device="dev-1")["volume"] == 8
    assert harness.call("player_get_volume", device="dev-1") == {
        "volume": 8,
        "userVolume": 8,
    }


def test_player_unknown_device_is_not_found(harness):
    with pytest.raises(ToolError, match=r"^not_found:"):
        harness.call("player_stop", device="garage")


def test_player_config_set_merges(harness):
    result = harness.call(
        "player_config_set", device="Kitchen", config={"nightTime": "19:00"}
    )
    assert result["config"] == {"maxVolumeLimit": "16", "nightTime": "19:00"}
    assert harness.devices.put_calls[0]["name"] == "Kitchen"


def test_icon_search_scopes(harness):
    assert [
        i["mediaId"] for i in harness.call("icon_search", query="sky")["result"]
    ] == ["pub-1"]
    assert [i["mediaId"] for i in harness.call("icon_list", scope="all")["result"]] == [
        "mine-1",
        "pub-1",
    ]


def test_group_lifecycle(harness):
    group = harness.call("group_create", name="Faves", content_ids=["abc12"])
    assert group["id"] == "g1" and group["imageId"] == "fp-cards"
    updated = harness.call("group_update", group_id="g1", name="Best")
    assert updated["name"] == "Best"
    assert updated["items"] == [{"contentId": "abc12"}]
    assert harness.call("group_delete", group_id="g1") == {"deleted": "g1"}
    assert harness.call("group_list") == {"result": []}


def test_auth_whoami_uses_static_token(harness, monkeypatch):
    harness.services.auth_gateway.userinfo = lambda token: {"name": "Dan"}
    result = harness.call("auth_whoami")
    assert result["name"] == "Dan"
