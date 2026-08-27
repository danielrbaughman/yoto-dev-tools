"""Auth tools (read-only: login/logout stay interactive CLI commands)."""

from typing import Any

from fastmcp import FastMCP

from yoto.adapters.mcp._common import get_services, tool_errors
from yoto.adapters.serialize import to_jsonable
from yoto.application import auth as auth_uc


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations={"readOnlyHint": True})
    @tool_errors
    def auth_whoami() -> dict[str, Any]:
        """Show the identity behind the current credentials (and confirm the
        server is logged in). Log in with `yoto auth login` in a terminal."""
        services = get_services()
        info = auth_uc.whoami(services.token_provider, services.auth_gateway)
        return to_jsonable(info)
