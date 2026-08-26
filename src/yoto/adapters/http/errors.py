"""Map Yoto API error responses to domain errors.

The API envelope is {"error": {"code": "...", "message": "..."}}; OAuth
endpoints use the flat RFC 6749 {"error": "...", "error_description": "..."}.
"""

from collections.abc import Iterable

import httpx

from yoto.domain.errors import (
    ApiError,
    ApiValidationError,
    AuthRequiredError,
    NotFoundError,
)


def parse_error_body(response: httpx.Response) -> tuple[str | None, str]:
    code: str | None = None
    message = ""
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            message = error.get("message") or ""
        elif isinstance(error, str):
            code = error
            message = body.get("error_description") or ""
        else:
            message = body.get("message") or ""
    if not message:
        message = (response.text or "").strip()[:300] or response.reason_phrase
    return code, message


def raise_for_status(
    response: httpx.Response, *, allowed_statuses: Iterable[int] = ()
) -> None:
    status = response.status_code
    if response.is_success or status in allowed_statuses:
        return
    code, message = parse_error_body(response)
    detail = f"{message} (HTTP {status}" + (f", {code})" if code else ")")
    if status == 404:
        raise NotFoundError(detail, status=status, code=code)
    if status == 401:
        raise AuthRequiredError(detail)
    if status == 400:
        raise ApiValidationError(detail, status=status, code=code)
    raise ApiError(detail, status=status, code=code)
