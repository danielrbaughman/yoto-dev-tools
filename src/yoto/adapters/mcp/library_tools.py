"""Family library tools: playlist groups and group images."""

from pathlib import Path
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from yoto.adapters.mcp._common import get_services, tool_errors
from yoto.adapters.serialize import to_jsonable
from yoto.application import library as library_uc

GroupId = Annotated[str, Field(description="Group id.")]
READ_ONLY = {"readOnlyHint": True}


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=READ_ONLY)
    @tool_errors
    def group_list() -> list[dict[str, Any]]:
        """List all playlist groups in the family library."""
        return to_jsonable(library_uc.list_groups(get_services().library))

    @mcp.tool(annotations=READ_ONLY)
    @tool_errors
    def group_get(group_id: GroupId) -> dict[str, Any]:
        """Get one group, including its resolved cards."""
        return to_jsonable(library_uc.get_group(get_services().library, group_id))

    @mcp.tool
    @tool_errors
    def group_create(
        name: Annotated[str, Field(description="Group name (max 100 chars).")],
        image_id: Annotated[
            str,
            Field(
                description="Image id: a pre-made id (e.g. fp-cards) or an uploaded "
                "family image id. The API rejects creation without one."
            ),
        ] = "fp-cards",
        content_ids: Annotated[
            list[str] | None, Field(description="Card ids to include.")
        ] = None,
    ) -> dict[str, Any]:
        """Create a playlist group."""
        group = library_uc.create_group(
            get_services().library,
            name=name,
            image_id=image_id,
            content_ids=content_ids,
        )
        return to_jsonable(group)

    @mcp.tool(annotations={"idempotentHint": True})
    @tool_errors
    def group_update(
        group_id: GroupId,
        name: Annotated[str | None, Field(description="New name.")] = None,
        image_id: Annotated[str | None, Field(description="New image id.")] = None,
        content_ids: Annotated[
            list[str] | None,
            Field(description="Card ids; REPLACES the group's items when given."),
        ] = None,
    ) -> dict[str, Any]:
        """Update a group (only the provided fields change)."""
        group = library_uc.update_group(
            get_services().library,
            group_id,
            name=name,
            image_id=image_id,
            content_ids=content_ids,
        )
        return to_jsonable(group)

    @mcp.tool(annotations={"destructiveHint": True, "idempotentHint": True})
    @tool_errors
    def group_delete(group_id: GroupId) -> dict[str, Any]:
        """Permanently delete a group (its cards are not deleted)."""
        library_uc.delete_group(get_services().library, group_id)
        return {"deleted": group_id}

    @mcp.tool(annotations=READ_ONLY)
    @tool_errors
    def group_image_list(
        limit: Annotated[int | None, Field(description="Max images to return.")] = None,
    ) -> list[dict[str, Any]]:
        """List uploaded family/group images."""
        images = library_uc.list_family_images(
            get_services().family_images, limit=limit
        )
        return to_jsonable(images)

    @mcp.tool(annotations=READ_ONLY)
    @tool_errors
    def group_image_url(
        image_id: Annotated[str, Field(description="Family image id (sha256).")],
        size: Annotated[
            str, Field(description="640x480 or 320x320 (the only supported sizes).")
        ] = "640x480",
    ) -> dict[str, Any]:
        """Resolve the signed URL of a family/group image."""
        url = library_uc.resolve_family_image_url(
            get_services().family_images, image_id, size=size
        )
        return {"imageId": image_id, "url": url}

    @mcp.tool
    @tool_errors
    def group_image_upload(
        path: Annotated[str, Field(description="Local JPEG/PNG/GIF, max 8 MB.")],
    ) -> dict[str, Any]:
        """Upload a group image; use the returned imageId in group_create/update."""
        image = library_uc.upload_family_image(get_services().family_images, Path(path))
        return {"imageId": image.image_id, "url": image.url}
