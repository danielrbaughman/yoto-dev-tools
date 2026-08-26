import json

import httpx
import pytest
import respx

from tests.conftest import load_fixture
from yoto.adapters.http.client import ApiHttp
from yoto.adapters.http.library_api import HttpFamilyImageGateway, HttpLibraryGateway
from yoto.domain.errors import ApiError, ApiValidationError
from yoto.domain.library import LibraryGroup, LibraryGroupItem


def make_http() -> ApiHttp:
    return ApiHttp(httpx.Client(base_url="https://api.test"), sleep=lambda _: None)


@respx.mock(assert_all_called=True)
def test_list_groups_parses_bare_array(respx_mock):
    respx_mock.get("https://api.test/card/family/library/groups").respond(
        json=load_fixture("groups.json")
    )
    groups = HttpLibraryGateway(make_http()).list_groups()
    assert groups[0].name == "Favourites"
    assert groups[0].cards is not None
    assert groups[0].cards[0].title == "Bedtime Stories"


@respx.mock(assert_all_called=True)
def test_create_group_body_shape(respx_mock):
    route = respx_mock.post("https://api.test/card/family/library/groups").respond(
        json={"id": "grp-9", "name": "Favs", "items": []}
    )
    group = LibraryGroup(
        name="Favs",
        image_id="fp-cards",
        items=[LibraryGroupItem(content_id="abc12")],
    )
    created = HttpLibraryGateway(make_http()).create_group(group)
    assert created.id == "grp-9"
    body = json.loads(route.calls[0].request.content)
    assert body == {
        "name": "Favs",
        "items": [{"contentId": "abc12"}],
        "imageId": "fp-cards",
    }


@respx.mock(assert_all_called=True)
def test_group_limit_maps_to_validation_error(respx_mock):
    respx_mock.post("https://api.test/card/family/library/groups").respond(
        400,
        json={
            "error": {
                "code": "group-limit",
                "message": "Maximum 20 groups can be created",
            }
        },
    )
    with pytest.raises(ApiValidationError, match="Maximum 20 groups") as excinfo:
        HttpLibraryGateway(make_http()).create_group(LibraryGroup(name="One more"))
    assert excinfo.value.code == "group-limit"


@respx.mock(assert_all_called=True)
def test_delete_group(respx_mock):
    route = respx_mock.delete(
        "https://api.test/card/family/library/groups/grp-1"
    ).respond(json={"id": "grp-1"})
    HttpLibraryGateway(make_http()).delete_group("grp-1")
    assert route.called


@respx.mock(assert_all_called=True)
def test_family_image_upload(respx_mock):
    route = respx_mock.post("https://api.test/media/family/images").respond(
        json={"imageId": "sha-1", "url": "https://api.test/media/family/images/sha-1"}
    )
    image = HttpFamilyImageGateway(make_http()).upload_image(
        b"png-bytes", content_type="image/png"
    )
    assert image.image_id == "sha-1"
    request = route.calls[0].request
    assert request.headers["Content-Type"] == "image/png"
    assert request.content == b"png-bytes"


@respx.mock(assert_all_called=True)
def test_family_image_list_limit_param(respx_mock):
    respx_mock.get(
        "https://api.test/media/family/images", params={"limit": "5"}
    ).respond(json=[{"imageId": "sha-1"}])
    images = HttpFamilyImageGateway(make_http()).list_images(limit=5)
    assert images[0].image_id == "sha-1"


@respx.mock(assert_all_called=True)
def test_family_image_resolve_returns_302_location(respx_mock):
    respx_mock.get(
        "https://api.test/media/family/images/sha-1",
        params={"width": "640", "height": "480"},
    ).respond(302, headers={"Location": "https://signed.example/sha-1?sig=x"})
    url = HttpFamilyImageGateway(make_http()).resolve_url(
        "sha-1", width=640, height=480
    )
    assert url == "https://signed.example/sha-1?sig=x"


@respx.mock(assert_all_called=True)
def test_family_image_resolve_without_location_is_api_error(respx_mock):
    respx_mock.get("https://api.test/media/family/images/sha-1").respond(302)
    with pytest.raises(ApiError, match="redirect"):
        HttpFamilyImageGateway(make_http()).resolve_url("sha-1", width=640, height=480)
