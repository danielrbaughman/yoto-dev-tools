"""Media gateway: audio upload slots, S3 PUT, transcode polling, covers."""

from typing import IO

import httpx

from yoto.adapters.http.client import ApiHttp
from yoto.application.ports import ChunkProgress
from yoto.domain.errors import ApiError, NetworkError
from yoto.domain.media import CoverImage, TranscodedAudio, UploadSlot

# Statuses the transcode endpoint may use for "not ready yet" (undocumented).
_TRANSCODE_PENDING_STATUSES = (202, 404)


class HttpMediaGateway:
    def __init__(self, http: ApiHttp, bare_client: httpx.Client) -> None:
        self._http = http
        # The bare client has no auth: presigned S3 URLs must NOT receive an
        # Authorization header.
        self._bare = bare_client

    def request_upload_slot(self, *, sha256: str, filename: str) -> UploadSlot:
        response = self._http.request(
            "GET",
            "/media/transcode/audio/uploadUrl",
            params={"sha256": sha256, "filename": filename},
        )
        body = response.json()
        return UploadSlot.model_validate(body.get("upload", body))

    def put_object(
        self, upload_url: str, data: IO[bytes], *, content_type: str
    ) -> None:
        try:
            response = self._bare.put(
                upload_url, content=data, headers={"Content-Type": content_type}
            )
        except httpx.TransportError as exc:
            raise NetworkError(f"Upload transfer failed: {exc}") from exc
        if not response.is_success:
            raise ApiError(
                f"Upload transfer rejected (HTTP {response.status_code}).",
                status=response.status_code,
            )

    def get_object(
        self, url: str, sink: IO[bytes], on_chunk: ChunkProgress | None = None
    ) -> int:
        written = 0
        try:
            with self._bare.stream("GET", url) as response:
                if not response.is_success:
                    raise ApiError(
                        f"Download rejected (HTTP {response.status_code}).",
                        status=response.status_code,
                    )
                length = response.headers.get("content-length")
                size = int(length) if length and length.isdigit() else None
                for chunk in response.iter_bytes():
                    sink.write(chunk)
                    written += len(chunk)
                    if on_chunk is not None:
                        on_chunk(written, size)
        except httpx.TransportError as exc:
            raise NetworkError(f"Download transfer failed: {exc}") from exc
        return written

    def get_transcode(
        self, upload_id: str, *, loudnorm: bool = False
    ) -> TranscodedAudio | None:
        response = self._http.request(
            "GET",
            f"/media/upload/{upload_id}/transcoded",
            params={"loudnorm": "true" if loudnorm else "false"},
            allowed_statuses=_TRANSCODE_PENDING_STATUSES,
        )
        if response.status_code in _TRANSCODE_PENDING_STATUSES:
            return None
        body = response.json()
        transcode = body.get("transcode") if isinstance(body, dict) else None
        if not isinstance(transcode, dict):
            return None
        return TranscodedAudio.model_validate(transcode)

    def upload_cover(
        self, data: bytes, *, content_type: str, cover_type: str, autoconvert: bool
    ) -> CoverImage:
        response = self._http.request(
            "POST",
            "/media/coverImage/user/me/upload",
            # NB: this endpoint's param is lowercase `autoconvert`; the icons
            # endpoint uses camelCase `autoConvert`.
            params={
                "autoconvert": "true" if autoconvert else "false",
                "coverType": cover_type,
            },
            content=data,
            headers={"Content-Type": content_type},
        )
        body = response.json()
        return CoverImage.model_validate(body.get("coverImage", body))
