"""Icon use cases."""

from pathlib import Path

from yoto.application.ports import IconGateway
from yoto.domain.errors import InputError
from yoto.domain.media import Icon


def list_icons(gateway: IconGateway, *, mine: bool = False) -> list[Icon]:
    return gateway.list_mine() if mine else gateway.list_public()


def search_icons(gateway: IconGateway, query: str, *, mine: bool = False) -> list[Icon]:
    """Case-insensitive substring match over title and public tags."""
    needle = query.lower()

    def matches(icon: Icon) -> bool:
        if icon.title and needle in icon.title.lower():
            return True
        return any(needle in tag.lower() for tag in icon.public_tags or [])

    return [icon for icon in list_icons(gateway, mine=mine) if matches(icon)]


def is_animated_gif(data: bytes) -> bool:
    """Heuristic: a GIF with more than one graphic control extension."""
    return data[:6] in (b"GIF87a", b"GIF89a") and data.count(b"\x21\xf9\x04") > 1


def upload_icon(
    gateway: IconGateway,
    path: Path,
    *,
    filename: str | None = None,
    autoconvert: bool = True,
) -> tuple[Icon, bool]:
    """Upload an icon. Returns (icon, autoconvert_used).

    Animated GIFs force autoconvert off — the server's conversion would
    flatten the animation.
    """
    if not path.is_file():
        raise InputError(f"Not a file: {path}")
    data = path.read_bytes()
    if autoconvert and is_animated_gif(data):
        autoconvert = False
    icon = gateway.upload(data, filename=filename or path.name, autoconvert=autoconvert)
    return icon, autoconvert
