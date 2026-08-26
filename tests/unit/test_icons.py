import pytest

from tests.conftest import load_fixture
from tests.fakes.gateways import FakeIconGateway
from yoto.application.icons import is_animated_gif, search_icons, upload_icon
from yoto.domain.errors import InputError
from yoto.domain.media import Icon


def public_icons():
    return [
        Icon.model_validate(icon)
        for icon in load_fixture("icons_public.json")["displayIcons"]
    ]


def test_search_matches_title_and_tags_case_insensitively():
    gateway = FakeIconGateway(public=public_icons())
    assert {icon.title for icon in search_icons(gateway, "MOON")} == {"Moon"}
    assert {icon.title for icon in search_icons(gateway, "sky")} == {"Moon", "Star"}
    assert search_icons(gateway, "robot") == []


def test_is_animated_gif():
    static = b"GIF89a" + b"\x21\xf9\x04" + b"rest"
    animated = b"GIF89a" + b"\x21\xf9\x04" * 2 + b"rest"
    png = b"\x89PNG" + b"\x21\xf9\x04" * 5
    assert not is_animated_gif(static)
    assert is_animated_gif(animated)
    assert not is_animated_gif(png)


def test_upload_forces_no_autoconvert_for_animated_gifs(tmp_path):
    path = tmp_path / "anim.gif"
    path.write_bytes(b"GIF89a" + b"\x21\xf9\x04" * 3)
    gateway = FakeIconGateway()
    _, used_autoconvert = upload_icon(gateway, path, autoconvert=True)
    assert used_autoconvert is False
    assert gateway.uploads[0]["autoconvert"] is False
    assert gateway.uploads[0]["filename"] == "anim.gif"


def test_upload_regular_png_keeps_autoconvert(tmp_path):
    path = tmp_path / "icon.png"
    path.write_bytes(b"\x89PNGdata")
    gateway = FakeIconGateway()
    _, used_autoconvert = upload_icon(gateway, path, filename="custom.png")
    assert used_autoconvert is True
    assert gateway.uploads[0]["filename"] == "custom.png"


def test_upload_missing_file_is_input_error(tmp_path):
    with pytest.raises(InputError):
        upload_icon(FakeIconGateway(), tmp_path / "nope.png")


def test_scope_all_combines_private_then_public():
    from yoto.application.icons import list_icons

    mine = [Icon.model_validate({"mediaId": "m-mine"})]
    gateway = FakeIconGateway(public=public_icons(), mine=mine)
    combined = list_icons(gateway, scope="all")
    assert combined[0].media_id == "m-mine"  # private first, not buried
    assert len(combined) == 1 + 3
    assert {i.title for i in search_icons(gateway, "star", scope="all")} == {"Star"}
