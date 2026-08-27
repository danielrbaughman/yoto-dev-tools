"""Output contract helpers.

- Data goes to stdout; progress/diagnostics/prompts go to stderr.
- --json emits API-native camelCase JSON (so `content get --json` output is
  valid `content update` input); NDJSON for streams.
- Rich handles NO_COLOR and non-TTY (no ANSI when piped) natively.
"""

import json
import sys
from collections.abc import Callable
from typing import Any

from rich.console import Console

from yoto.adapters.serialize import to_jsonable

stdout_console = Console()
stderr_console = Console(stderr=True)


def note(message: str) -> None:
    """Human-facing progress/diagnostics — always stderr."""
    stderr_console.print(message, highlight=False)


def print_json(value: Any) -> None:
    indent = 2 if sys.stdout.isatty() else None
    json.dump(to_jsonable(value), sys.stdout, indent=indent)
    sys.stdout.write("\n")


def print_json_line(value: Any) -> None:
    """One NDJSON line, flushed immediately (for watch/streaming)."""
    json.dump(to_jsonable(value), sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")
    sys.stdout.flush()


def emit(value: Any, json_mode: bool, human: Callable[[Any], None]) -> None:
    if json_mode:
        print_json(value)
    else:
        human(value)
