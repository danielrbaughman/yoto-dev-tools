from urllib.parse import parse_qs

import pytest
import respx

from yoto.adapters.http.oauth import Auth0Gateway
from yoto.domain.errors import ConfigError, OAuthFlowError


def make_gateway(clock, client_id="cid"):
    return Auth0Gateway(auth_url="https://login.test", client_id=client_id, clock=clock)


def form(request) -> dict[str, list[str]]:
    return parse_qs(request.content.decode())


@respx.mock(assert_all_called=True)
def test_exchange_code_sends_pkce_form(respx_mock, clock):
    route = respx_mock.post("https://login.test/oauth/token").respond(
        json={
            "access_token": "at-1",
            "refresh_token": "rt-1",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
    )
    tokens = make_gateway(clock).exchange_code(
        code="c0de", verifier="v3rif", redirect_uri="http://127.0.0.1:8787/callback"
    )
    body = form(route.calls[0].request)
    assert body["grant_type"] == ["authorization_code"]
    assert body["client_id"] == ["cid"]
    assert body["code"] == ["c0de"]
    assert body["code_verifier"] == ["v3rif"]
    assert body["redirect_uri"] == ["http://127.0.0.1:8787/callback"]
    content_type = route.calls[0].request.headers["Content-Type"]
    assert content_type == "application/x-www-form-urlencoded"
    assert tokens.access_token == "at-1"
    assert tokens.refresh_token == "rt-1"
    assert tokens.expires_at == clock.now() + 3600


@respx.mock(assert_all_called=True)
def test_refresh_rotates_refresh_token(respx_mock, clock):
    route = respx_mock.post("https://login.test/oauth/token").respond(
        json={"access_token": "at-2", "refresh_token": "rt-2", "expires_in": 3600}
    )
    tokens = make_gateway(clock).refresh("rt-1")
    assert form(route.calls[0].request)["grant_type"] == ["refresh_token"]
    assert form(route.calls[0].request)["refresh_token"] == ["rt-1"]
    assert tokens.refresh_token == "rt-2"


@respx.mock(assert_all_called=True)
def test_refresh_without_rotation_keeps_previous_token(respx_mock, clock):
    respx_mock.post("https://login.test/oauth/token").respond(
        json={"access_token": "at-2", "expires_in": 3600}
    )
    tokens = make_gateway(clock).refresh("rt-1")
    assert tokens.refresh_token == "rt-1"


@respx.mock(assert_all_called=True)
def test_missing_expires_in_falls_back_to_jwt_exp(respx_mock, clock):
    # payload {"exp": 1500000}
    jwt = "e30.eyJleHAiOiAxNTAwMDAwfQ.sig"
    respx_mock.post("https://login.test/oauth/token").respond(
        json={"access_token": jwt}
    )
    tokens = make_gateway(clock).refresh("rt-1")
    assert tokens.expires_at == 1_500_000.0


@respx.mock(assert_all_called=True)
def test_oauth_error_shape_is_parsed(respx_mock, clock):
    respx_mock.post("https://login.test/oauth/token").respond(
        403,
        json={"error": "invalid_grant", "error_description": "Unknown refresh token"},
    )
    with pytest.raises(OAuthFlowError, match="Unknown refresh token") as excinfo:
        make_gateway(clock).refresh("rt-bad")
    assert excinfo.value.error == "invalid_grant"


def test_missing_client_id_is_config_error(clock):
    with pytest.raises(ConfigError, match="dashboard.yoto.dev"):
        make_gateway(clock, client_id=None).refresh("rt")


@respx.mock(assert_all_called=True)
def test_userinfo(respx_mock, clock):
    route = respx_mock.get("https://login.test/userinfo").respond(
        json={"name": "Daniel", "email": "d@example.com"}
    )
    info = make_gateway(clock).userinfo("tok")
    assert info["name"] == "Daniel"
    assert route.calls[0].request.headers["Authorization"] == "Bearer tok"
