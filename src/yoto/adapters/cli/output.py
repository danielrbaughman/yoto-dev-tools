"""Output contract helpers.

- Data goes to stdout; progress/diagnostics/prompts go to stderr.
- --json emits API-native camelCase JSON (so `content get --json` output is
  valid `content update` input); NDJSON for streams.
- Rich handles NO_COLOR and non-TTY (no ANSI when piped) natively.
- Human helpers never parse Rich markup in user/API-supplied strings.
"""

import json
import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from rich.console import Console, Group
from rich.live import Live
from rich.progress import (
    BarColumn,
    DownloadColumn,
    MofNCompleteColumn,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.progress import (
    Progress as RichProgress,
)
from rich.text import Text
from rich.theme import Theme

from yoto.adapters.serialize import to_jsonable

THEME = Theme(
    {
        "label": "dim",
        "id": "cyan",
        "ok": "green",
        "warn": "yellow",
        "err": "bold red",
        "muted": "dim",
        "title": "bold",
        "empty": "dim italic",
    }
)

stdout_console = Console(theme=THEME)
stderr_console = Console(stderr=True, theme=THEME)

Progress = Callable[[str], None]


def note(message: str) -> None:
    """Human-facing progress/diagnostics — always stderr, never markup."""
    stderr_console.print(message, highlight=False, markup=False)


def success(message: str) -> None:
    stderr_console.print(Text.assemble(("✓ ", "ok"), message), highlight=False)


def warn(message: str) -> None:
    stderr_console.print(Text.assemble(("⚠ ", "warn"), message), highlight=False)


def error_line(message: str, hint: str | None = None) -> None:
    stderr_console.print(Text.assemble(("error: ", "err"), message), highlight=False)
    if hint:
        stderr_console.print(Text(hint, style="muted"), highlight=False)


@contextmanager
def status(initial: str) -> Iterator[Progress]:
    """Spinner on stderr while a long operation runs (TTY only).

    Yields a progress callback that always prints a persistent line (so piped
    and test output are unchanged) and, on a terminal, also updates the
    spinner's caption.
    """
    if not stderr_console.is_terminal:
        yield note
        return
    with stderr_console.status(initial, spinner="dots") as spinner:

        def progress(line: str) -> None:
            note(line)
            spinner.update(Text(line, style="muted"))

        yield progress


class TransferBar:
    """Progress bars for multi-file transfers (TTY only; no-op otherwise).

    ``message(line)`` prints a persistent line above the bars; ``update(...)``
    drives an overall "N/M files" bar plus one byte bar per file currently in
    flight. Safe to call from worker threads (Rich serialises rendering).
    """

    def __init__(
        self,
        overall: RichProgress | None,
        files: RichProgress | None,
        description: str = "files",
    ) -> None:
        self._overall = overall
        self._files = files
        self._description = description
        self._overall_task: TaskID | None = None
        self._file_tasks: dict[str, TaskID] = {}
        self._completed = 0
        self._lock = threading.Lock()

    def message(self, line: str) -> None:
        note(line)

    def update(
        self,
        name: str,
        index: int,
        total: int,
        written: int,
        size: int | None,
        done: bool = False,
    ) -> None:
        if self._overall is None or self._files is None:
            return
        with self._lock:
            if self._overall_task is None:
                self._overall_task = self._overall.add_task(
                    self._description, total=total
                )
            task = self._file_tasks.get(name)
            if task is None:
                task = self._file_tasks[name] = self._files.add_task(name, total=size)
            self._files.update(task, completed=written, total=size)
            if done:
                self._files.remove_task(task)
                del self._file_tasks[name]
                self._completed += 1
                self._overall.update(self._overall_task, completed=self._completed)


@contextmanager
def transfer_bar(description: str) -> Iterator[TransferBar]:
    """Two stacked progress bars on stderr: files done, and bytes of the
    current file. Degrades to plain ``note`` lines when not on a terminal."""
    if not stderr_console.is_terminal:
        yield TransferBar(None, None)
        return
    overall = RichProgress(
        TextColumn("[muted]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=stderr_console,
    )
    files = RichProgress(
        TextColumn("[muted]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=stderr_console,
    )
    with Live(Group(overall, files), console=stderr_console, transient=True):
        yield TransferBar(overall, files, description)


def print_json(value: Any) -> None:
    indent = 2 if sys.stdout.isatty() else None
    json.dump(to_jsonable(value), sys.stdout, indent=indent)
    sys.stdout.write("\n")


def print_json_line(value: Any) -> None:
    """One NDJSON line, flushed immediately (for watch/streaming)."""
    json.dump(to_jsonable(value), sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")
    sys.stdout.flush()


def emit(
    value: Any, json_mode: bool, human: Callable[[Any], None] | None = None
) -> None:
    """Print `value` as JSON, or hand it to `human` (None = nothing to show)."""
    if json_mode:
        print_json(value)
    elif human is not None:
        human(value)
