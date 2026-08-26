"""File-backed token store.

Yoto refresh tokens are single-use, so losing one mid-write logs the user out.
Writes are atomic (exclusive temp file + fsync + os.replace) and an fcntl lock
file serializes concurrent `yoto` invocations around load-refresh-save.
macOS/Linux only (fcntl).
"""

import fcntl
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from pydantic import ValidationError

from yoto.domain.auth import TokenSet

logger = logging.getLogger("yoto.storage")


class FileTokenStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock_path = path.with_name(path.name + ".lock")

    def load(self) -> TokenSet | None:
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        try:
            return TokenSet.model_validate_json(raw)
        except ValidationError:
            logger.warning("Ignoring corrupt token file at %s", self._path)
            return None

    def save(self, tokens: TokenSet) -> None:
        self._ensure_dir()
        tmp_path = self._path.with_name(f"{self._path.name}.{os.getpid()}.tmp")
        fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(tokens.model_dump_json())
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, self._path)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise
        os.chmod(self._path, 0o600)

    def clear(self) -> None:
        self._path.unlink(missing_ok=True)

    @contextmanager
    def lock(self) -> Iterator[None]:
        self._ensure_dir()
        fd = os.open(str(self._lock_path), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _ensure_dir(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self._path.parent, 0o700)
