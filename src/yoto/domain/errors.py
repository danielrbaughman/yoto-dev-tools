"""Domain error hierarchy.

Every error the CLI intentionally surfaces derives from YotoError; the CLI maps
each subtype to a stable exit code (see adapters/cli/errors.py).
"""


class YotoError(Exception):
    """Base for all yoto errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ConfigError(YotoError):
    """Missing or invalid configuration (e.g. no client id)."""


class AuthError(YotoError):
    """Base for authentication problems."""


class AuthRequiredError(AuthError):
    """No usable credentials: not logged in, refresh failed, or token rejected."""


class OAuthFlowError(AuthError):
    """The OAuth flow itself failed (state mismatch, token endpoint error, ...)."""

    def __init__(self, message: str, *, error: str | None = None) -> None:
        super().__init__(message)
        self.error = error


class ApiError(YotoError):
    """The Yoto API returned an error response."""

    def __init__(
        self, message: str, *, status: int | None = None, code: str | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class NotFoundError(ApiError):
    """The requested resource does not exist (HTTP 404, or local resolution)."""


class ApiValidationError(ApiError):
    """The API rejected the request as invalid (HTTP 400)."""


class InputError(YotoError):
    """User-supplied input is invalid (bad JSON file, oversized upload, ...)."""


class NetworkError(YotoError):
    """Transport-level failure after retries."""


class OperationTimeout(YotoError):
    """A logical wait timed out (transcode poll, MQTT ack, login callback)."""


class MqttError(YotoError):
    """MQTT connect/subscribe/publish failure."""
