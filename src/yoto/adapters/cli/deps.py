"""Lazy service container for CLI commands (and the test override seam)."""

from yoto.composition import Services, build_services

_services: Services | None = None


def get_services() -> Services:
    global _services
    if _services is None:
        _services = build_services()
    return _services


def set_services(services: Services | None) -> None:
    """Test seam: inject or reset the container."""
    global _services
    _services = services
