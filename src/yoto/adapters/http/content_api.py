"""Content gateway over api.yotoplay.com."""

from yoto.adapters.http.client import ApiHttp
from yoto.domain.content import Card


class HttpContentGateway:
    def __init__(self, http: ApiHttp) -> None:
        self._http = http

    def list_cards(self) -> list[Card]:
        response = self._http.request("GET", "/content/mine")
        cards = response.json().get("cards", [])
        return [Card.model_validate(card) for card in cards]

    def get_card(self, card_id: str, *, playable: bool = False) -> Card:
        params = {"playable": "true", "signingType": "s3"} if playable else {}
        response = self._http.request("GET", f"/content/{card_id}", params=params)
        body = response.json()
        return Card.model_validate(body.get("card", body))

    def upsert_card(self, card: Card) -> Card:
        response = self._http.request("POST", "/content", json=card.to_api())
        body = response.json()
        return Card.model_validate(body.get("card", body))

    def delete_card(self, card_id: str) -> None:
        self._http.request("DELETE", f"/content/{card_id}")
