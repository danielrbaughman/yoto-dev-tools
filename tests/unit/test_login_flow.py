from urllib.parse import parse_qs, urlsplit

import pytest

from tests.fakes.token import (
    FakeAuthGateway,
    FakeBrowser,
    FakeReceiver,
    InMemoryTokenStore,
)
from yoto.application.auth import LoginFlow
from yoto.domain.auth import TokenSet
from yoto.domain.errors import ConfigError


def make_flow(
    *, client_id="cid", browser=None, receiver=None, gateway=None, store=None
):
    gateway = gateway or FakeAuthGateway()
    gateway.exchange_result = TokenSet(
        access_token="h.eyJzdWIiOiJ1MSJ9.s", refresh_token="r1", expires_at=2e6
    )
    notes: list[str] = []
    flow = LoginFlow(
        auth_gateway=gateway,
        receiver=receiver or FakeReceiver(),
        browser=browser or FakeBrowser(),
        store=store or InMemoryTokenStore(),
        auth_url="https://login.example",
        audience="https://api.example",
        client_id=client_id,
        scopes="openid offline_access",
        notify=notes.append,
    )
    return flow, gateway, notes


def test_happy_path_exchanges_code_and_saves_tokens():
    store = InMemoryTokenStore()
    receiver = FakeReceiver(code="the-code")
    browser = FakeBrowser()
    flow, gateway, _ = make_flow(store=store, receiver=receiver, browser=browser)
    flow.run()
    call = gateway.exchange_calls[0]
    assert call["code"] == "the-code"
    assert call["redirect_uri"] == "http://127.0.0.1:9999/callback"
    assert store.tokens is not None and store.tokens.refresh_token == "r1"
    assert receiver.closed


def test_state_in_url_matches_state_validated_by_receiver():
    receiver = FakeReceiver()
    browser = FakeBrowser()
    flow, _, _ = make_flow(receiver=receiver, browser=browser)
    flow.run()
    query = parse_qs(urlsplit(browser.opened[0]).query)
    assert query["state"] == [receiver.expected_state]
    assert query["code_challenge_method"] == ["S256"]


def test_no_browser_prints_url_instead():
    browser = FakeBrowser()
    flow, _, notes = make_flow(browser=browser)
    flow.run(open_browser=False)
    assert browser.opened == []
    assert any("https://login.example/authorize?" in note for note in notes)


def test_failed_browser_open_falls_back_to_printing():
    browser = FakeBrowser(succeed=False)
    flow, _, notes = make_flow(browser=browser)
    flow.run()
    assert any("authorize?" in note for note in notes)


def test_missing_client_id_is_a_config_error():
    flow, _, _ = make_flow(client_id=None)
    with pytest.raises(ConfigError, match="dashboard.yoto.dev"):
        flow.run()
