import pytest

from tests.conftest import load_fixture
from tests.fakes.gateways import InMemoryContentGateway
from yoto.application.content import (
    create_card,
    deep_merge,
    parse_card_input,
    update_card,
)
from yoto.domain.content import Card
from yoto.domain.errors import InputError


def test_deep_merge_merges_nested_dicts_and_replaces_scalars_and_lists():
    base = {"a": 1, "nested": {"x": 1, "y": 2}, "items": [1, 2]}
    patch = {"nested": {"y": 3, "z": 4}, "items": [9], "b": 2}
    assert deep_merge(base, patch) == {
        "a": 1,
        "nested": {"x": 1, "y": 3, "z": 4},
        "items": [9],
        "b": 2,
    }
    assert base["nested"] == {"x": 1, "y": 2}  # base untouched


def test_parse_card_input_unwraps_envelope():
    card = parse_card_input({"card": {"title": "T"}})
    assert card.title == "T"


def test_parse_card_input_rejects_non_objects():
    with pytest.raises(InputError):
        parse_card_input([1, 2])


def test_create_card_assigns_id():
    gateway = InMemoryContentGateway()
    card = create_card(gateway, {"title": "New"})
    assert card.card_id is not None


def test_update_card_merges_patch_and_preserves_unknown_fields():
    gateway = InMemoryContentGateway()
    gateway.seed(Card.model_validate(load_fixture("card_full.json")))
    updated = update_card(gateway, "abc12", {"title": "Renamed"})
    assert updated.title == "Renamed"
    api = updated.to_api()
    # unknown fields at several levels survived the fetch-merge-upsert cycle
    assert api["sortkey"] == "zz-unknown-top-level"
    assert api["content"]["activity"] == "yoto_Player"
    assert api["content"]["chapters"][0]["tracks"][0]["events"] == {
        "onEnd": {"cmd": "stop", "params": {}}
    }
    # and the patch didn't clobber siblings
    assert api["metadata"]["description"] == "Two calm stories."


def test_update_card_nested_patch():
    gateway = InMemoryContentGateway()
    gateway.seed(Card.model_validate(load_fixture("card_full.json")))
    updated = update_card(
        gateway, "abc12", {"metadata": {"description": "New description"}}
    )
    assert updated.metadata is not None
    assert updated.metadata.description == "New description"
    assert updated.metadata.category == "stories"  # sibling preserved
