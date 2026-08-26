import pytest

from tests.fakes.token import FakeAuthGateway, InMemoryTokenStore
from yoto.application.auth import AuthSession, StaticTokenProvider
from yoto.domain.auth import TokenSet
from yoto.domain.errors import AuthRequiredError, OAuthFlowError


def make_tokens(access="a1", refresh="r1", expires_at=2_000_000.0):
    return TokenSet(access_token=access, refresh_token=refresh, expires_at=expires_at)


def test_valid_token_is_returned_without_refresh(clock):
    store = InMemoryTokenStore(make_tokens(expires_at=clock.now() + 3600))
    gateway = FakeAuthGateway()
    session = AuthSession(store, gateway, clock)
    assert session.access_token() == "a1"
    assert gateway.refresh_calls == []


def test_expiring_token_is_refreshed_proactively(clock):
    store = InMemoryTokenStore(make_tokens(expires_at=clock.now() + 10))  # < 30s buffer
    gateway = FakeAuthGateway()
    gateway.refresh_results = [make_tokens("a2", "r2", clock.now() + 3600)]
    session = AuthSession(store, gateway, clock)
    assert session.access_token() == "a2"
    assert gateway.refresh_calls == ["r1"]
    assert store.tokens is not None and store.tokens.refresh_token == "r2"


def test_rotated_refresh_token_is_saved_before_use(clock):
    """Single-use refresh tokens: persist the new one before handing out the
    access token, so a crash never strands the session."""
    store = InMemoryTokenStore(make_tokens(expires_at=clock.now()))
    gateway = FakeAuthGateway()
    gateway.refresh_results = [make_tokens("a2", "r2", clock.now() + 3600)]
    combined_log = store.log  # store logs load/save; gateway appends "refresh"
    gateway.log = combined_log
    session = AuthSession(store, gateway, clock)
    session.access_token()
    assert combined_log.index("refresh") < combined_log.index("save")


def test_on_unauthorized_forces_refresh_even_if_token_looks_valid(clock):
    store = InMemoryTokenStore(make_tokens(expires_at=clock.now() + 3600))
    gateway = FakeAuthGateway()
    gateway.refresh_results = [make_tokens("a2", "r2", clock.now() + 3600)]
    session = AuthSession(store, gateway, clock)
    assert session.on_unauthorized() == "a2"


def test_invalid_grant_clears_store_and_asks_for_login(clock):
    store = InMemoryTokenStore(make_tokens(expires_at=clock.now()))
    gateway = FakeAuthGateway()
    gateway.refresh_results = [OAuthFlowError("nope", error="invalid_grant")]
    session = AuthSession(store, gateway, clock)
    with pytest.raises(AuthRequiredError, match="auth login"):
        session.access_token()
    assert store.tokens is None


def test_other_oauth_errors_propagate(clock):
    store = InMemoryTokenStore(make_tokens(expires_at=clock.now()))
    gateway = FakeAuthGateway()
    gateway.refresh_results = [OAuthFlowError("server sad", error="server_error")]
    session = AuthSession(store, gateway, clock)
    with pytest.raises(OAuthFlowError):
        session.access_token()
    assert store.tokens is not None  # not cleared


def test_no_tokens_raises_auth_required(clock):
    session = AuthSession(InMemoryTokenStore(), FakeAuthGateway(), clock)
    with pytest.raises(AuthRequiredError, match="Not logged in"):
        session.access_token()


def test_no_refresh_token_raises_auth_required(clock):
    store = InMemoryTokenStore(make_tokens(refresh=None, expires_at=clock.now()))
    session = AuthSession(store, FakeAuthGateway(), clock)
    with pytest.raises(AuthRequiredError, match="expired"):
        session.access_token()


def test_static_provider_returns_token_and_never_refreshes():
    provider = StaticTokenProvider("env-token")
    assert provider.access_token() == "env-token"
    with pytest.raises(AuthRequiredError, match="YOTO_ACCESS_TOKEN"):
        provider.on_unauthorized()
