"""Content (card/playlist) use cases."""

from typing import Any

from yoto.application.ports import ContentGateway
from yoto.domain.content import Card
from yoto.domain.errors import InputError


def list_cards(gateway: ContentGateway) -> list[Card]:
    return gateway.list_cards()


def get_card(gateway: ContentGateway, card_id: str, *, playable: bool = False) -> Card:
    return gateway.get_card(card_id, playable=playable)


def parse_card_input(data: Any) -> Card:
    """Parse user-supplied JSON (either a bare card or {"card": {...}})."""
    if isinstance(data, dict) and isinstance(data.get("card"), dict):
        data = data["card"]
    if not isinstance(data, dict):
        raise InputError("Card input must be a JSON object.")
    return Card.model_validate(data)


def create_card(gateway: ContentGateway, data: Any) -> Card:
    return gateway.upsert_card(parse_card_input(data))


def update_card(gateway: ContentGateway, card_id: str, patch: Any) -> Card:
    """Fetch-merge-upsert so partial patches never clobber unknown fields."""
    if isinstance(patch, dict) and isinstance(patch.get("card"), dict):
        patch = patch["card"]
    if not isinstance(patch, dict):
        raise InputError("Card patch must be a JSON object.")
    current = gateway.get_card(card_id)
    merged = deep_merge(current.to_api(), patch)
    merged["cardId"] = card_id
    return gateway.upsert_card(Card.model_validate(merged))


def delete_card(gateway: ContentGateway, card_id: str) -> None:
    gateway.delete_card(card_id)


def deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge dicts; lists and scalars in the patch replace."""
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
