"""HTTP client wrapper: retries, timeouts, error mapping.

Retry policy (the Yoto docs document no rate limits, so be defensive):
- transport errors: retried; for POST only connect errors are retried, because
  a POST /content that reached the server may have created a card already.
- 502/503/504: retried for idempotent methods only.
- 429: retried for all methods (the request was not processed), honoring
  Retry-After capped at 10s, at most twice.
"""

import logging
import time
from collections.abc import Callable, Iterable
from typing import Any

import httpx

from yoto.adapters.http.errors import raise_for_status
from yoto.domain.errors import NetworkError

logger = logging.getLogger("yoto.http")

MAX_ATTEMPTS = 5
MAX_429_RETRIES = 2
RETRYABLE_STATUSES = {502, 503, 504}
IDEMPOTENT_METHODS = {"GET", "HEAD", "PUT", "DELETE"}
_CONNECT_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout)


def _retry_after_seconds(response: httpx.Response) -> float:
    try:
        return min(float(response.headers.get("Retry-After", "1")), 10.0)
    except ValueError:
        return 1.0


class ApiHttp:
    """A thin request façade shared by all HTTP gateways."""

    def __init__(
        self,
        client: httpx.Client,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self._sleep = sleep

    def request(
        self,
        method: str,
        url: str,
        *,
        allowed_statuses: Iterable[int] = (),
        **kwargs: Any,
    ) -> httpx.Response:
        method = method.upper()
        idempotent = method in IDEMPOTENT_METHODS
        attempts = 0
        retries_429 = 0
        while True:
            attempts += 1
            try:
                response = self._client.request(method, url, **kwargs)
            except httpx.TransportError as exc:
                sent = not isinstance(exc, _CONNECT_ERRORS)
                retryable = attempts < MAX_ATTEMPTS and (idempotent or not sent)
                if not retryable:
                    raise NetworkError(
                        f"{method} {url} failed after {attempts} attempt(s): {exc}"
                    ) from exc
                delay = min(0.5 * 2 ** (attempts - 1), 8.0)
                logger.debug("%s %s: %s — retrying in %.1fs", method, url, exc, delay)
                self._sleep(delay)
                continue
            status = response.status_code
            if status == 429 and retries_429 < MAX_429_RETRIES:
                retries_429 += 1
                delay = _retry_after_seconds(response)
                logger.debug("%s %s: 429 — retrying in %.1fs", method, url, delay)
                self._sleep(delay)
                continue
            if status in RETRYABLE_STATUSES and idempotent and attempts < MAX_ATTEMPTS:
                delay = min(0.5 * 2 ** (attempts - 1), 8.0)
                logger.debug(
                    "%s %s: %d — retrying in %.1fs", method, url, status, delay
                )
                self._sleep(delay)
                continue
            raise_for_status(response, allowed_statuses=allowed_statuses)
            return response

    def close(self) -> None:
        self._client.close()
