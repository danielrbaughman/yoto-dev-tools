"""Player control use cases (MQTT)."""

from collections.abc import Iterator

from yoto.application.ports import PlayerGateway
from yoto.domain.player import CommandAck, PlaybackEvent, PlayerStatus, PlayRequest

DEFAULT_ACK_TIMEOUT = 10.0


def play(
    gateway: PlayerGateway,
    device_id: str,
    request: PlayRequest,
    *,
    timeout: float = DEFAULT_ACK_TIMEOUT,
) -> CommandAck:
    return gateway.send(device_id, "card/start", request.to_payload(), timeout=timeout)


def pause(
    gateway: PlayerGateway, device_id: str, *, timeout: float = DEFAULT_ACK_TIMEOUT
) -> CommandAck:
    return gateway.send(device_id, "card/pause", {}, timeout=timeout)


def resume(
    gateway: PlayerGateway, device_id: str, *, timeout: float = DEFAULT_ACK_TIMEOUT
) -> CommandAck:
    return gateway.send(device_id, "card/resume", {}, timeout=timeout)


def stop(
    gateway: PlayerGateway, device_id: str, *, timeout: float = DEFAULT_ACK_TIMEOUT
) -> CommandAck:
    return gateway.send(device_id, "card/stop", {}, timeout=timeout)


def set_volume(
    gateway: PlayerGateway,
    device_id: str,
    volume: int,
    *,
    timeout: float = DEFAULT_ACK_TIMEOUT,
) -> CommandAck:
    return gateway.send(device_id, "volume/set", {"volume": volume}, timeout=timeout)


def set_ambient(
    gateway: PlayerGateway,
    device_id: str,
    r: int,
    g: int,
    b: int,
    *,
    timeout: float = DEFAULT_ACK_TIMEOUT,
) -> CommandAck:
    payload = {"r": r, "g": g, "b": b}
    return gateway.send(device_id, "ambients/set", payload, timeout=timeout)


def set_sleep_timer(
    gateway: PlayerGateway,
    device_id: str,
    seconds: int,
    *,
    timeout: float = DEFAULT_ACK_TIMEOUT,
) -> CommandAck:
    """0 disables the sleep timer."""
    return gateway.send(
        device_id, "sleep-timer/set", {"seconds": seconds}, timeout=timeout
    )


def get_status(
    gateway: PlayerGateway, device_id: str, *, timeout: float = DEFAULT_ACK_TIMEOUT
) -> PlayerStatus:
    return gateway.request_status(device_id, timeout=timeout)


def watch_events(gateway: PlayerGateway, device_id: str) -> Iterator[PlaybackEvent]:
    return gateway.events(device_id)
