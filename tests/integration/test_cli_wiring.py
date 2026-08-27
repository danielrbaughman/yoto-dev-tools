"""CLI wiring for group/image/icon/cover commands via fake gateways.

The use cases are unit-tested; these pin the command surface: options,
exit codes, and JSON output shapes.
"""

import json

import pytest
from typer.testing import CliRunner

from tests.fakes.gateways import (
    FakeFamilyImageGateway,
    FakeIconGateway,
    FakeLibraryGateway,
    FakeMediaGateway,
    InMemoryContentGateway,
)
from yoto.adapters.cli import deps
from yoto.adapters.cli.app import app
from yoto.composition import build_services
from yoto.domain.content import Card
from yoto.domain.media import FamilyImage, Icon
from yoto.settings import YotoSettings

runner = CliRunner()


@pytest.fixture
def services():
    container = build_services(YotoSettings(access_token="tok"))
    container.content = InMemoryContentGateway()
    container.media = FakeMediaGateway()
    container.icons = FakeIconGateway(
        public=[Icon(media_id="pub-1", title="Moon", public_tags=["sky"])],
        mine=[Icon(media_id="mine-1", title="Mine")],
    )
    container.library = FakeLibraryGateway()
    container.family_images = FakeFamilyImageGateway(
        images=[FamilyImage(image_id="sha-1")]
    )
    deps.set_services(container)
    return container


def invoke_json(argv: list[str]):
    result = runner.invoke(app, [*argv, "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def test_group_lifecycle(services):
    created = invoke_json(["myo", "group", "create", "--name", "Faves"])
    group_id = created["id"]
    assert invoke_json(["myo", "group", "get", group_id])["name"] == "Faves"
    updated = invoke_json(["myo", "group", "update", group_id, "--name", "Best"])
    assert updated["name"] == "Best"
    human_list = runner.invoke(app, ["myo", "group", "list"])
    assert human_list.exit_code == 0 and "Best" in human_list.stdout
    deleted = runner.invoke(app, ["myo", "group", "delete", group_id, "--yes"])
    assert deleted.exit_code == 0
    assert services.library.groups == {}


def test_group_images_list_and_upload(services, tmp_path):
    assert invoke_json(["myo", "group", "images", "list"]) == [{"imageId": "sha-1"}]
    image = tmp_path / "family.png"
    image.write_bytes(b"png-bytes")
    uploaded = invoke_json(["myo", "group", "images", "upload", str(image)])
    assert uploaded["imageId"] == "sha-new"
    assert services.family_images.uploads[0]["content_type"] == "image/png"


def test_icon_search_private_and_all(services):
    assert invoke_json(["myo", "icon", "search", "private", "mine"]) == [
        {"mediaId": "mine-1", "title": "Mine"}
    ]
    combined = invoke_json(["myo", "icon", "search", "all", "m"])
    assert {icon["mediaId"] for icon in combined} == {"pub-1", "mine-1"}


def test_icon_upload(services, tmp_path):
    icon = tmp_path / "star.png"
    icon.write_bytes(b"png-bytes")
    result = invoke_json(["myo", "icon", "upload", str(icon)])
    assert result == {"mediaId": "icon-1"}
    assert services.icons.uploads[0]["filename"] == "star.png"


def test_upload_cover(services, tmp_path):
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"jpg-bytes")
    result = invoke_json(
        ["myo", "playlist", "upload", "cover", str(cover), "--type", "myo"]
    )
    assert result == {"mediaId": "cover-1", "mediaUrl": "https://cdn.test/cover.png"}
    assert services.media.cover_calls[0]["cover_type"] == "myo"


def test_playlist_update_reads_patch_from_file(services, tmp_path):
    services.content.seed(Card(card_id="abc12", title="Old"))
    patch = tmp_path / "patch.json"
    patch.write_text('{"title": "New"}', encoding="utf-8")
    result = invoke_json(["myo", "playlist", "update", "abc12", "--file", str(patch)])
    assert result["title"] == "New"


def test_playlist_update_missing_file_is_input_error(services):
    result = runner.invoke(
        app, ["myo", "playlist", "update", "abc12", "--file", "/nope/patch.json"]
    )
    assert result.exit_code == 5
