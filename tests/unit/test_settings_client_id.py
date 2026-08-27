from yoto.settings import DEFAULT_CLIENT_ID, YotoSettings


def test_client_id_defaults_to_builtin(monkeypatch, tmp_path):
    monkeypatch.delenv("YOTO_CLIENT_ID", raising=False)
    monkeypatch.setenv("YOTO_CONFIG_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)  # no .env here
    assert YotoSettings().client_id == DEFAULT_CLIENT_ID


def test_client_id_env_overrides_builtin(monkeypatch, tmp_path):
    monkeypatch.setenv("YOTO_CLIENT_ID", "mine")
    monkeypatch.setenv("YOTO_CONFIG_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    assert YotoSettings().client_id == "mine"
