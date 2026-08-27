"""`yoto player` commands: list & config via REST, control & status via MQTT."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

import typer

from yoto.adapters.cli import presenters
from yoto.adapters.cli.deps import get_services
from yoto.adapters.cli.errors import handle_errors
from yoto.adapters.cli.output import (
    emit,
    print_json_line,
    stdout_console,
    success,
    warn,
)
from yoto.adapters.cli.params import JsonOpt, verbose
from yoto.application import devices as devices_uc
from yoto.application import player as player_uc
from yoto.application.ports import PlayerGateway
from yoto.domain.errors import InputError
from yoto.domain.player import CommandAck, PlayRequest, card_uri

player_app = typer.Typer(help="Yoto players: control, status, configuration.")

DeviceArg = Annotated[str, typer.Argument(help="Device id or unique name.")]


@contextmanager
def connected_player(ref: str) -> Iterator[tuple[PlayerGateway, str]]:
    services = get_services()
    device = devices_uc.resolve_device(services.devices, ref)
    device_id = device.device_id or ref
    gateway = services.player
    gateway.connect(device_id)
    try:
        yield gateway, device_id
    finally:
        gateway.close()


def _report_ack(ack: CommandAck, json_mode: bool, action: str) -> None:
    if json_mode:
        emit(ack, True)
    elif ack.ok:
        success(f"{action}: ok")
    else:
        warn(f"{action}: player reported FAIL")


@player_app.command("list")
@verbose()
@handle_errors
def player_list(json_: JsonOpt = False) -> None:
    """List all Yoto players."""
    devices = devices_uc.list_devices(get_services().devices)
    emit(devices, json_, presenters.show_devices)


@player_app.command()
@verbose()
@handle_errors
def status(device: DeviceArg, json_: JsonOpt = False) -> None:
    """Status of a Yoto player."""
    with connected_player(device) as (gateway, device_id):
        result = player_uc.get_status(gateway, device_id)
    emit(result, json_, presenters.show_status)


@player_app.command()
@verbose()
@handle_errors
def play(
    device: DeviceArg,
    card_id: Annotated[str, typer.Argument(help="Card id to play.")],
    chapter: Annotated[str | None, typer.Option(help="Chapter key.")] = None,
    track: Annotated[str | None, typer.Option(help="Track key.")] = None,
    seconds_in: Annotated[int | None, typer.Option(help="Start offset.")] = None,
    cutoff: Annotated[int | None, typer.Option(help="Stop after N seconds.")] = None,
    any_button_stop: Annotated[
        bool, typer.Option("--any-button-stop", help="Any button stops playback.")
    ] = False,
    uri: Annotated[
        str | None,
        typer.Option(help="Override the card URI sent to the player."),
    ] = None,
    json_: JsonOpt = False,
) -> None:
    """Play a card."""
    request = PlayRequest(
        uri=uri or card_uri(card_id),
        chapter_key=chapter,
        track_key=track,
        seconds_in=seconds_in,
        cut_off=cutoff,
        any_button_stop=any_button_stop or None,
    )
    with connected_player(device) as (gateway, device_id):
        ack = player_uc.play(gateway, device_id, request)
    _report_ack(ack, json_, f"play {card_id}")


def _simple(device: str, action: str, json_: bool) -> None:
    with connected_player(device) as (gateway, device_id):
        ack = {
            "pause": player_uc.pause,
            "resume": player_uc.resume,
            "stop": player_uc.stop,
        }[action](gateway, device_id)
    _report_ack(ack, json_, action)


@player_app.command()
@verbose()
@handle_errors
def pause(device: DeviceArg, json_: JsonOpt = False) -> None:
    """Pause playback."""
    _simple(device, "pause", json_)


@player_app.command()
@verbose()
@handle_errors
def resume(device: DeviceArg, json_: JsonOpt = False) -> None:
    """Resume playback."""
    _simple(device, "resume", json_)


@player_app.command()
@verbose()
@handle_errors
def stop(device: DeviceArg, json_: JsonOpt = False) -> None:
    """Stop playback."""
    _simple(device, "stop", json_)


@player_app.command()
@verbose()
@handle_errors
def volume(
    device: DeviceArg,
    level: Annotated[
        int | None,
        typer.Argument(
            min=0,
            max=100,
            help="0-100 (the hardware uses 16 steps). Omit to read the current volume.",
        ),
    ] = None,
    json_: JsonOpt = False,
) -> None:
    """Get or set the volume."""
    with connected_player(device) as (gateway, device_id):
        if level is None:
            status = player_uc.get_status(gateway, device_id)
            emit(
                {"volume": status.volume, "userVolume": status.user_volume},
                json_,
                presenters.show_kv,
            )
            return
        ack = player_uc.set_volume(gateway, device_id, level)
    _report_ack(ack, json_, f"volume {level}")


@player_app.command()
@verbose()
@handle_errors
def watch(device: DeviceArg, json_: JsonOpt = False) -> None:
    """Stream playback events."""
    with connected_player(device) as (gateway, device_id):
        for event in player_uc.watch_events(gateway, device_id):
            if json_:
                print_json_line(event)
            else:
                stdout_console.print(presenters.event_line(event))


@player_app.command()
@verbose()
@handle_errors
def light(
    device: DeviceArg,
    rgb: Annotated[
        list[int] | None,
        typer.Argument(metavar="[R G B]", help="Three values 0-255."),
    ] = None,
    hex_: Annotated[str | None, typer.Option("--hex", help="Color as #rrggbb.")] = None,
    off: Annotated[bool, typer.Option("--off", help="Turn the light off.")] = False,
    json_: JsonOpt = False,
) -> None:
    """Set the ambient light color."""
    provided = sum([bool(rgb), hex_ is not None, off])
    if provided != 1:
        raise InputError("Pass exactly one of: R G B, --hex, or --off.")
    if off:
        r = g = b = 0
    elif hex_ is not None:
        value = hex_.removeprefix("#")
        if len(value) != 6:
            raise InputError(f"Bad --hex value {hex_!r}; expected #rrggbb.")
        try:
            r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            raise InputError(f"Bad --hex value {hex_!r}; expected #rrggbb.") from None
    else:
        assert rgb is not None
        if len(rgb) != 3 or not all(0 <= v <= 255 for v in rgb):
            raise InputError("R G B must be three values 0-255.")
        r, g, b = rgb
    with connected_player(device) as (gateway, device_id):
        ack = player_uc.set_ambient(gateway, device_id, r, g, b)
    _report_ack(ack, json_, f"ambient {r},{g},{b}")


@player_app.command()
@verbose()
@handle_errors
def sleep(
    device: DeviceArg,
    seconds: Annotated[
        int | None, typer.Argument(min=0, help="Sleep timer in seconds.")
    ] = None,
    off: Annotated[bool, typer.Option("--off", help="Cancel the sleep timer.")] = False,
    json_: JsonOpt = False,
) -> None:
    """Set or cancel the sleep timer."""
    if off == (seconds is not None):
        raise InputError("Pass either SECONDS or --off.")
    value = 0 if off else int(seconds or 0)
    with connected_player(device) as (gateway, device_id):
        ack = player_uc.set_sleep_timer(gateway, device_id, value)
    _report_ack(ack, json_, "sleep off" if off else f"sleep {value}s")


config_app = typer.Typer(help="Player configuration.")
player_app.add_typer(config_app, name="config")


@config_app.command("get")
@verbose()
@handle_errors
def config_get(device: DeviceArg, json_: JsonOpt = False) -> None:
    """Show a player's configuration."""
    details = devices_uc.get_device_details(get_services().devices, device)
    emit(details, json_, presenters.show_device_details)


@config_app.command("set")
@verbose()
@handle_errors
def config_set(
    device: DeviceArg,
    pairs: Annotated[
        list[str],
        typer.Argument(
            metavar="KEY=VALUE...",
            help="Config entries, e.g. maxVolumeLimit=12 nightTime=19:00",
        ),
    ],
    name: Annotated[
        str | None, typer.Option("--name", help="Also rename the player.")
    ] = None,
    json_: JsonOpt = False,
) -> None:
    """Update config keys (existing keys are preserved: fetch-merge-put)."""
    updates = devices_uc.parse_config_updates(pairs)
    details = devices_uc.set_device_config(
        get_services().devices, device, updates, name=name
    )
    success(f"Updated {', '.join(updates)}.")
    emit(details, json_, presenters.show_device_details)
