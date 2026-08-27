"""FastMCP server assembly."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from yoto import __version__
from yoto.adapters.mcp import (
    auth_tools,
    icon_tools,
    library_tools,
    player_tools,
    playlist_tools,
)
from yoto.adapters.mcp._common import close_services
from yoto.domain.content import CARD_JSON_EXAMPLE

INSTRUCTIONS = f"""Yoto API: MYO playlists (cards), audio/cover/icon uploads, family
library groups, and Yoto player control.

Notes:
- A "card" and a "playlist" are the same object; ids are 5 characters.
- Tool results and inputs use the API's camelCase JSON. playlist_get output is
  valid playlist_update input (update is a deep merge).
- Player control tools talk to the player over MQTT; it must be online.
  Player arguments accept a device id or a unique player name.
- File inputs are paths on the machine running this server.
- If a tool fails with "auth_required", the user must run `yoto auth login`
  in a terminal.
- Linking a playlist to a physical MYO card is not possible via the API.

{CARD_JSON_EXAMPLE}
"""


@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[None]:
    try:
        yield
    finally:
        close_services()


def build_server() -> FastMCP:
    mcp = FastMCP(
        "yoto",
        instructions=INSTRUCTIONS,
        version=__version__,
        lifespan=_lifespan,
    )
    for module in (
        playlist_tools,
        library_tools,
        icon_tools,
        player_tools,
        auth_tools,
    ):
        module.register(mcp)
    return mcp
