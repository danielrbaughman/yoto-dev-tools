"""Device (REST) use cases."""

from typing import Any

from yoto.application.ports import DeviceGateway
from yoto.domain.device import Device, DeviceDetails
from yoto.domain.errors import InputError, NotFoundError


def list_devices(gateway: DeviceGateway) -> list[Device]:
    return gateway.list_devices()


def resolve_device(gateway: DeviceGateway, ref: str) -> Device:
    """Resolve a device by exact id, else by unique (case-insensitive) name."""
    devices = gateway.list_devices()
    for device in devices:
        if device.device_id == ref:
            return device
    named = [
        device
        for device in devices
        if device.name and device.name.lower() == ref.lower()
    ]
    if len(named) == 1:
        return named[0]
    if len(named) > 1:
        ids = ", ".join(device.device_id or "?" for device in named)
        raise InputError(f"Device name {ref!r} is ambiguous ({ids}); use the id.")
    raise NotFoundError(f"No device with id or name {ref!r}.")


def get_device_details(gateway: DeviceGateway, ref: str) -> DeviceDetails:
    device = resolve_device(gateway, ref)
    return gateway.get_details(device.device_id or ref)


def parse_config_updates(pairs: list[str]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            raise InputError(f"Expected KEY=VALUE, got {pair!r}.")
        updates[key] = value
    return updates


def set_device_config(
    gateway: DeviceGateway,
    ref: str,
    updates: dict[str, Any],
    *,
    name: str | None = None,
) -> DeviceDetails:
    """Fetch-merge-put so unrelated config keys are never clobbered."""
    device = resolve_device(gateway, ref)
    device_id = device.device_id or ref
    details = gateway.get_details(device_id)
    merged = {**details.config, **updates}
    gateway.put_config(
        device_id, name=name or details.name or device.name, config=merged
    )
    return gateway.get_details(device_id)
