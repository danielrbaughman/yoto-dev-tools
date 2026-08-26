"""Family library gateways: groups and family images."""

from yoto.adapters.http.client import ApiHttp
from yoto.domain.errors import ApiError
from yoto.domain.library import LibraryGroup
from yoto.domain.media import FamilyImage

_GROUPS = "/card/family/library/groups"


class HttpLibraryGateway:
    def __init__(self, http: ApiHttp) -> None:
        self._http = http

    def list_groups(self) -> list[LibraryGroup]:
        response = self._http.request("GET", _GROUPS)
        body = response.json()  # a bare JSON array, not an envelope
        groups = body if isinstance(body, list) else body.get("groups", [])
        return [LibraryGroup.model_validate(group) for group in groups]

    def get_group(self, group_id: str) -> LibraryGroup:
        response = self._http.request("GET", f"{_GROUPS}/{group_id}")
        return LibraryGroup.model_validate(response.json())

    def create_group(self, group: LibraryGroup) -> LibraryGroup:
        response = self._http.request("POST", _GROUPS, json=_group_body(group))
        return LibraryGroup.model_validate(response.json())

    def update_group(self, group_id: str, group: LibraryGroup) -> LibraryGroup:
        response = self._http.request(
            "PUT", f"{_GROUPS}/{group_id}", json=_group_body(group)
        )
        return LibraryGroup.model_validate(response.json())

    def delete_group(self, group_id: str) -> None:
        self._http.request("DELETE", f"{_GROUPS}/{group_id}")


def _group_body(group: LibraryGroup) -> dict[str, object]:
    body: dict[str, object] = {
        "name": group.name,
        "items": [{"contentId": item.content_id} for item in group.items or []],
    }
    if group.image_id is not None:
        body["imageId"] = group.image_id
    return body


class HttpFamilyImageGateway:
    def __init__(self, http: ApiHttp) -> None:
        self._http = http

    def list_images(self, *, limit: int | None = None) -> list[FamilyImage]:
        params = {"limit": str(limit)} if limit is not None else {}
        response = self._http.request("GET", "/media/family/images", params=params)
        body = response.json()
        images = body if isinstance(body, list) else body.get("images", [])
        return [FamilyImage.model_validate(image) for image in images]

    def upload_image(self, data: bytes, *, content_type: str) -> FamilyImage:
        response = self._http.request(
            "POST",
            "/media/family/images",
            content=data,
            headers={"Content-Type": content_type},
        )
        return FamilyImage.model_validate(response.json())

    def resolve_url(self, image_id: str, *, width: int, height: int) -> str:
        response = self._http.request(
            "GET",
            f"/media/family/images/{image_id}",
            params={"width": str(width), "height": str(height)},
            allowed_statuses=(302,),
        )
        location = response.headers.get("Location")
        if not location:
            raise ApiError(
                f"Expected a redirect for family image {image_id} "
                f"(got HTTP {response.status_code})."
            )
        return location
