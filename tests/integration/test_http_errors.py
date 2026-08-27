"""Error-body parsing: every shape the API (and Auth0) uses for failures."""

import httpx
import pytest
import respx

from yoto.adapters.http.client import ApiHttp
from yoto.domain.errors import ApiError, ApiValidationError


def make_http() -> ApiHttp:
    return ApiHttp(httpx.Client(base_url="https://api.test"), sleep=lambda _: None)


@respx.mock(assert_all_called=True)
def test_flat_oauth_error_shape(respx_mock):
    respx_mock.get("https://api.test/x").respond(
        400, json={"error": "invalid_request", "error_description": "bad param"}
    )
    with pytest.raises(ApiValidationError, match="bad param") as excinfo:
        make_http().request("GET", "/x")
    assert excinfo.value.code == "invalid_request"


@respx.mock(assert_all_called=True)
def test_bare_message_key_fallback(respx_mock):
    respx_mock.get("https://api.test/x").respond(403, json={"message": "no entry"})
    with pytest.raises(ApiError, match="no entry"):
        make_http().request("GET", "/x")


@respx.mock(assert_all_called=True)
def test_plain_text_body_fallback(respx_mock):
    respx_mock.get("https://api.test/x").respond(403, text="tilt")
    with pytest.raises(ApiError, match="tilt"):
        make_http().request("GET", "/x")
