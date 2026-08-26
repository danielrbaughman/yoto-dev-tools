"""Auth use cases: PKCE login flow, token session, whoami, logout."""

import base64
import binascii
import hashlib
import json
import logging
import secrets
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

from yoto.application.ports import (
    AuthGateway,
    BrowserOpener,
    Clock,
    CodeReceiver,
    TokenProvider,
    TokenStore,
)
from yoto.domain.auth import TokenSet, UserInfo
from yoto.domain.errors import (
    AuthRequiredError,
    ConfigError,
    OAuthFlowError,
    YotoError,
)

logger = logging.getLogger("yoto.auth")

REFRESH_BUFFER_SECONDS = 30.0
LOGIN_HINT = "Run `yoto auth login` to log in."


def pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, S256 code_challenge)."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def build_authorize_url(
    *,
    auth_url: str,
    audience: str,
    client_id: str,
    scopes: str,
    redirect_uri: str,
    state: str,
    challenge: str,
) -> str:
    params = {
        "audience": audience,
        "scope": scopes,
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{auth_url}/authorize?{urlencode(params)}"


def decode_jwt_claims(token: str) -> dict[str, Any]:
    """Decode a JWT's payload without verifying. Returns {} for opaque tokens."""
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1]
    try:
        raw = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        claims = json.loads(raw)
    except ValueError, binascii.Error:
        return {}
    return claims if isinstance(claims, dict) else {}


def user_info_from_token(token: str) -> UserInfo:
    claims = decode_jwt_claims(token)
    return UserInfo(
        sub=claims.get("sub"),
        scope=claims.get("scope"),
        expires_at=claims.get("exp"),
    )


class LoginFlow:
    """Authorization-code + PKCE flow over a loopback redirect."""

    def __init__(
        self,
        *,
        auth_gateway: AuthGateway,
        receiver: CodeReceiver,
        browser: BrowserOpener,
        store: TokenStore,
        auth_url: str,
        audience: str,
        client_id: str | None,
        scopes: str,
        notify: Callable[[str], None],
    ) -> None:
        self._auth_gateway = auth_gateway
        self._receiver = receiver
        self._browser = browser
        self._store = store
        self._auth_url = auth_url
        self._audience = audience
        self._client_id = client_id
        self._scopes = scopes
        self._notify = notify

    def run(self, *, timeout: float = 300.0, open_browser: bool = True) -> UserInfo:
        if not self._client_id:
            raise ConfigError(
                "No client id configured. Create one at https://dashboard.yoto.dev/ "
                "and set YOTO_CLIENT_ID (env or .env), ~/.config/yoto/config.json, "
                "or pass --client-id."
            )
        verifier, challenge = pkce_pair()
        state = secrets.token_urlsafe(16)
        redirect_uri = self._receiver.start()
        try:
            url = build_authorize_url(
                auth_url=self._auth_url,
                audience=self._audience,
                client_id=self._client_id,
                scopes=self._scopes,
                redirect_uri=redirect_uri,
                state=state,
                challenge=challenge,
            )
            if open_browser and self._browser.open(url):
                self._notify("Opened your browser for Yoto login…")
            else:
                self._notify(f"Open this URL in a browser to log in:\n\n  {url}\n")
            self._notify(
                f"Waiting for the login callback on {redirect_uri} "
                f"(this URI must be registered for your client id)…"
            )
            code = self._receiver.wait_for_code(expected_state=state, timeout=timeout)
        finally:
            self._receiver.close()
        tokens = self._auth_gateway.exchange_code(
            code=code, verifier=verifier, redirect_uri=redirect_uri
        )
        self._store.save(tokens)
        return user_info_from_token(tokens.access_token)


class AuthSession:
    """File-backed TokenProvider with proactive + reactive refresh.

    Yoto refresh tokens are single-use: every refresh returns a new one and
    invalidates the old. The store's inter-process lock is held for the whole
    load-refresh-save critical section, and the rotated token is saved before
    the new access token is handed out.
    """

    def __init__(
        self,
        store: TokenStore,
        auth_gateway: AuthGateway,
        clock: Clock,
        *,
        buffer_seconds: float = REFRESH_BUFFER_SECONDS,
    ) -> None:
        self._store = store
        self._auth_gateway = auth_gateway
        self._clock = clock
        self._buffer = buffer_seconds

    def access_token(self) -> str:
        with self._store.lock():
            tokens = self._load()
            if not tokens.expires_within(self._buffer, now=self._clock.now()):
                return tokens.access_token
            logger.debug("access token expiring; refreshing proactively")
            return self._refresh_locked(tokens)

    def on_unauthorized(self) -> str:
        with self._store.lock():
            logger.debug("got 401; forcing a token refresh")
            return self._refresh_locked(self._load())

    def _load(self) -> TokenSet:
        tokens = self._store.load()
        if tokens is None:
            raise AuthRequiredError(f"Not logged in. {LOGIN_HINT}")
        return tokens

    def _refresh_locked(self, tokens: TokenSet) -> str:
        if not tokens.refresh_token:
            raise AuthRequiredError(f"Session expired (no refresh token). {LOGIN_HINT}")
        try:
            new_tokens = self._auth_gateway.refresh(tokens.refresh_token)
        except OAuthFlowError as exc:
            if exc.error == "invalid_grant":
                self._store.clear()
                raise AuthRequiredError(
                    f"Session expired (refresh token rejected). {LOGIN_HINT}"
                ) from exc
            raise
        self._store.save(new_tokens)  # persist the rotated refresh token first
        return new_tokens.access_token


class StaticTokenProvider:
    """TokenProvider for a fixed token from YOTO_ACCESS_TOKEN (headless/CI)."""

    def __init__(self, token: str) -> None:
        self._token = token

    def access_token(self) -> str:
        return self._token

    def on_unauthorized(self) -> str:
        raise AuthRequiredError(
            "The API rejected YOTO_ACCESS_TOKEN and it cannot be refreshed. "
            "Export a fresh token (e.g. from `yoto auth token`)."
        )


def whoami(
    provider: TokenProvider, auth_gateway: AuthGateway | None = None
) -> UserInfo:
    token = provider.access_token()
    info = user_info_from_token(token)
    if auth_gateway is not None:
        try:
            extra = auth_gateway.userinfo(token)
        except YotoError as exc:  # best-effort enrichment only
            logger.debug("userinfo lookup failed: %s", exc)
        else:
            info.name = extra.get("name") or info.name
            info.email = extra.get("email") or info.email
    return info


def logout(store: TokenStore) -> None:
    store.clear()
