"""`yoto player DEVICE ...` commands (MQTT)."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

import typer

from yoto.adapters.cli import presenters
from yoto.adapters.cli.deps import get_services
from yoto.adapters.cli.errors import handle_errors
from yoto.adapters.cli.output import emit, note, print_json_line, stdout_console
from yoto.adapters.cli.params import JsonOpt, verbose
from yoto.application import devices as devices_uc
from yoto.application import player as player_uc
from yoto.application.ports import PlayerGateway
from yoto.domain.errors import InputError
from yoto.domain.player import CommandAck, PlayRequest, card_uri

player_app = typer.Typer(help="Real-time player control over MQTT.")


@player_app.callback()
def _player_root(
    ctx: typer.Context,
    device: Annotated[str, typer.Argument(help="Device id or unique name.")],
) -> None:
    ctx.obj = device


@contextmanager
def connected_player(ctx: typer.Context) -> Iterator[tuple[PlayerGateway, str]]:
    services = get_services()
    device = devices_uc.resolve_device(services.devices, str(ctx.obj))
    device_id = device.device_id or str(ctx.obj)
    gateway = services.player
    gateway.connect(device_id)
    try:
        yield gateway, device_id
    finally:
        gateway.close()


def _report_ack(ack: CommandAck, json_mode: bool, action: str) -> None:
    if json_mode:
        emit(ack, True, lambda _: None)
    elif ack.ok:
        note(f"{action}: ok")
    else:
        note(f"{action}: player reported FAIL")


@player_app.command()
@verbose()
@handle_errors
def play(
    ctx: typer.Context,
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
    """Start playing a card."""
    request = PlayRequest(
        uri=uri or card_uri(card_id),
        chapter_key=chapter,
        track_key=track,
        seconds_in=seconds_in,
        cut_off=cutoff,
        any_button_stop=any_button_stop or None,
    )
    with connected_player(ctx) as (gateway, device_id):
        ack = player_uc.play(gateway, device_id, request)
    _report_ack(ack, json_, f"play {card_id}")


def _simple(ctx: typer.Context, action: str, json_: bool) -> None:
    with connected_player(ctx) as (gateway, device_id):
        ack = {
            "pause": player_uc.pause,
            "resume": player_uc.resume,
            "stop": player_uc.stop,
        }[action](gateway, device_id)
    _report_ack(ack, json_, action)


@player_app.command()
@verbose()
@handle_errors
def pause(ctx: typer.Context, json_: JsonOpt = False) -> None:
    """Pause playback."""
    _simple(ctx, "pause", json_)


@player_app.command()
@verbose()
@handle_errors
def resume(ctx: typer.Context, json_: JsonOpt = False) -> None:
    """Resume playback."""
    _simple(ctx, "resume", json_)


@player_app.command()
@verbose()
@handle_errors
def stop(ctx: typer.Context, json_: JsonOpt = False) -> None:
    """Stop playback."""
    _simple(ctx, "stop", json_)


@player_app.command()
@verbose()
@handle_errors
def volume(
    ctx: typer.Context,
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
    """Set (or read) the volume."""
    with connected_player(ctx) as (gateway, device_id):
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
def status(ctx: typer.Context, json_: JsonOpt = False) -> None:
    """Request a live status report (battery, active card, volume, ...)."""
    with connected_player(ctx) as (gateway, device_id):
        result = player_uc.get_status(gateway, device_id)
    emit(result, json_, presenters.show_status)


@player_app.command()
@verbose()
@handle_errors
def watch(ctx: typer.Context, json_: JsonOpt = False) -> None:
    """Stream playback events until Ctrl-C (--json emits NDJSON)."""
    with connected_player(ctx) as (gateway, device_id):
        for event in player_uc.watch_events(gateway, device_id):
            if json_:
                print_json_line(event)
            else:
                stdout_console.print(presenters.event_line(event), highlight=False)


@player_app.command()
@verbose()
@handle_errors
def ambient(
    ctx: typer.Context,
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
    with connected_player(ctx) as (gateway, device_id):
        ack = player_uc.set_ambient(gateway, device_id, r, g, b)
    _report_ack(ack, json_, f"ambient {r},{g},{b}")


@player_app.command()
@verbose()
@handle_errors
def sleep(
    ctx: typer.Context,
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
    with connected_player(ctx) as (gateway, device_id):
        ack = player_uc.set_sleep_timer(gateway, device_id, value)
    _report_ack(ack, json_, "sleep off" if off else f"sleep {value}s")
