"""Player (MQTT) domain models."""

from typing import Any

from pydantic import BaseModel

from yoto.domain.base import ApiModel


def card_uri(card_id: str) -> str:
    """The URI form the player expects in card/start commands."""
    return f"https://yoto.io/{card_id}"


class PlayRequest(BaseModel):
    uri: str
    chapter_key: str | None = None
    track_key: str | None = None
    seconds_in: int | None = None
    cut_off: int | None = None
    any_button_stop: bool | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"uri": self.uri}
        if self.chapter_key is not None:
            payload["chapterKey"] = self.chapter_key
        if self.track_key is not None:
            payload["trackKey"] = self.track_key
        if self.seconds_in is not None:
            payload["secondsIn"] = self.seconds_in
        if self.cut_off is not None:
            payload["cutOff"] = self.cut_off
        if self.any_button_stop is not None:
            payload["anyButtonStop"] = self.any_button_stop
        return payload


class PlayerStatus(ApiModel):
    """device/{id}/data/status payload (inner ``status`` object)."""

    status_version: int | str | None = None
    fw_version: str | None = None
    product_type: str | None = None
    battery_level: int | None = None
    charging: int | bool | None = None
    free_disk: int | None = None
    active_card: str | None = None
    card_inserted: int | bool | None = None
    playing_status: int | str | None = None
    headphones: int | bool | None = None
    bluetooth_hp: int | bool | None = None
    volume: int | None = None
    user_volume: int | None = None
    time_format: str | None = None
    nightlight_mode: str | None = None
    day: int | bool | None = None


class PlaybackEvent(ApiModel):
    """device/{id}/data/events payload (now-playing report)."""

    card_id: str | None = None
    chapter_title: str | None = None
    chapter_key: str | None = None
    track_title: str | None = None
    track_key: str | None = None
    position: int | float | None = None  # seconds
    track_length: int | float | None = None  # seconds
    playback_status: str | None = None  # playing | paused | stopped
    volume: int | None = None
    sleep_timer_active: bool | None = None
    sleep_timer_seconds: int | None = None
    source: str | None = None  # card | remote | button | bt | none
    event_utc: int | float | None = None


class CommandAck(BaseModel):
    """Parsed device/{id}/response message."""

    resource: str
    ok: bool
    req_body: str | None = None
