"""BearerAuth: proactive token injection + one reactive refresh on 401."""

import httpx
import pytest
import respx

from yoto.adapters.http.auth_httpx import BearerAuth
from yoto.adapters.http.client import ApiHttp
from yoto.domain.errors import AuthRequiredError


class SequenceProvider:
    def __init__(self, tokens: list[str]) -> None:
        self.tokens = tokens
        self.unauthorized_calls = 0

    def access_token(self) -> str:
        return self.tokens[0]

    def on_unauthorized(self) -> str:
        self.unauthorized_calls += 1
        if len(self.tokens) > 1:
            self.tokens.pop(0)
            return self.tokens[0]
        raise AuthRequiredError("refresh failed")


def make_http(provider) -> ApiHttp:
    client = httpx.Client(base_url="https://api.test", auth=BearerAuth(provider))
    return ApiHttp(client, sleep=lambda _: None)


@respx.mock(assert_all_called=True)
def test_success_sends_bearer_header(respx_mock):
    route = respx_mock.get("https://api.test/thing").respond(json={"ok": True})
    make_http(SequenceProvider(["tok-1"])).request("GET", "/thing")
    assert route.calls[0].request.headers["Authorization"] == "Bearer tok-1"


@respx.mock(assert_all_called=True)
def test_401_triggers_one_refresh_and_retry(respx_mock):
    route = respx_mock.get("https://api.test/thing").mock(
        side_effect=[httpx.Response(401), httpx.Response(200, json={"ok": True})]
    )
    provider = SequenceProvider(["stale", "fresh"])
    response = make_http(provider).request("GET", "/thing")
    assert response.status_code == 200
    assert provider.unauthorized_calls == 1
    assert route.calls[0].request.headers["Authorization"] == "Bearer stale"
    assert route.calls[1].request.headers["Authorization"] == "Bearer fresh"


@respx.mock(assert_all_called=True)
def test_second_401_maps_to_auth_required(respx_mock):
    respx_mock.get("https://api.test/thing").respond(401)
    provider = SequenceProvider(["stale", "still-bad"])
    with pytest.raises(AuthRequiredError):
        make_http(provider).request("GET", "/thing")
    assert provider.unauthorized_calls == 1


@respx.mock(assert_all_called=True)
def test_failed_refresh_propagates_auth_required(respx_mock):
    respx_mock.get("https://api.test/thing").respond(401)
    provider = SequenceProvider(["stale"])  # on_unauthorized raises
    with pytest.raises(AuthRequiredError, match="refresh failed"):
        make_http(provider).request("GET", "/thing")
