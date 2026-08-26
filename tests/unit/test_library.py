import pytest

from tests.fakes.gateways import FakeLibraryGateway
from yoto.application.library import (
    MAX_FAMILY_IMAGE_BYTES,
    create_group,
    resolve_family_image_url,
    update_group,
    upload_family_image,
)
from yoto.domain.errors import InputError


class FakeFamilyImageGateway:
    def __init__(self):
        self.uploads = []
        self.resolved = []

    def list_images(self, *, limit=None):
        return []

    def upload_image(self, data, *, content_type):
        self.uploads.append({"bytes": data, "content_type": content_type})
        from yoto.domain.media import FamilyImage

        return FamilyImage(image_id="img-1", url="https://api/img-1")

    def resolve_url(self, image_id, *, width, height):
        self.resolved.append((image_id, width, height))
        return "https://signed.example/img"


def test_create_group_builds_items():
    gateway = FakeLibraryGateway()
    group = create_group(
        gateway, name="Favs", image_id="fp-cards", content_ids=["a", "b"]
    )
    assert group.id == "g1"
    assert [item.content_id for item in group.items or []] == ["a", "b"]


def test_update_group_only_changes_provided_fields():
    gateway = FakeLibraryGateway()
    created = create_group(gateway, name="Favs", content_ids=["a"])
    assert created.id is not None
    updated = update_group(gateway, created.id, name="Renamed")
    assert updated.name == "Renamed"
    assert [item.content_id for item in updated.items or []] == ["a"]  # kept


def test_upload_family_image_validates_type_and_size(tmp_path):
    bad_type = tmp_path / "img.webp"
    bad_type.write_bytes(b"x")
    with pytest.raises(InputError, match="JPEG, PNG, or GIF"):
        upload_family_image(FakeFamilyImageGateway(), bad_type)

    too_big = tmp_path / "big.png"
    too_big.write_bytes(b"x" * (MAX_FAMILY_IMAGE_BYTES + 1))
    with pytest.raises(InputError, match="8 MB"):
        upload_family_image(FakeFamilyImageGateway(), too_big)

    ok = tmp_path / "ok.jpg"
    ok.write_bytes(b"jpeg-bytes")
    gateway = FakeFamilyImageGateway()
    image = upload_family_image(gateway, ok)
    assert image.image_id == "img-1"
    assert gateway.uploads[0]["content_type"] == "image/jpeg"


def test_resolve_family_image_url_validates_size():
    gateway = FakeFamilyImageGateway()
    url = resolve_family_image_url(gateway, "img-1", size="320x320")
    assert url == "https://signed.example/img"
    assert gateway.resolved == [("img-1", 320, 320)]
    with pytest.raises(InputError, match="640x480"):
        resolve_family_image_url(gateway, "img-1", size="100x100")
    with pytest.raises(InputError, match="Bad size"):
        resolve_family_image_url(gateway, "img-1", size="huge")
