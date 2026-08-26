"""ApiHttp retry policy."""

import httpx
import pytest
import respx

from yoto.adapters.http.client import ApiHttp
from yoto.domain.errors import ApiError, NetworkError


def make_http(sleeps: list[float]) -> ApiHttp:
    return ApiHttp(httpx.Client(base_url="https://api.test"), sleep=sleeps.append)


@respx.mock(assert_all_called=True)
def test_get_retries_5xx_then_succeeds(respx_mock):
    respx_mock.get("https://api.test/x").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, json={"ok": 1}),
        ]
    )
    sleeps: list[float] = []
    assert make_http(sleeps).request("GET", "/x").json() == {"ok": 1}
    assert sleeps == [0.5, 1.0]  # exponential backoff


@respx.mock(assert_all_called=True)
def test_post_does_not_retry_5xx(respx_mock):
    route = respx_mock.post("https://api.test/content").respond(503)
    with pytest.raises(ApiError):
        make_http([]).request("POST", "/content")
    assert route.call_count == 1  # a replayed POST could double-create


@respx.mock(assert_all_called=True)
def test_post_does_not_retry_after_request_was_sent(respx_mock):
    route = respx_mock.post("https://api.test/content").mock(
        side_effect=httpx.ReadTimeout("read timed out")
    )
    with pytest.raises(NetworkError):
        make_http([]).request("POST", "/content")
    assert route.call_count == 1


@respx.mock(assert_all_called=True)
def test_post_retries_connect_errors(respx_mock):
    respx_mock.post("https://api.test/content").mock(
        side_effect=[
            httpx.ConnectError("refused"),
            httpx.Response(200, json={"ok": 1}),
        ]
    )
    sleeps: list[float] = []
    assert make_http(sleeps).request("POST", "/content").json() == {"ok": 1}
    assert len(sleeps) == 1


@respx.mock(assert_all_called=True)
def test_get_gives_up_after_max_attempts(respx_mock):
    route = respx_mock.get("https://api.test/x").mock(
        side_effect=httpx.ConnectError("refused")
    )
    with pytest.raises(NetworkError, match="after 5 attempt"):
        make_http([]).request("GET", "/x")
    assert route.call_count == 5


@respx.mock(assert_all_called=True)
def test_429_honors_retry_after_and_is_capped(respx_mock):
    respx_mock.get("https://api.test/x").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "3"}),
            httpx.Response(429, headers={"Retry-After": "600"}),
            httpx.Response(200, json={"ok": 1}),
        ]
    )
    sleeps: list[float] = []
    assert make_http(sleeps).request("GET", "/x").json() == {"ok": 1}
    assert sleeps == [3.0, 10.0]  # second wait capped at 10s
