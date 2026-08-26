"""Icon gateway."""

from yoto.adapters.http.client import ApiHttp
from yoto.domain.media import Icon


class HttpIconGateway:
    def __init__(self, http: ApiHttp) -> None:
        self._http = http

    def list_public(self) -> list[Icon]:
        return self._list("/media/displayIcons/user/yoto")

    def list_mine(self) -> list[Icon]:
        return self._list("/media/displayIcons/user/me")

    def upload(self, data: bytes, *, filename: str, autoconvert: bool) -> Icon:
        response = self._http.request(
            "POST",
            "/media/displayIcons/user/me/upload",
            # NB: camelCase `autoConvert` here, unlike covers' `autoconvert`.
            params={
                "autoConvert": "true" if autoconvert else "false",
                "filename": filename,
            },
            content=data,
            headers={"Content-Type": _content_type_for(filename)},
        )
        body = response.json()
        return Icon.model_validate(body.get("displayIcon", body))

    def _list(self, path: str) -> list[Icon]:
        response = self._http.request("GET", path)
        body = response.json()
        icons = body.get("displayIcons", body) if isinstance(body, dict) else body
        return [Icon.model_validate(icon) for icon in icons or []]


def _content_type_for(filename: str) -> str:
    if filename.lower().endswith(".gif"):
        return "image/gif"
    return "image/png"
