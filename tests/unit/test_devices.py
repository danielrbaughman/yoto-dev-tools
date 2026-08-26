import pytest

from tests.conftest import load_fixture
from tests.fakes.gateways import FakeDeviceGateway
from yoto.application.devices import (
    parse_config_updates,
    resolve_device,
    set_device_config,
)
from yoto.domain.device import Device, DeviceDetails
from yoto.domain.errors import InputError, NotFoundError


def make_gateway():
    devices = [
        Device.model_validate(d) for d in load_fixture("devices.json")["devices"]
    ]
    details = DeviceDetails.model_validate(load_fixture("device_config.json")["device"])
    return FakeDeviceGateway(devices, details)


def test_resolve_by_exact_id():
    gateway = make_gateway()
    assert resolve_device(gateway, "y2BBBBBBBBBBBBBB").name == "Mini"


def test_resolve_by_name_case_insensitive():
    gateway = make_gateway()
    assert resolve_device(gateway, "kitchen player").device_id == "y2AAAAAAAAAAAAAA"


def test_resolve_unknown_raises_not_found():
    with pytest.raises(NotFoundError, match="garage"):
        resolve_device(make_gateway(), "garage")


def test_resolve_ambiguous_name_raises_input_error():
    gateway = make_gateway()
    gateway.devices.append(Device(device_id="y2C", name="Mini"))
    with pytest.raises(InputError, match="ambiguous"):
        resolve_device(gateway, "MINI")


def test_parse_config_updates():
    assert parse_config_updates(["a=1", "b=x=y"]) == {"a": "1", "b": "x=y"}
    with pytest.raises(InputError, match="KEY=VALUE"):
        parse_config_updates(["oops"])


def test_set_config_merges_with_existing_values():
    gateway = make_gateway()
    set_device_config(gateway, "Kitchen Player", {"maxVolumeLimit": "12"})
    put = gateway.put_calls[0]
    assert put["device_id"] == "y2AAAAAAAAAAAAAA"
    assert put["name"] == "Kitchen Player"  # name preserved on plain config set
    assert put["config"]["maxVolumeLimit"] == "12"  # updated
    assert put["config"]["dayTime"] == "07:30"  # merged, not clobbered


def test_set_config_can_rename():
    gateway = make_gateway()
    set_device_config(gateway, "y2AAAAAAAAAAAAAA", {}, name="Lounge")
    assert gateway.put_calls[0]["name"] == "Lounge"
