"""In-memory fakes for auth-related ports."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from yoto.domain.auth import TokenSet
from yoto.domain.errors import OAuthFlowError


class InMemoryTokenStore:
    def __init__(self, tokens: TokenSet | None = None) -> None:
        self.tokens = tokens
        self.log: list[str] = []

    def load(self) -> TokenSet | None:
        self.log.append("load")
        return self.tokens

    def save(self, tokens: TokenSet) -> None:
        self.log.append("save")
        self.tokens = tokens

    def clear(self) -> None:
        self.log.append("clear")
        self.tokens = None

    @contextmanager
    def lock(self) -> Iterator[None]:
        self.log.append("lock")
        yield


class FakeAuthGateway:
    """Scripted AuthGateway: returns queued TokenSets or raises."""

    def __init__(self) -> None:
        self.refresh_results: list[TokenSet | Exception] = []
        self.exchange_result: TokenSet | Exception | None = None
        self.refresh_calls: list[str] = []
        self.exchange_calls: list[dict[str, str]] = []
        self.userinfo_result: dict[str, Any] | Exception = {}
        self.log: list[str] = []

    def exchange_code(self, *, code: str, verifier: str, redirect_uri: str) -> TokenSet:
        self.exchange_calls.append(
            {"code": code, "verifier": verifier, "redirect_uri": redirect_uri}
        )
        result = self.exchange_result
        if isinstance(result, Exception):
            raise result
        if result is None:
            raise AssertionError("exchange_result not scripted")
        return result

    def refresh(self, refresh_token: str) -> TokenSet:
        self.log.append("refresh")
        self.refresh_calls.append(refresh_token)
        if not self.refresh_results:
            raise OAuthFlowError("no scripted refresh result", error="invalid_grant")
        result = self.refresh_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def userinfo(self, access_token: str) -> dict[str, Any]:
        if isinstance(self.userinfo_result, Exception):
            raise self.userinfo_result
        return self.userinfo_result


class FakeReceiver:
    """CodeReceiver that returns a scripted code and records the state check."""

    def __init__(self, code: str = "auth-code") -> None:
        self.code = code
        self.expected_state: str | None = None
        self.started = False
        self.closed = False

    def start(self) -> str:
        self.started = True
        return "http://127.0.0.1:9999/callback"

    def wait_for_code(self, *, expected_state: str, timeout: float) -> str:
        self.expected_state = expected_state
        return self.code

    def close(self) -> None:
        self.closed = True


class FakeBrowser:
    def __init__(self, succeed: bool = True) -> None:
        self.succeed = succeed
        self.opened: list[str] = []

    def open(self, url: str) -> bool:
        self.opened.append(url)
        return self.succeed
