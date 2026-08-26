"""Device gateway (REST device-v2)."""

from typing import Any

from yoto.adapters.http.client import ApiHttp
from yoto.domain.device import Device, DeviceDetails


class HttpDeviceGateway:
    def __init__(self, http: ApiHttp) -> None:
        self._http = http

    def list_devices(self) -> list[Device]:
        response = self._http.request("GET", "/device-v2/devices/mine")
        devices = response.json().get("devices", [])
        return [Device.model_validate(device) for device in devices]

    def get_details(self, device_id: str) -> DeviceDetails:
        response = self._http.request("GET", f"/device-v2/{device_id}/config")
        body = response.json()
        return DeviceDetails.model_validate(body.get("device", body))

    def put_config(
        self, device_id: str, *, name: str | None, config: dict[str, Any]
    ) -> None:
        payload: dict[str, Any] = {"config": config}
        if name is not None:
            payload["name"] = name
        self._http.request("PUT", f"/device-v2/{device_id}/config", json=payload)
