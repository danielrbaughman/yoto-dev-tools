import io

import httpx
import respx

from yoto.adapters.http.client import ApiHttp
from yoto.adapters.http.media_api import HttpMediaGateway


def make_gateway() -> HttpMediaGateway:
    return HttpMediaGateway(
        ApiHttp(httpx.Client(base_url="https://api.test"), sleep=lambda _: None),
        bare_client=httpx.Client(),
    )


@respx.mock(assert_all_called=True)
def test_upload_slot_query(respx_mock):
    respx_mock.get(
        "https://api.test/media/transcode/audio/uploadUrl",
        params={"sha256": "abc", "filename": "song.mp3"},
    ).respond(json={"upload": {"uploadUrl": "https://s3.test/u", "uploadId": "id1"}})
    slot = make_gateway().request_upload_slot(sha256="abc", filename="song.mp3")
    assert slot.upload_url == "https://s3.test/u"
    assert slot.upload_id == "id1"


@respx.mock(assert_all_called=True)
def test_deduplicated_slot_has_null_url(respx_mock):
    respx_mock.get("https://api.test/media/transcode/audio/uploadUrl").respond(
        json={"upload": {"uploadUrl": None, "uploadId": "id1"}}
    )
    slot = make_gateway().request_upload_slot(sha256="abc", filename="f")
    assert slot.upload_url is None


@respx.mock(assert_all_called=True)
def test_s3_put_has_no_authorization_header(respx_mock):
    route = respx_mock.put("https://s3.test/upload").respond(200)
    make_gateway().put_object(
        "https://s3.test/upload", io.BytesIO(b"bytes"), content_type="audio/mpeg"
    )
    request = route.calls[0].request
    assert "Authorization" not in request.headers  # presigned URL: no bearer!
    assert request.headers["Content-Type"] == "audio/mpeg"
    assert request.content == b"bytes"


@respx.mock(assert_all_called=True)
def test_transcode_pending_states_return_none(respx_mock):
    respx_mock.get("https://api.test/media/upload/id1/transcoded").mock(
        side_effect=[
            httpx.Response(404),
            httpx.Response(202),
            httpx.Response(200, json={"transcode": {}}),
            httpx.Response(
                200,
                json={
                    "transcode": {
                        "transcodedSha256": "sha",
                        "transcodedInfo": {"duration": 12, "fileSize": 100},
                    }
                },
            ),
        ]
    )
    gateway = make_gateway()
    assert gateway.get_transcode("id1") is None  # 404
    assert gateway.get_transcode("id1") is None  # 202
    result = gateway.get_transcode("id1")  # 200 but no sha yet
    assert result is not None and result.transcoded_sha256 is None
    done = gateway.get_transcode("id1")
    assert done is not None and done.track_url == "yoto:#sha"


@respx.mock(assert_all_called=True)
def test_transcode_loudnorm_param(respx_mock):
    respx_mock.get(
        "https://api.test/media/upload/id1/transcoded", params={"loudnorm": "true"}
    ).respond(404)
    make_gateway().get_transcode("id1", loudnorm=True)


@respx.mock(assert_all_called=True)
def test_cover_upload_uses_lowercase_autoconvert(respx_mock):
    route = respx_mock.post(
        "https://api.test/media/coverImage/user/me/upload",
        params={"autoconvert": "true", "coverType": "myo"},
    ).respond(json={"coverImage": {"mediaId": "m1", "mediaUrl": "https://cdn/c"}})
    cover = make_gateway().upload_cover(
        b"img", content_type="image/jpeg", cover_type="myo", autoconvert=True
    )
    assert cover.media_url == "https://cdn/c"
    request = route.calls[0].request
    assert request.headers["Content-Type"] == "image/jpeg"
    assert request.content == b"img"
