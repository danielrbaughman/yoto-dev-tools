# yoto-dev-tools

A CLI and MCP for the [Yoto API](https://yoto.dev/api/)

## Setup

1. Install [uv](https://docs.astral.sh/uv/), then:

   ```sh
   ./setup.sh              # dev env: uv sync + pre-commit hook
   ./install.sh            # install the `yoto` command (uv tool, ~/.local/bin)
   yoto --help             # or, without installing: uv run yoto --help
   ```

   Re-run `./install.sh` after pulling changes — it rebuilds from the
   current sources.

2. `yoto auth login` — opens the browser, stores tokens in
   `~/.config/yoto/tokens.json` (0600). Refresh tokens are single-use; the CLI
   rotates and persists them atomically, and serializes concurrent invocations
   with a lock file.

Headless/CI: skip login and export `YOTO_ACCESS_TOKEN` instead (get one from a
logged-in machine with `yoto auth token`).

## MCP server

`yoto mcp` serves the same capabilities as MCP tools (34 of them: playlists,
downloads, uploads, groups, icons, players, `auth_whoami`) for Claude Code, Claude
Desktop, and any other MCP client. It reuses the CLI's credentials — run
`yoto auth login` once (or export `YOTO_ACCESS_TOKEN`), then:

```sh
claude mcp add yoto -- yoto mcp          # Claude Code
```

Claude Desktop (`claude_desktop_config.json`):

```json
{"mcpServers": {"yoto": {"command": "yoto", "args": ["mcp"]}}}
```

`yoto mcp --http [--host 127.0.0.1] [--port 8765]` serves streamable HTTP at
`http://127.0.0.1:8765/mcp`. The endpoint has no auth of its own and acts
with your Yoto account — keep it bound to localhost.
