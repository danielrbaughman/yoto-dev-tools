"""Family library domain models."""

from yoto.domain.base import ApiModel
from yoto.domain.content import Card


class LibraryGroupItem(ApiModel):
    content_id: str | None = None
    added_at: str | None = None


class LibraryGroup(ApiModel):
    id: str | None = None
    name: str | None = None  # truncated by the server at 100 chars
    family_id: str | None = None
    image_id: str | None = None
    image_url: str | None = None
    items: list[LibraryGroupItem] | None = None
    cards: list[Card] | None = None  # resolved form of items (read-only)
    created_at: str | None = None
    last_modified_at: str | None = None
