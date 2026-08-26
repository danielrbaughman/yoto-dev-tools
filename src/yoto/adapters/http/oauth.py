"""Auth0 (login.yotoplay.com) gateway: token exchange, refresh, userinfo."""

import logging
from typing import Any

import httpx

from yoto.application.auth import decode_jwt_claims
from yoto.application.ports import Clock
from yoto.domain.auth import TokenSet
from yoto.domain.errors import ConfigError, NetworkError, OAuthFlowError

logger = logging.getLogger("yoto.oauth")

_FALLBACK_LIFETIME_SECONDS = 300.0  # conservative, if the response omits expiry


class Auth0Gateway:
    def __init__(
        self,
        *,
        auth_url: str,
        client_id: str | None,
        clock: Clock,
        client: httpx.Client | None = None,
    ) -> None:
        self._client_id = client_id
        self._clock = clock
        self._client = client or httpx.Client(
            base_url=auth_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"Accept": "application/json"},
        )

    def exchange_code(self, *, code: str, verifier: str, redirect_uri: str) -> TokenSet:
        return self._token_request(
            {
                "grant_type": "authorization_code",
                "client_id": self._require_client_id(),
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": verifier,
            }
        )

    def refresh(self, refresh_token: str) -> TokenSet:
        return self._token_request(
            {
                "grant_type": "refresh_token",
                "client_id": self._require_client_id(),
                "refresh_token": refresh_token,
            },
            previous_refresh_token=refresh_token,
        )

    def userinfo(self, access_token: str) -> dict[str, Any]:
        try:
            response = self._client.get(
                "/userinfo", headers={"Authorization": f"Bearer {access_token}"}
            )
        except httpx.TransportError as exc:
            raise NetworkError(f"userinfo request failed: {exc}") from exc
        if not response.is_success:
            raise OAuthFlowError(f"userinfo failed (HTTP {response.status_code})")
        try:
            body = response.json()
        except ValueError as exc:
            raise OAuthFlowError("userinfo returned invalid JSON") from exc
        return body if isinstance(body, dict) else {}

    def close(self) -> None:
        self._client.close()

    def _require_client_id(self) -> str:
        if not self._client_id:
            raise ConfigError(
                "No client id configured. Create one at https://dashboard.yoto.dev/ "
                "and set YOTO_CLIENT_ID (env or .env) or ~/.config/yoto/config.json."
            )
        return self._client_id

    def _token_request(
        self, data: dict[str, str], *, previous_refresh_token: str | None = None
    ) -> TokenSet:
        try:
            response = self._client.post("/oauth/token", data=data)
        except httpx.TransportError as exc:
            raise NetworkError(f"Token request failed: {exc}") from exc
        if not response.is_success:
            error, description = _parse_oauth_error(response)
            raise OAuthFlowError(
                f"Token request failed: {description or error} "
                f"(HTTP {response.status_code})",
                error=error,
            )
        payload = response.json()
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise OAuthFlowError("Token response did not include an access_token.")
        expires_in = payload.get("expires_in")
        if isinstance(expires_in, int | float):
            expires_at = self._clock.now() + float(expires_in)
        else:
            exp = decode_jwt_claims(access_token).get("exp")
            expires_at = (
                float(exp)
                if isinstance(exp, int | float)
                else self._clock.now() + _FALLBACK_LIFETIME_SECONDS
            )
        # Refresh tokens rotate: prefer the new one, fall back to the one we
        # used only if the response omits it.
        refresh_token = payload.get("refresh_token") or previous_refresh_token
        return TokenSet(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )


def _parse_oauth_error(response: httpx.Response) -> tuple[str | None, str | None]:
    try:
        body = response.json()
    except ValueError:
        return None, (response.text or "").strip()[:300] or None
    if isinstance(body, dict):
        error = body.get("error")
        return (
            error if isinstance(error, str) else None,
            body.get("error_description"),
        )
    return None, None
