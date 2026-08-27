"""`yoto mcp`: serve the MCP server (stdio by default)."""

from typing import Annotated

import typer

from yoto.adapters.cli.errors import handle_errors
from yoto.adapters.cli.params import verbose


@verbose()
@handle_errors
def mcp(
    http: Annotated[
        bool,
        typer.Option(
            "--http",
            help="Serve streamable HTTP instead of stdio. The endpoint has no "
            "auth of its own (it acts with your Yoto credentials) — keep it on "
            "localhost.",
        ),
    ] = False,
    host: Annotated[str, typer.Option(help="HTTP bind address.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="HTTP port.")] = 8765,
) -> None:
    """Run the Yoto MCP server.

    Uses the same credentials as the CLI: log in once with `yoto auth login`,
    or export YOTO_ACCESS_TOKEN. Over stdio nothing but MCP traffic is written
    to stdout; logs go to stderr.
    """
    from yoto.adapters.mcp.server import build_server

    server = build_server()
    if http:
        server.run(transport="http", host=host, port=port, show_banner=False)
    else:
        server.run(transport="stdio", show_banner=False)
