"""Device domain models (REST device-v2 API)."""

from typing import Any

from pydantic import Field

from yoto.domain.base import ApiModel


class Device(ApiModel):
    """Entry of GET /device-v2/devices/mine."""

    device_id: str | None = None
    name: str | None = None
    description: str | None = None  # two-word slug like "late.smoke"
    online: bool | None = None
    release_channel: str | None = None
    device_type: str | None = None
    device_family: str | None = None
    device_group: str | None = None


class DeviceDetails(ApiModel):
    """GET /device-v2/{id}/config response.

    ``config`` is a loose grab bag of string-typed settings (maxVolumeLimit,
    dayTime, ambientColour, ...), so it stays a plain dict — the set-config
    flow is fetch/merge/put on that dict.
    """

    device_id: str | None = None
    name: str | None = None
    device_type: str | None = None
    device_family: str | None = None
    device_group: str | None = None
    online: bool | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    shortcuts: dict[str, Any] | None = None
