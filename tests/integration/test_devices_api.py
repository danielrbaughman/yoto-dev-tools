import json

import httpx
import respx

from tests.conftest import load_fixture
from yoto.adapters.http.client import ApiHttp
from yoto.adapters.http.devices_api import HttpDeviceGateway


def make_gateway() -> HttpDeviceGateway:
    return HttpDeviceGateway(
        ApiHttp(httpx.Client(base_url="https://api.test"), sleep=lambda _: None)
    )


@respx.mock(assert_all_called=True)
def test_list_devices(respx_mock):
    respx_mock.get("https://api.test/device-v2/devices/mine").respond(
        json=load_fixture("devices.json")
    )
    devices = make_gateway().list_devices()
    assert [device.name for device in devices] == ["Kitchen Player", "Mini"]
    assert devices[0].online is True


@respx.mock(assert_all_called=True)
def test_get_details_unwraps_device(respx_mock):
    respx_mock.get("https://api.test/device-v2/y2A/config").respond(
        json=load_fixture("device_config.json")
    )
    details = make_gateway().get_details("y2A")
    assert details.name == "Kitchen Player"
    assert details.config["maxVolumeLimit"] == "16"
    assert details.to_api()["mac"] == "aa:bb:cc:dd:ee:ff"  # unknown field kept


@respx.mock(assert_all_called=True)
def test_put_config_body_shape(respx_mock):
    route = respx_mock.put("https://api.test/device-v2/y2A/config").respond(
        json={"status": "ok"}
    )
    make_gateway().put_config("y2A", name="Kitchen", config={"dayTime": "07:00"})
    body = json.loads(route.calls[0].request.content)
    assert body == {"config": {"dayTime": "07:00"}, "name": "Kitchen"}


@respx.mock(assert_all_called=True)
def test_put_config_without_name(respx_mock):
    route = respx_mock.put("https://api.test/device-v2/y2A/config").respond(
        json={"status": "ok"}
    )
    make_gateway().put_config("y2A", name=None, config={})
    assert json.loads(route.calls[0].request.content) == {"config": {}}
