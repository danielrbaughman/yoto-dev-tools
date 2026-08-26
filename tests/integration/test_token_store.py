import fcntl
import os
import stat

import pytest

from yoto.adapters.storage.token_store import FileTokenStore
from yoto.domain.auth import TokenSet


def make_tokens() -> TokenSet:
    return TokenSet(access_token="a1", refresh_token="r1", expires_at=2_000_000.0)


def test_save_load_round_trip(tmp_path):
    store = FileTokenStore(tmp_path / "cfg" / "tokens.json")
    store.save(make_tokens())
    loaded = store.load()
    assert loaded == make_tokens()


def test_file_and_dir_permissions(tmp_path):
    path = tmp_path / "cfg" / "tokens.json"
    FileTokenStore(path).save(make_tokens())
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


def test_missing_file_loads_none(tmp_path):
    assert FileTokenStore(tmp_path / "tokens.json").load() is None


def test_corrupt_file_loads_none(tmp_path):
    path = tmp_path / "tokens.json"
    path.write_text("{not json")
    assert FileTokenStore(path).load() is None
    path.write_text('{"access_token": 42}')
    assert FileTokenStore(path).load() is None


def test_clear_removes_file(tmp_path):
    path = tmp_path / "tokens.json"
    store = FileTokenStore(path)
    store.save(make_tokens())
    store.clear()
    assert not path.exists()
    store.clear()  # idempotent


def test_failed_replace_keeps_previous_tokens_and_no_tmp_litter(tmp_path, monkeypatch):
    path = tmp_path / "tokens.json"
    store = FileTokenStore(path)
    store.save(make_tokens())

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        store.save(TokenSet(access_token="a2", refresh_token="r2", expires_at=1.0))
    monkeypatch.undo()
    assert store.load() == make_tokens()  # old tokens intact
    assert [p.name for p in tmp_path.iterdir()] == ["tokens.json"]  # tmp cleaned


def test_lock_excludes_other_processes(tmp_path):
    path = tmp_path / "tokens.json"
    store = FileTokenStore(path)
    lock_path = tmp_path / "tokens.json.lock"
    with store.lock():
        fd = os.open(str(lock_path), os.O_RDWR)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd)
    # released afterwards
    fd = os.open(str(lock_path), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
