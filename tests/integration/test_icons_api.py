import httpx
import respx

from tests.conftest import load_fixture
from yoto.adapters.http.client import ApiHttp
from yoto.adapters.http.icons_api import HttpIconGateway


def make_gateway() -> HttpIconGateway:
    return HttpIconGateway(
        ApiHttp(httpx.Client(base_url="https://api.test"), sleep=lambda _: None)
    )


@respx.mock(assert_all_called=True)
def test_list_public_and_mine_paths(respx_mock):
    respx_mock.get("https://api.test/media/displayIcons/user/yoto").respond(
        json=load_fixture("icons_public.json")
    )
    respx_mock.get("https://api.test/media/displayIcons/user/me").respond(
        json={"displayIcons": []}
    )
    gateway = make_gateway()
    assert len(gateway.list_public()) == 3
    assert gateway.list_mine() == []


@respx.mock(assert_all_called=True)
def test_upload_uses_camel_case_autoconvert(respx_mock):
    route = respx_mock.post(
        "https://api.test/media/displayIcons/user/me/upload",
        params={"autoConvert": "false", "filename": "anim.gif"},
    ).respond(json={"displayIcon": {"mediaId": "m1", "url": {}, "new": True}})
    icon = make_gateway().upload(b"gifdata", filename="anim.gif", autoconvert=False)
    assert icon.media_id == "m1"
    assert icon.url is None  # "url": {} tolerated
    request = route.calls[0].request
    assert request.headers["Content-Type"] == "image/gif"
    assert request.content == b"gifdata"


@respx.mock(assert_all_called=True)
def test_upload_png_content_type(respx_mock):
    route = respx_mock.post(
        "https://api.test/media/displayIcons/user/me/upload",
        params={"autoConvert": "true", "filename": "icon.png"},
    ).respond(json={"displayIcon": {"mediaId": "m2"}})
    make_gateway().upload(b"png", filename="icon.png", autoconvert=True)
    assert route.calls[0].request.headers["Content-Type"] == "image/png"
