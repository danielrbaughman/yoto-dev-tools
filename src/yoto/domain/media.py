"""Media domain models: audio uploads, cover images, icons, family images."""

from typing import Any

from pydantic import field_validator

from yoto.domain.base import ApiModel


class UploadSlot(ApiModel):
    """Response of the upload-URL request. ``upload_url`` is None when the file
    is already in Yoto's store (deduplicated by sha256) — skip the PUT."""

    upload_url: str | None = None
    upload_id: str | None = None


class TranscodedInfo(ApiModel):
    duration: int | float | None = None
    file_size: int | None = None
    channels: int | str | None = None
    format: str | None = None
    metadata: dict[str, Any] | None = None


class TranscodedAudio(ApiModel):
    transcoded_sha256: str | None = None
    transcoded_info: TranscodedInfo | None = None

    @property
    def track_url(self) -> str | None:
        if self.transcoded_sha256 is None:
            return None
        return f"yoto:#{self.transcoded_sha256}"


class CoverImage(ApiModel):
    media_id: str | None = None
    media_url: str | None = None  # use as metadata.cover.imageL


class Icon(ApiModel):
    media_id: str | None = None
    user_id: str | None = None
    display_icon_id: str | None = None
    url: str | None = None
    title: str | None = None
    public_tags: list[str] | None = None
    public: bool | None = None
    new: bool | None = None
    created_at: str | None = None

    @field_validator("url", mode="before")
    @classmethod
    def _url_must_be_str(cls, value: object) -> object:
        # Re-uploading an existing icon returns "url": {} — treat as absent.
        return value if isinstance(value, str) else None

    @property
    def ref(self) -> str | None:
        """Value usable as display.icon16x16."""
        if self.media_id is None:
            return None
        return f"yoto:#{self.media_id}"


class FamilyImage(ApiModel):
    image_id: str | None = None
    url: str | None = None
