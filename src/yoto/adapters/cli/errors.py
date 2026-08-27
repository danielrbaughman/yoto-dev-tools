"""Error handling: one mapping from domain errors to stable exit codes.

| exit | meaning                     |
|------|-----------------------------|
| 0    | success                     |
| 1    | API/server/unexpected error |
| 2    | usage error (Typer/Click)   |
| 3    | not found                   |
| 4    | auth required/failed        |
| 5    | invalid input/config        |
| 6    | timed out                   |
| 7    | network failure             |
| 130  | interrupted (Ctrl-C)        |
"""

import functools
import json
import sys
from collections.abc import Callable
from typing import Any

import typer

from yoto.adapters.cli.output import error_line
from yoto.domain.errors import (
    ApiValidationError,
    AuthError,
    ConfigError,
    InputError,
    NetworkError,
    NotFoundError,
    OperationTimeout,
    YotoError,
)

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_NOT_FOUND = 3
EXIT_AUTH = 4
EXIT_INVALID = 5
EXIT_TIMEOUT = 6
EXIT_NETWORK = 7
EXIT_INTERRUPTED = 130

# Ordered: first isinstance match wins (subclasses before bases).
_EXIT_MAP: list[tuple[type[YotoError], int]] = [
    (NotFoundError, EXIT_NOT_FOUND),
    (ApiValidationError, EXIT_INVALID),
    (AuthError, EXIT_AUTH),
    (ConfigError, EXIT_INVALID),
    (InputError, EXIT_INVALID),
    (OperationTimeout, EXIT_TIMEOUT),
    (NetworkError, EXIT_NETWORK),
    (YotoError, EXIT_ERROR),
]


def exit_code_for(error: YotoError) -> int:
    for error_type, code in _EXIT_MAP:
        if isinstance(error, error_type):
            return code
    return EXIT_ERROR


def report_error(error: YotoError, *, json_mode: bool) -> None:
    """Human one-liner, or a JSON error object in --json mode — on stderr
    either way; stdout stays clean on failure."""
    exit_code = exit_code_for(error)
    if json_mode:
        payload = {
            "error": {
                "code": getattr(error, "code", None) or type(error).__name__,
                "message": error.message,
                "exitCode": exit_code,
            }
        }
        json.dump(payload, sys.stderr)
        sys.stderr.write("\n")
    else:
        hint = (
            "Run `yoto auth login` to sign in."
            if isinstance(error, AuthError)
            else None
        )
        error_line(error.message, hint)


def handle_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """Command decorator: map domain errors to exit codes + stderr output."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        json_mode = bool(kwargs.get("json_", False))
        try:
            return func(*args, **kwargs)
        except YotoError as error:
            report_error(error, json_mode=json_mode)
            raise typer.Exit(exit_code_for(error)) from error
        except KeyboardInterrupt:
            raise typer.Exit(EXIT_INTERRUPTED) from None
        except BrokenPipeError:
            raise typer.Exit(EXIT_OK) from None

    return wrapper
