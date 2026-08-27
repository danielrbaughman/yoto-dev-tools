"""Yoto player tools: list/config via REST, control/status via MQTT."""

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from yoto.adapters.mcp._common import (
    ack_result,
    connected_player,
    get_services,
    tool_errors,
)
from yoto.adapters.serialize import to_jsonable
from yoto.application import devices as devices_uc
from yoto.application import player as player_uc
from yoto.domain.player import PlayRequest, card_uri

Device = Annotated[
    str, Field(description="Device id or unique player name (case-insensitive).")
]
READ_ONLY = {"readOnlyHint": True}
IDEMPOTENT = {"idempotentHint": True}
Channel = Annotated[int, Field(ge=0, le=255)]


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=READ_ONLY)
    @tool_errors
    def player_list() -> list[dict[str, Any]]:
        """List all Yoto players (id, name, online, type)."""
        return to_jsonable(devices_uc.list_devices(get_services().devices))

    @mcp.tool(annotations=READ_ONLY)
    @tool_errors
    def player_status(device: Device) -> dict[str, Any]:
        """Live status of a player over MQTT: battery, volume, active card,
        playing status, etc. The player must be online."""
        with connected_player(device) as (gateway, device_id):
            return to_jsonable(player_uc.get_status(gateway, device_id))

    @mcp.tool
    @tool_errors
    def player_play(
        device: Device,
        card_id: Annotated[str, Field(description="Card/playlist id to play.")],
        chapter: Annotated[str | None, Field(description="Chapter key.")] = None,
        track: Annotated[str | None, Field(description="Track key.")] = None,
        seconds_in: Annotated[int | None, Field(description="Start offset.")] = None,
        cutoff: Annotated[
            int | None, Field(description="Stop after N seconds.")
        ] = None,
        any_button_stop: Annotated[
            bool, Field(description="Any button press stops playback.")
        ] = False,
    ) -> dict[str, Any]:
        """Start playing a card/playlist on a player."""
        request = PlayRequest(
            uri=card_uri(card_id),
            chapter_key=chapter,
            track_key=track,
            seconds_in=seconds_in,
            cut_off=cutoff,
            any_button_stop=any_button_stop or None,
        )
        with connected_player(device) as (gateway, device_id):
            return ack_result(player_uc.play(gateway, device_id, request))

    @mcp.tool(annotations=IDEMPOTENT)
    @tool_errors
    def player_pause(device: Device) -> dict[str, Any]:
        """Pause playback."""
        with connected_player(device) as (gateway, device_id):
            return ack_result(player_uc.pause(gateway, device_id))

    @mcp.tool(annotations=IDEMPOTENT)
    @tool_errors
    def player_resume(device: Device) -> dict[str, Any]:
        """Resume paused playback."""
        with connected_player(device) as (gateway, device_id):
            return ack_result(player_uc.resume(gateway, device_id))

    @mcp.tool(annotations=IDEMPOTENT)
    @tool_errors
    def player_stop(device: Device) -> dict[str, Any]:
        """Stop playback."""
        with connected_player(device) as (gateway, device_id):
            return ack_result(player_uc.stop(gateway, device_id))

    @mcp.tool(annotations=READ_ONLY)
    @tool_errors
    def player_get_volume(device: Device) -> dict[str, Any]:
        """Read the current volume (0-100)."""
        with connected_player(device) as (gateway, device_id):
            status = player_uc.get_status(gateway, device_id)
        return {"volume": status.volume, "userVolume": status.user_volume}

    @mcp.tool(annotations=IDEMPOTENT)
    @tool_errors
    def player_set_volume(
        device: Device,
        level: Annotated[
            int, Field(ge=0, le=100, description="0-100 (hardware uses 16 steps).")
        ],
    ) -> dict[str, Any]:
        """Set the volume."""
        with connected_player(device) as (gateway, device_id):
            return ack_result(player_uc.set_volume(gateway, device_id, level))

    @mcp.tool(annotations=IDEMPOTENT)
    @tool_errors
    def player_set_light(
        device: Device, r: Channel, g: Channel, b: Channel
    ) -> dict[str, Any]:
        """Set the ambient light colour (RGB 0-255 each)."""
        with connected_player(device) as (gateway, device_id):
            return ack_result(player_uc.set_ambient(gateway, device_id, r, g, b))

    @mcp.tool(annotations=IDEMPOTENT)
    @tool_errors
    def player_light_off(device: Device) -> dict[str, Any]:
        """Turn the ambient light off."""
        with connected_player(device) as (gateway, device_id):
            return ack_result(player_uc.set_ambient(gateway, device_id, 0, 0, 0))

    @mcp.tool(annotations=IDEMPOTENT)
    @tool_errors
    def player_set_sleep_timer(
        device: Device,
        seconds: Annotated[
            int, Field(ge=0, description="Seconds until sleep; 0 cancels the timer.")
        ],
    ) -> dict[str, Any]:
        """Set or cancel the sleep timer."""
        with connected_player(device) as (gateway, device_id):
            return ack_result(player_uc.set_sleep_timer(gateway, device_id, seconds))

    @mcp.tool(annotations=READ_ONLY)
    @tool_errors
    def player_config_get(device: Device) -> dict[str, Any]:
        """Show a player's configuration (REST; works while offline)."""
        details = devices_uc.get_device_details(get_services().devices, device)
        return to_jsonable(details)

    @mcp.tool(annotations=IDEMPOTENT)
    @tool_errors
    def player_config_set(
        device: Device,
        config: Annotated[
            dict[str, Any],
            Field(
                description='Config keys to set, e.g. {"maxVolumeLimit": "12", '
                '"nightTime": "19:00"}. Existing keys are preserved.'
            ),
        ],
        name: Annotated[
            str | None, Field(description="Also rename the player.")
        ] = None,
    ) -> dict[str, Any]:
        """Update player configuration keys (fetch-merge-put)."""
        details = devices_uc.set_device_config(
            get_services().devices, device, config, name=name
        )
        return to_jsonable(details)
