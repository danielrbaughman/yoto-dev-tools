import json

import httpx
import pytest
import respx

from tests.conftest import load_fixture
from yoto.adapters.http.client import ApiHttp
from yoto.adapters.http.content_api import HttpContentGateway
from yoto.domain.content import Card
from yoto.domain.errors import NotFoundError


def make_gateway() -> HttpContentGateway:
    return HttpContentGateway(
        ApiHttp(httpx.Client(base_url="https://api.test"), sleep=lambda _: None)
    )


@respx.mock(assert_all_called=True)
def test_list_cards(respx_mock):
    respx_mock.get("https://api.test/content/mine").respond(
        json=load_fixture("content_mine.json")
    )
    cards = make_gateway().list_cards()
    assert [card.card_id for card in cards] == ["abc12", "def34"]
    assert cards[0].metadata is not None
    assert cards[0].metadata.category == "stories"


@respx.mock(assert_all_called=True)
def test_get_card_plain(respx_mock):
    respx_mock.get("https://api.test/content/abc12").respond(
        json={"card": load_fixture("card_full.json")}
    )
    card = make_gateway().get_card("abc12")
    assert card.title == "Bedtime Stories"


@respx.mock(assert_all_called=True)
def test_get_card_playable_sends_signing_params(respx_mock):
    respx_mock.get(
        "https://api.test/content/abc12",
        params={"playable": "true", "signingType": "s3"},
    ).respond(json={"card": load_fixture("card_full.json")})
    make_gateway().get_card("abc12", playable=True)


@respx.mock(assert_all_called=True)
def test_upsert_posts_camel_case_body(respx_mock):
    route = respx_mock.post("https://api.test/content").respond(
        json={"card": {"cardId": "new01", "title": "T"}}
    )
    card = Card(title="T", card_id=None)
    created = make_gateway().upsert_card(card)
    assert created.card_id == "new01"
    body = json.loads(route.calls[0].request.content)
    assert body == {"title": "T"}  # no explicit nulls, camelCase keys


@respx.mock(assert_all_called=True)
def test_delete(respx_mock):
    route = respx_mock.delete("https://api.test/content/abc12").respond(
        json={"status": "ok"}
    )
    make_gateway().delete_card("abc12")
    assert route.called


@respx.mock(assert_all_called=True)
def test_error_envelope_maps_to_not_found(respx_mock):
    respx_mock.get("https://api.test/content/zzzzz").respond(
        404, json={"error": {"code": "not-found", "message": "Card zzzzz missing"}}
    )
    with pytest.raises(NotFoundError, match="Card zzzzz missing") as excinfo:
        make_gateway().get_card("zzzzz")
    assert excinfo.value.code == "not-found"
    assert excinfo.value.status == 404
