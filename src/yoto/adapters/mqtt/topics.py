"""MQTT topic builders and payload parsers (pure functions, no paho).

Topics have NO leading slash — the reference page shows one, but every
working example (and the players themselves) use the bare form.
"""

import json
from typing import Any

from yoto.domain.player import CommandAck, PlaybackEvent, PlayerStatus


def command_topic(device_id: str, command: str) -> str:
    return f"device/{device_id}/command/{command}"


def events_topic(device_id: str) -> str:
    return f"device/{device_id}/data/events"


def status_topic(device_id: str) -> str:
    return f"device/{device_id}/data/status"


def response_topic(device_id: str) -> str:
    return f"device/{device_id}/response"


def ack_matches(ack: CommandAck, command: str, request_body: str) -> bool:
    """Does a response-topic ack belong to the command we just published?

    Primary signal: the device echoes the request body in ``req_body`` —
    observed on real v2.23.3 firmware for commands with a payload; empty-object
    payloads come back as ``""``. Fallback: the ack's resource key, whose
    naming is inconsistent in practice — observed "set-volume" (volume/set),
    "card-play" (card/start), "card-stop" (card/stop), and the literal
    "status/request", while the docs claim bare names like "volume"/"status".
    """
    if ack.req_body:  # non-empty echo: exact correlation
        return ack.req_body == request_body
    first, _, rest = command.partition("/")
    candidates = {command, first, command.replace("/", "-")}
    if rest:
        candidates.add(f"{rest}-{first}")  # volume/set -> set-volume
    return ack.resource in candidates


def _load(payload: bytes) -> dict[str, Any]:
    try:
        body = json.loads(payload or b"{}")
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def parse_status(payload: bytes) -> PlayerStatus:
    body = _load(payload)
    inner = body.get("status")
    return PlayerStatus.model_validate(inner if isinstance(inner, dict) else body)


def parse_event(payload: bytes) -> PlaybackEvent:
    return PlaybackEvent.model_validate(_load(payload))


def parse_ack(payload: bytes) -> CommandAck | None:
    """Parse a response message: {"status": {"<resource>": "OK"|"FAIL",
    "req_body": "..."}}. Note the doubled key for status acks:
    {"status": {"status": "OK", ...}}."""
    status = _load(payload).get("status")
    if not isinstance(status, dict):
        return None
    req_body = status.get("req_body")
    for key, value in status.items():
        if key == "req_body":
            continue
        if isinstance(value, str):
            return CommandAck(
                resource=key,
                ok=value.upper() == "OK",
                req_body=req_body if isinstance(req_body, str) else None,
            )
    return None
