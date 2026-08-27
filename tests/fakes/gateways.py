"""In-memory fakes for content/media/icon/device/library gateways."""

from collections.abc import Iterator
from typing import IO, Any

from yoto.application.ports import ChunkProgress
from yoto.domain.content import Card
from yoto.domain.device import Device, DeviceDetails
from yoto.domain.errors import NotFoundError
from yoto.domain.library import LibraryGroup
from yoto.domain.media import CoverImage, Icon, TranscodedAudio, UploadSlot
from yoto.domain.player import CommandAck, PlaybackEvent, PlayerStatus


class InMemoryContentGateway:
    def __init__(self) -> None:
        self.cards: dict[str, Card] = {}
        self.upserted: list[Card] = []
        self.deleted: list[str] = []
        self._counter = 0

    def seed(self, card: Card) -> Card:
        assert card.card_id
        self.cards[card.card_id] = card
        return card

    def list_cards(self) -> list[Card]:
        return list(self.cards.values())

    def get_card(self, card_id: str, *, playable: bool = False) -> Card:
        try:
            return self.cards[card_id]
        except KeyError:
            raise NotFoundError(f"Card {card_id} does not exist.") from None

    def upsert_card(self, card: Card) -> Card:
        self.upserted.append(card)
        if card.card_id is None:
            self._counter += 1
            card = card.model_copy(update={"card_id": f"c{self._counter:04d}"})
        assert card.card_id is not None
        self.cards[card.card_id] = card
        return card

    def delete_card(self, card_id: str) -> None:
        self.deleted.append(card_id)
        self.cards.pop(card_id, None)


class FakeMediaGateway:
    """Scripted media gateway for upload flows."""

    def __init__(self) -> None:
        self.slot = UploadSlot(upload_url="https://s3.test/put", upload_id="up-1")
        # get_transcode pops from this list; empty -> keep returning last_result
        self.transcode_results: list[TranscodedAudio | None] = []
        self.last_result: TranscodedAudio | None = None
        self.slot_requests: list[dict[str, str]] = []
        self.put_calls: list[dict[str, Any]] = []
        self.poll_calls: list[dict[str, Any]] = []
        self.cover_calls: list[dict[str, Any]] = []
        # get_object serves from here; unknown URLs raise NotFoundError
        self.objects: dict[str, bytes] = {}
        self.get_calls: list[str] = []

    def get_object(
        self, url: str, sink: IO[bytes], on_chunk: ChunkProgress | None = None
    ) -> int:
        self.get_calls.append(url)
        try:
            data = self.objects[url]
        except KeyError:
            raise NotFoundError(f"No object at {url}") from None
        sink.write(data)
        if on_chunk is not None:
            on_chunk(len(data), len(data))
        return len(data)

    def request_upload_slot(self, *, sha256: str, filename: str) -> UploadSlot:
        self.slot_requests.append({"sha256": sha256, "filename": filename})
        return self.slot

    def put_object(
        self, upload_url: str, data: IO[bytes], *, content_type: str
    ) -> None:
        self.put_calls.append(
            {
                "url": upload_url,
                "bytes": data.read(),
                "content_type": content_type,
            }
        )

    def get_transcode(
        self, upload_id: str, *, loudnorm: bool = False
    ) -> TranscodedAudio | None:
        self.poll_calls.append({"upload_id": upload_id, "loudnorm": loudnorm})
        if self.transcode_results:
            return self.transcode_results.pop(0)
        return self.last_result

    def upload_cover(
        self, data: bytes, *, content_type: str, cover_type: str, autoconvert: bool
    ) -> CoverImage:
        self.cover_calls.append(
            {
                "bytes": data,
                "content_type": content_type,
                "cover_type": cover_type,
                "autoconvert": autoconvert,
            }
        )
        return CoverImage(media_id="cover-1", media_url="https://cdn.test/cover.png")


class FakeIconGateway:
    def __init__(
        self, public: list[Icon] | None = None, mine: list[Icon] | None = None
    ):
        self.public = public or []
        self.mine = mine or []
        self.uploads: list[dict[str, Any]] = []

    def list_public(self) -> list[Icon]:
        return self.public

    def list_mine(self) -> list[Icon]:
        return self.mine

    def upload(self, data: bytes, *, filename: str, autoconvert: bool) -> Icon:
        self.uploads.append(
            {"bytes": data, "filename": filename, "autoconvert": autoconvert}
        )
        return Icon(media_id="icon-1")


class FakeDeviceGateway:
    def __init__(self, devices: list[Device], details: DeviceDetails | None = None):
        self.devices = devices
        self.details = details
        self.put_calls: list[dict[str, Any]] = []

    def list_devices(self) -> list[Device]:
        return self.devices

    def get_details(self, device_id: str) -> DeviceDetails:
        assert self.details is not None
        return self.details

    def put_config(
        self, device_id: str, *, name: str | None, config: dict[str, Any]
    ) -> None:
        self.put_calls.append({"device_id": device_id, "name": name, "config": config})
        assert self.details is not None
        self.details = self.details.model_copy(update={"config": config})


class FakeLibraryGateway:
    def __init__(self) -> None:
        self.groups: dict[str, LibraryGroup] = {}
        self.updates: list[tuple[str, LibraryGroup]] = []

    def list_groups(self) -> list[LibraryGroup]:
        return list(self.groups.values())

    def get_group(self, group_id: str) -> LibraryGroup:
        try:
            return self.groups[group_id]
        except KeyError:
            raise NotFoundError(f"Group {group_id} does not exist.") from None

    def create_group(self, group: LibraryGroup) -> LibraryGroup:
        created = group.model_copy(update={"id": f"g{len(self.groups) + 1}"})
        assert created.id is not None
        self.groups[created.id] = created
        return created

    def update_group(self, group_id: str, group: LibraryGroup) -> LibraryGroup:
        self.updates.append((group_id, group))
        stored = group.model_copy(update={"id": group_id})
        self.groups[group_id] = stored
        return stored

    def delete_group(self, group_id: str) -> None:
        self.groups.pop(group_id, None)


class FakePlayerGateway:
    """Scripted PlayerGateway: records sends, returns canned ack/status."""

    def __init__(self, status: PlayerStatus | None = None, ok: bool = True) -> None:
        self.status = status or PlayerStatus(volume=8, user_volume=8)
        self.ok = ok
        self.connected: list[str] = []
        self.closed = 0
        self.sent: list[tuple[str, str, dict[str, Any]]] = []

    def connect(self, device_id: str) -> None:
        self.connected.append(device_id)

    def close(self) -> None:
        self.closed += 1

    def send(
        self, device_id: str, command: str, payload: dict[str, Any], *, timeout: float
    ) -> CommandAck:
        self.sent.append((device_id, command, payload))
        return CommandAck(resource=command, ok=self.ok)

    def request_status(self, device_id: str, *, timeout: float) -> PlayerStatus:
        return self.status

    def events(self, device_id: str) -> Iterator[PlaybackEvent]:
        return iter(())
