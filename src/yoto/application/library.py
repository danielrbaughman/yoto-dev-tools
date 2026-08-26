"""Family library use cases: groups and family images."""

from pathlib import Path

from yoto.application.ports import FamilyImageGateway, LibraryGateway
from yoto.domain.errors import InputError
from yoto.domain.library import LibraryGroup, LibraryGroupItem
from yoto.domain.media import FamilyImage

MAX_FAMILY_IMAGE_BYTES = 8 * 1024 * 1024
IMAGE_CONTENT_TYPES = {
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
}
ALLOWED_IMAGE_SIZES = {(640, 480), (320, 320)}


def list_groups(gateway: LibraryGateway) -> list[LibraryGroup]:
    return gateway.list_groups()


def get_group(gateway: LibraryGateway, group_id: str) -> LibraryGroup:
    return gateway.get_group(group_id)


def create_group(
    gateway: LibraryGateway,
    *,
    name: str,
    image_id: str | None = None,
    content_ids: list[str] | None = None,
) -> LibraryGroup:
    group = LibraryGroup(
        name=name,
        image_id=image_id,
        items=[LibraryGroupItem(content_id=cid) for cid in content_ids or []],
    )
    return gateway.create_group(group)


def update_group(
    gateway: LibraryGateway,
    group_id: str,
    *,
    name: str | None = None,
    image_id: str | None = None,
    content_ids: list[str] | None = None,
) -> LibraryGroup:
    """Fetch-merge-put: only the provided fields change."""
    current = gateway.get_group(group_id)
    updated = LibraryGroup(
        name=name if name is not None else current.name,
        image_id=image_id if image_id is not None else current.image_id,
        items=(
            [LibraryGroupItem(content_id=cid) for cid in content_ids]
            if content_ids is not None
            else current.items
        ),
    )
    return gateway.update_group(group_id, updated)


def delete_group(gateway: LibraryGateway, group_id: str) -> None:
    gateway.delete_group(group_id)


def list_family_images(
    gateway: FamilyImageGateway, *, limit: int | None = None
) -> list[FamilyImage]:
    return gateway.list_images(limit=limit)


def upload_family_image(gateway: FamilyImageGateway, path: Path) -> FamilyImage:
    if not path.is_file():
        raise InputError(f"Not a file: {path}")
    content_type = IMAGE_CONTENT_TYPES.get(path.suffix.lower())
    if content_type is None:
        raise InputError(
            f"Unsupported image type {path.suffix!r}; use JPEG, PNG, or GIF."
        )
    data = path.read_bytes()
    if len(data) > MAX_FAMILY_IMAGE_BYTES:
        raise InputError(f"{path.name} exceeds the 8 MB family image limit.")
    return gateway.upload_image(data, content_type=content_type)


def resolve_family_image_url(
    gateway: FamilyImageGateway, image_id: str, *, size: str = "640x480"
) -> str:
    try:
        width_s, _, height_s = size.lower().partition("x")
        width, height = int(width_s), int(height_s)
    except ValueError:
        raise InputError(f"Bad size {size!r}; expected 640x480 or 320x320.") from None
    if (width, height) not in ALLOWED_IMAGE_SIZES:
        raise InputError("The API only supports sizes 640x480 and 320x320.")
    return gateway.resolve_url(image_id, width=width, height=height)
