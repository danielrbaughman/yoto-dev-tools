"""Shared plumbing for MCP tools: service container, error mapping, helpers."""

import functools
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from fastmcp.exceptions import ToolError

from yoto.application import devices as devices_uc
from yoto.application.ports import PlayerGateway
from yoto.composition import Services, build_services
from yoto.domain.errors import (
    ApiValidationError,
    AuthError,
    ConfigError,
    InputError,
    NetworkError,
    NotFoundError,
    OperationTimeout,
    YotoError,
)

logger = logging.getLogger("yoto.mcp")

_services: Services | None = None


def get_services() -> Services:
    """One Services per server process, built on first use."""
    global _services
    if _services is None:
        _services = build_services()
    return _services


def set_services(services: Services | None) -> None:
    """Test seam: inject or reset the container."""
    global _services
    _services = services


def close_services() -> None:
    global _services
    if _services is not None:
        _services.close()
        _services = None


# Ordered: first isinstance match wins (subclasses before bases). Mirrors the
# CLI's exit-code table so the two adapters classify errors identically.
_KINDS: list[tuple[type[YotoError], str]] = [
    (NotFoundError, "not_found"),
    (ApiValidationError, "invalid"),
    (AuthError, "auth_required"),
    (ConfigError, "invalid"),
    (InputError, "invalid"),
    (OperationTimeout, "timeout"),
    (NetworkError, "network"),
    (YotoError, "api_error"),
]


def error_kind(error: YotoError) -> str:
    for error_type, kind in _KINDS:
        if isinstance(error, error_type):
            return kind
    return "api_error"


def tool_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """Map domain errors to ToolError("<kind>: <message>")."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except YotoError as error:
            kind = error_kind(error)
            message = f"{kind}: {error.message}"
            if kind == "auth_required":
                message += " (run `yoto auth login` in a terminal, then retry)"
            raise ToolError(message) from error

    return wrapper


@contextmanager
def connected_player(ref: str) -> Iterator[tuple[PlayerGateway, str]]:
    """Resolve a device id/name and hold an MQTT connection for one call."""
    services = get_services()
    device = devices_uc.resolve_device(services.devices, ref)
    device_id = device.device_id or ref
    gateway = services.player
    gateway.connect(device_id)
    try:
        yield gateway, device_id
    finally:
        gateway.close()


def ack_result(ack: Any) -> dict[str, Any]:
    return {"ok": ack.ok, "resource": ack.resource}
