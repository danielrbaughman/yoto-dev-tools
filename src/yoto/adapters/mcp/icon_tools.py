"""16x16 display icon tools."""

from pathlib import Path
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from yoto.adapters.mcp._common import get_services, tool_errors
from yoto.adapters.serialize import to_jsonable
from yoto.application import icons as icons_uc
from yoto.application.icons import IconScope

Scope = Annotated[
    IconScope,
    Field(description="public (Yoto's library), private (your uploads), or all."),
]


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations={"readOnlyHint": True})
    @tool_errors
    def icon_list(scope: Scope = "public") -> list[dict[str, Any]]:
        """List 16x16 display icons. Use `yoto:#<mediaId>` as a chapter/track
        display.icon16x16 value. The public library is large; prefer icon_search."""
        return to_jsonable(icons_uc.list_icons(get_services().icons, scope=scope))

    @mcp.tool(annotations={"readOnlyHint": True})
    @tool_errors
    def icon_search(
        query: Annotated[
            str, Field(description="Case-insensitive substring of title or tags.")
        ],
        scope: Scope = "public",
    ) -> list[dict[str, Any]]:
        """Search display icons by title/tags."""
        icons = icons_uc.search_icons(get_services().icons, query, scope=scope)
        return to_jsonable(icons)

    @mcp.tool
    @tool_errors
    def icon_upload(
        path: Annotated[
            str, Field(description="Local PNG or GIF; 16x16 unless autoconvert.")
        ],
        name: Annotated[
            str | None, Field(description="Filename to store it under.")
        ] = None,
        autoconvert: Annotated[
            bool,
            Field(
                description="Let Yoto resize/convert to 16x16 PNG. Animated GIFs "
                "are always uploaded as-is."
            ),
        ] = True,
    ) -> dict[str, Any]:
        """Upload a custom icon; returns its mediaId and `yoto:#` ref."""
        icon, used_autoconvert = icons_uc.upload_icon(
            get_services().icons, Path(path), filename=name, autoconvert=autoconvert
        )
        return {
            "mediaId": icon.media_id,
            "ref": icon.ref,
            "autoconvert": used_autoconvert,
        }
