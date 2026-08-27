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

2. Create an app at [dashboard.yoto.dev](https://dashboard.yoto.dev/)
   (**public client** — the CLI uses PKCE, no secret). Register the redirect
   URI **`http://127.0.0.1:8787/callback`** exactly (or another port, passed
   via `yoto auth login --port N`).

3. Put the client id where the CLI can find it — any of:
   - `.env` in the working directory: `yoto_client_id=...`
   - environment: `YOTO_CLIENT_ID=...`
   - `~/.config/yoto/config.json`: `{"client_id": "..."}`

4. `yoto auth login` — opens the browser, stores tokens in
   `~/.config/yoto/tokens.json` (0600). Refresh tokens are single-use; the CLI
   rotates and persists them atomically, and serializes concurrent invocations
   with a lock file.

Headless/CI: skip login and export `YOTO_ACCESS_TOKEN` instead (get one from a
logged-in machine with `yoto auth token`).

## MCP server

`yoto mcp` serves the same capabilities as MCP tools (33 of them: playlists,
uploads, groups, icons, players, `auth_whoami`) for Claude Code, Claude
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
