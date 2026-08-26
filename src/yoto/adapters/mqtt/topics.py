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


def command_resource(command: str) -> str:
    """The resource name a command is acknowledged under
    ("volume/set" -> "volume", "card/start" -> "card")."""
    return command.split("/", 1)[0]


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
