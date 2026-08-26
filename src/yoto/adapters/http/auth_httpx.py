"""httpx auth hook: bearer tokens with proactive + reactive refresh.

This is the single place every REST request gains authentication. The
TokenProvider refreshes proactively (30s expiry buffer); on a 401 we force one
refresh and retry the request once.
"""

from collections.abc import Generator

import httpx

from yoto.application.ports import TokenProvider


class BearerAuth(httpx.Auth):
    def __init__(self, provider: TokenProvider) -> None:
        self._provider = provider

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response]:
        request.headers["Authorization"] = f"Bearer {self._provider.access_token()}"
        response = yield request
        if response.status_code == 401:
            token = self._provider.on_unauthorized()  # may raise AuthRequiredError
            request.headers["Authorization"] = f"Bearer {token}"
            yield request
