"""End-to-end CLI tests: CliRunner -> real composition -> respx-mocked API.

These pin the machine contract: JSON shapes, exit codes, stdout/stderr split.
"""

import base64
import json

import pytest
import respx
from typer.testing import CliRunner

from tests.conftest import load_fixture
from yoto.adapters.cli.app import app

runner = CliRunner()

API = "https://api.yotoplay.com"
LOGIN = "https://login.yotoplay.com"


def jwt_for(claims: dict) -> str:
    def b64(part: dict) -> str:
        raw = json.dumps(part).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return f"{b64({'alg': 'none'})}.{b64(claims)}.sig"


@pytest.fixture
def logged_in(monkeypatch):
    monkeypatch.setenv(
        "YOTO_ACCESS_TOKEN",
        jwt_for({"sub": "auth0|dan", "scope": "openid", "exp": 9_999_999_999}),
    )


@respx.mock(assert_all_called=True)
def test_content_list_json_outputs_api_shape(respx_mock, logged_in):
    respx_mock.get(f"{API}/content/mine").respond(
        json=load_fixture("content_mine.json")
    )
    result = runner.invoke(app, ["playlist", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert [card["cardId"] for card in data] == ["abc12", "def34"]
    assert data[0]["metadata"]["category"] == "stories"  # camelCase, API-native


@respx.mock(assert_all_called=True)
def test_content_list_human_table(respx_mock, logged_in):
    respx_mock.get(f"{API}/content/mine").respond(
        json=load_fixture("content_mine.json")
    )
    result = runner.invoke(app, ["playlist", "list"])
    assert result.exit_code == 0
    assert "Bedtime Stories" in result.stdout
    assert "2 card(s)" in result.stdout


@respx.mock(assert_all_called=True)
def test_content_get_json_round_trips_unknown_fields(respx_mock, logged_in):
    respx_mock.get(f"{API}/content/abc12").respond(
        json={"card": load_fixture("card_full.json")}
    )
    result = runner.invoke(app, ["playlist", "get", "abc12", "--json"])
    assert result.exit_code == 0
    card = json.loads(result.stdout)
    assert card["sortkey"] == "zz-unknown-top-level"
    assert card["content"]["chapters"][0]["display"]["icon16x16"].startswith("yoto:#")


@respx.mock(assert_all_called=True)
def test_content_update_merges_patch_from_stdin(respx_mock, logged_in):
    respx_mock.get(f"{API}/content/abc12").respond(
        json={"card": load_fixture("card_full.json")}
    )
    post = respx_mock.post(f"{API}/content").respond(
        json={"card": {"cardId": "abc12", "title": "Renamed"}}
    )
    result = runner.invoke(
        app,
        ["playlist", "update", "abc12", "--file", "-", "--json"],
        input='{"title": "Renamed"}',
    )
    assert result.exit_code == 0
    body = json.loads(post.calls[0].request.content)
    assert body["title"] == "Renamed"
    assert body["cardId"] == "abc12"
    assert body["sortkey"] == "zz-unknown-top-level"  # unknown fields survived
    assert body["metadata"]["description"] == "Two calm stories."


@respx.mock(assert_all_called=True)
def test_not_found_maps_to_exit_3_with_clean_stdout(respx_mock, logged_in):
    respx_mock.get(f"{API}/content/zzzzz").respond(
        404, json={"error": {"code": "not-found", "message": "Card zzzzz missing"}}
    )
    result = runner.invoke(app, ["playlist", "get", "zzzzz"])
    assert result.exit_code == 3
    assert result.stdout == ""
    assert "error: Card zzzzz missing" in result.stderr


@respx.mock(assert_all_called=True)
def test_json_mode_emits_error_object_on_stderr(respx_mock, logged_in):
    respx_mock.get(f"{API}/content/zzzzz").respond(
        404, json={"error": {"code": "not-found", "message": "Card zzzzz missing"}}
    )
    result = runner.invoke(app, ["playlist", "get", "zzzzz", "--json"])
    assert result.exit_code == 3
    assert result.stdout == ""
    error = json.loads(result.stderr)["error"]
    assert error["code"] == "not-found"
    assert error["exitCode"] == 3


def test_missing_credentials_maps_to_exit_4():
    result = runner.invoke(app, ["playlist", "list"])
    assert result.exit_code == 4
    assert "Not logged in" in result.stderr


def test_bad_json_input_maps_to_exit_5(logged_in):
    result = runner.invoke(
        app, ["playlist", "create", "--file", "-", "--json"], input="{nope"
    )
    assert result.exit_code == 5
    assert json.loads(result.stderr)["error"]["exitCode"] == 5


@respx.mock(assert_all_called=True)
def test_delete_requires_confirmation_and_yes_skips_it(respx_mock, logged_in):
    route = respx_mock.delete(f"{API}/content/abc12").respond(json={"status": "ok"})
    aborted = runner.invoke(app, ["playlist", "delete", "abc12"], input="n\n")
    assert aborted.exit_code != 0
    assert not route.called
    confirmed = runner.invoke(app, ["playlist", "delete", "abc12", "--yes"])
    assert confirmed.exit_code == 0
    assert route.called
    assert "Deleted abc12." in confirmed.stderr


@respx.mock(assert_all_called=True)
def test_whoami_merges_userinfo(respx_mock, logged_in):
    respx_mock.get(f"{LOGIN}/userinfo").respond(
        json={"name": "Daniel", "email": "dan@example.com"}
    )
    result = runner.invoke(app, ["auth", "whoami", "--json"])
    assert result.exit_code == 0
    info = json.loads(result.stdout)
    assert info["sub"] == "auth0|dan"
    assert info["name"] == "Daniel"


@respx.mock(assert_all_called=True)
def test_whoami_survives_userinfo_failure(respx_mock, logged_in):
    respx_mock.get(f"{LOGIN}/userinfo").respond(500)
    result = runner.invoke(app, ["auth", "whoami", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["sub"] == "auth0|dan"


def test_auth_token_prints_bare_token(logged_in, monkeypatch):
    result = runner.invoke(app, ["auth", "token"])
    assert result.exit_code == 0
    assert result.stdout.strip().count(".") == 2  # the JWT, nothing else


@respx.mock(assert_all_called=True)
def test_upload_end_to_end(respx_mock, logged_in, tmp_path):
    audio = tmp_path / "song.mp3"
    audio.write_bytes(b"audio")
    respx_mock.get(f"{API}/media/transcode/audio/uploadUrl").respond(
        json={"upload": {"uploadUrl": "https://s3.test/put", "uploadId": "u1"}}
    )
    put = respx_mock.put("https://s3.test/put").respond(200)
    respx_mock.get(f"{API}/media/upload/u1/transcoded").respond(
        json={
            "transcode": {
                "transcodedSha256": "shaX",
                "transcodedInfo": {"duration": 9, "fileSize": 5, "format": "aac"},
            }
        }
    )
    result = runner.invoke(app, ["playlist", "upload", "audio", str(audio), "--json"])
    assert result.exit_code == 0
    assert "Authorization" not in put.calls[0].request.headers
    (entry,) = json.loads(result.stdout)
    assert entry["transcodedSha256"] == "shaX"
    assert entry["file"] == str(audio)
    # progress went to stderr, not stdout
    assert "Uploading" in result.stderr


def test_upload_group_has_audio_and_cover():
    assert runner.invoke(app, ["playlist", "upload", "audio", "--help"]).exit_code == 0
    assert runner.invoke(app, ["playlist", "upload", "cover", "--help"]).exit_code == 0


def test_create_from_dir_nests_under_create():
    assert (
        runner.invoke(app, ["playlist", "create", "from-dir", "--help"]).exit_code == 0
    )
    # bare `create` without --file explains both forms
    result = runner.invoke(app, ["playlist", "create"])
    assert result.exit_code == 5
    assert "from-dir" in result.stderr


def test_bare_upload_is_gone():
    assert runner.invoke(app, ["upload", "--help"]).exit_code == 2


@respx.mock(assert_all_called=True)
def test_devices_list(respx_mock, logged_in):
    respx_mock.get(f"{API}/device-v2/devices/mine").respond(
        json=load_fixture("devices.json")
    )
    result = runner.invoke(app, ["devices", "list", "--json"])
    assert result.exit_code == 0
    devices = json.loads(result.stdout)
    assert devices[0]["deviceId"] == "y2AAAAAAAAAAAAAA"


@respx.mock(assert_all_called=True)
def test_icons_search_filters_public_library(respx_mock, logged_in):
    respx_mock.get(f"{API}/media/displayIcons/user/yoto").respond(
        json=load_fixture("icons_public.json")
    )
    result = runner.invoke(app, ["icons", "search", "sky", "--json"])
    assert result.exit_code == 0
    icons = json.loads(result.stdout)
    assert {icon["title"] for icon in icons} == {"Moon", "Star"}


@respx.mock(assert_all_called=True)
def test_library_groups_list(respx_mock, logged_in):
    respx_mock.get(f"{API}/card/family/library/groups").respond(
        json=load_fixture("groups.json")
    )
    result = runner.invoke(app, ["library", "groups", "list", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)[0]["name"] == "Favourites"


@respx.mock(assert_all_called=True)
def test_family_images_get_prints_signed_url(respx_mock, logged_in):
    respx_mock.get(f"{API}/media/family/images/sha-1").respond(
        302, headers={"Location": "https://signed.example/x"}
    )
    result = runner.invoke(app, ["family", "images", "get", "sha-1", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["url"] == "https://signed.example/x"


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.startswith("yoto ")


def test_usage_error_is_exit_2():
    result = runner.invoke(app, ["playlist", "get"])  # missing CARD_ID
    assert result.exit_code == 2
