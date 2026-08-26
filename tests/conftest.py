"""Shared fixtures: full environment isolation + fake clock + fixture loader."""

import json
import os
from pathlib import Path
from typing import Any

import pytest

from yoto.adapters.cli import deps

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        path = str(item.fspath)
        if "/integration/" in path:
            item.add_marker(pytest.mark.integration)
        if "/live/" in path:
            item.add_marker(pytest.mark.live)


@pytest.fixture(autouse=True)
def _isolated_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Keep tests away from the real config dir, repo .env, and env vars."""
    if "live" in {marker.name for marker in request.node.iter_markers()}:
        return  # live tests use the real environment
    for key in list(os.environ):
        if key.upper().startswith("YOTO_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("YOTO_CONFIG_DIR", str(tmp_path / "yoto-config"))
    monkeypatch.chdir(tmp_path)
    deps.set_services(None)
    request.addfinalizer(lambda: deps.set_services(None))


class FakeClock:
    def __init__(self, start: float = 1_000_000.0) -> None:
        self.current = start
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.current += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()
