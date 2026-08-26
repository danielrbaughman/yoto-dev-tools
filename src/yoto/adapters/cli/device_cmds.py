"""`yoto device` commands (REST)."""

from typing import Annotated

import typer

from yoto.adapters.cli import presenters
from yoto.adapters.cli.deps import get_services
from yoto.adapters.cli.errors import handle_errors
from yoto.adapters.cli.output import emit, note
from yoto.adapters.cli.params import JsonOpt, verbose
from yoto.application import devices as devices_uc

device_app = typer.Typer(help="Your Yoto players.")
config_app = typer.Typer(help="Player configuration.")
device_app.add_typer(config_app, name="config")

DeviceArg = Annotated[str, typer.Argument(help="Device id or unique name.")]


@device_app.command("list")
@verbose()
@handle_errors
def device_list(json_: JsonOpt = False) -> None:
    """List the family's players."""
    devices = devices_uc.list_devices(get_services().devices)
    emit(devices, json_, presenters.show_devices)


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
    note(f"Updated {', '.join(updates)}.")
    emit(details, json_, presenters.show_device_details)
