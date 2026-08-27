"""Ports: the interfaces the application layer depends on.

Driven adapters (HTTP, MQTT, storage, system) implement these; tests supply
in-memory fakes. This file is the architecture's table of contents.
"""

from collections.abc import Iterator
from contextlib import AbstractContextManager
from typing import IO, Any, Protocol

from yoto.domain.auth import TokenSet
from yoto.domain.content import Card
from yoto.domain.device import Device, DeviceDetails
from yoto.domain.library import LibraryGroup
from yoto.domain.media import (
    CoverImage,
    FamilyImage,
    Icon,
    TranscodedAudio,
    UploadSlot,
)
from yoto.domain.player import CommandAck, PlaybackEvent, PlayerStatus


class Clock(Protocol):
    def now(self) -> float: ...
    def sleep(self, seconds: float) -> None: ...


class TokenStore(Protocol):
    def load(self) -> TokenSet | None: ...
    def save(self, tokens: TokenSet) -> None: ...
    def clear(self) -> None: ...
    def lock(self) -> AbstractContextManager[None]:
        """Inter-process exclusion for the load-refresh-save critical section
        (Yoto refresh tokens are single-use)."""
        ...


class TokenProvider(Protocol):
    """What the HTTP and MQTT adapters consume to authenticate requests."""

    def access_token(self) -> str:
        """A token valid for at least ~30s, refreshing if needed.
        Raises AuthRequiredError when there is no way to get one."""
        ...

    def on_unauthorized(self) -> str:
        """Reactive path after a 401: force one refresh and return the new
        token, or raise AuthRequiredError."""
        ...


class AuthGateway(Protocol):
    """The OAuth endpoints at login.yotoplay.com."""

    def exchange_code(
        self, *, code: str, verifier: str, redirect_uri: str
    ) -> TokenSet: ...
    def refresh(self, refresh_token: str) -> TokenSet: ...
    def userinfo(self, access_token: str) -> dict[str, Any]: ...


class CodeReceiver(Protocol):
    """Loopback server that receives the OAuth authorization code."""

    def start(self) -> str:
        """Bind and return the redirect URI."""
        ...

    def wait_for_code(self, *, expected_state: str, timeout: float) -> str: ...
    def close(self) -> None: ...


class BrowserOpener(Protocol):
    def open(self, url: str) -> bool: ...


class ContentGateway(Protocol):
    def list_cards(self) -> list[Card]: ...
    def get_card(self, card_id: str, *, playable: bool = False) -> Card: ...
    def upsert_card(self, card: Card) -> Card: ...
    def delete_card(self, card_id: str) -> None: ...


class MediaGateway(Protocol):
    def request_upload_slot(self, *, sha256: str, filename: str) -> UploadSlot: ...

    def put_object(
        self, upload_url: str, data: IO[bytes], *, content_type: str
    ) -> None: ...

    def get_object(self, url: str, sink: IO[bytes]) -> int:
        """Stream a (pre-signed, unauthenticated) URL into ``sink``; returns
        the number of bytes written."""
        ...

    def get_transcode(
        self, upload_id: str, *, loudnorm: bool = False
    ) -> TranscodedAudio | None:
        """None means "not ready yet" — keep polling."""
        ...

    def upload_cover(
        self, data: bytes, *, content_type: str, cover_type: str, autoconvert: bool
    ) -> CoverImage: ...


class IconGateway(Protocol):
    def list_public(self) -> list[Icon]: ...
    def list_mine(self) -> list[Icon]: ...

    def upload(self, data: bytes, *, filename: str, autoconvert: bool) -> Icon: ...


class DeviceGateway(Protocol):
    def list_devices(self) -> list[Device]: ...
    def get_details(self, device_id: str) -> DeviceDetails: ...

    def put_config(
        self, device_id: str, *, name: str | None, config: dict[str, Any]
    ) -> None: ...


class PlayerGateway(Protocol):
    """MQTT control of one player; one connection per CLI invocation."""

    def connect(self, device_id: str) -> None: ...
    def close(self) -> None: ...

    def send(
        self, device_id: str, command: str, payload: dict[str, Any], *, timeout: float
    ) -> CommandAck: ...

    def request_status(self, device_id: str, *, timeout: float) -> PlayerStatus: ...

    def events(self, device_id: str) -> Iterator[PlaybackEvent]:
        """Blocking stream of playback events (for watch)."""
        ...


class LibraryGateway(Protocol):
    def list_groups(self) -> list[LibraryGroup]: ...
    def get_group(self, group_id: str) -> LibraryGroup: ...
    def create_group(self, group: LibraryGroup) -> LibraryGroup: ...
    def update_group(self, group_id: str, group: LibraryGroup) -> LibraryGroup: ...
    def delete_group(self, group_id: str) -> None: ...


class FamilyImageGateway(Protocol):
    def list_images(self, *, limit: int | None = None) -> list[FamilyImage]: ...
    def upload_image(self, data: bytes, *, content_type: str) -> FamilyImage: ...

    def resolve_url(self, image_id: str, *, width: int, height: int) -> str:
        """Follow the API's 302 and return the signed URL."""
        ...
