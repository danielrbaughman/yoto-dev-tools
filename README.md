# yoto-dev-tools

`yoto` — a CLI for the [Yoto API](https://yoto.dev/api/), built for both humans
(tables, prompts, progress) and machines (`--json`, stable exit codes, strict
stdout/stderr discipline).

```console
$ yoto myo playlist list
$ yoto myo playlist create --file ./album --title "Road Trip Mix"
$ yoto player status "Kitchen Player"
$ yoto myo playlist list --json | jq -r '.[].cardId'
```

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

## Commands

```
yoto
├── auth      login | logout | whoami | token [--refresh]
├── player    list | status DEVICE | play DEVICE CARD_ID [--chapter K] [--track K]
│             pause|resume|stop DEVICE | volume DEVICE [0-100] | watch DEVICE   (MQTT)
│             light DEVICE R G B|--hex|--off | sleep DEVICE SECONDS|--off
│             config get DEVICE | config set DEVICE KEY=VALUE... [--name]   (REST)
├── mcp       [--http --host 127.0.0.1 --port 8765]   MCP server (stdio by default)
└── myo       playlist  list | get | create | update | delete
              playlist  create --file card.json|-  (schema in --help)
              playlist  create --file DIR [--title] [--cover IMG] [--icon ID]
              playlist  upload audio FILE... | upload cover FILE [--type]
              playlist  download CARD_ID [--dest DIR] [--no-cover] [--no-icons] [--overwrite]
              group     list|get|create|update|delete | images list|upload|get
              icon      list|search public|private|all | upload FILE
```

- `DEVICE` is a device id or a unique device name (case-insensitive).
- `myo playlist update` is **merge semantics**: fetched card + your JSON patch →
  upsert. Unknown/undocumented API fields are preserved losslessly.
- `myo playlist create/update --file -` reads JSON from stdin.
- `myo playlist download` saves tracks as `NN - Title.<format>` (the original
  files Yoto stores, usually opus) plus `cover.*`, `icons/`, and `card.json`
  into `./<title>/`. Re-running skips files that already exist.
- Player control needs the `family:devices:control` scope on your client.
- There is no API to link a playlist to a physical MYO card — that final step
  happens in the Yoto app/player.

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

- Tool results and inputs are the same API-native camelCase JSON as `--json`;
  `playlist_get` output is valid `playlist_update` input (deep merge).
- Errors come back as `<kind>: <message>` with kind in `not_found`, `invalid`,
  `auth_required`, `timeout`, `network`, `api_error`.
- File arguments are paths on the machine running the server.
- `yoto mcp --http [--host 127.0.0.1] [--port 8765]` serves streamable HTTP at
  `http://127.0.0.1:8765/mcp`. The endpoint has no auth of its own and acts
  with your Yoto account — keep it bound to localhost.
- Not exposed: `auth login/logout` (interactive) and `player watch` (streaming).

## Machine contract

- **stdout is data, stderr is everything else** (progress, prompts, logs,
  errors). Piping-safe; Rich disables ANSI when not a TTY and honors
  `NO_COLOR`.
- `--json` emits **API-native camelCase JSON** — `yoto myo playlist get X --json`
  output is valid `yoto myo playlist update X --file -` input.
- `yoto player watch DEVICE --json` streams **NDJSON** (one event per line,
  flushed).
- Errors in `--json` mode: stderr gets one JSON object
  `{"error": {"code", "message", "exitCode"}}`; stdout stays empty.
- Destructive commands prompt on a TTY; pass `--yes` in scripts.
- `yoto auth token` prints a bare access token for `curl`-style scripting.

### Exit codes

| code | meaning |
|-----:|---------|
| 0    | success |
| 1    | API/server/unexpected error |
| 2    | usage error |
| 3    | not found |
| 4    | auth required or failed |
| 5    | invalid input / validation / config |
| 6    | timed out (transcode, MQTT ack, login callback) |
| 7    | network failure after retries |
| 130  | interrupted |

### Environment variables

`YOTO_CLIENT_ID`, `YOTO_ACCESS_TOKEN`, `YOTO_CONFIG_DIR`, `YOTO_API_URL`,
`YOTO_AUTH_URL`, `YOTO_MQTT_HOST`, `YOTO_REDIRECT_PORT`, `YOTO_SCOPES`,
`YOTO_TIMEOUT`. Precedence: CLI flag > env > `.env` (cwd) >
`~/.config/yoto/config.json` > defaults.

## Architecture

Hexagonal (ports & adapters), `src/yoto/`:

```
domain/          pure pydantic models + error hierarchy (no I/O)
application/     use cases + ports.py (all Protocols)
adapters/
  http/          api.yotoplay.com + login.yotoplay.com gateways, retry, PKCE loopback
  mqtt/          AWS IoT websockets player control (paho)
  storage/       atomic 0600 token file + flock
  cli/           Typer commands, presenters, output/exit-code contract
  mcp/           FastMCP tools over the same use cases (`yoto mcp`)
  serialize.py   the shared --json / tool-result serializer
composition.py   the only place adapters are wired together
settings.py      pydantic-settings (env, .env, config.json)
```

Domain models use `extra="allow"` — unknown API fields round-trip untouched,
so upserts never destroy data the CLI doesn't know about.

## Development

```sh
./checks.sh                      # ty + ruff + pytest (also the pre-commit hook)
uv run pytest tests/unit         # fast, pure
uv run pytest -m integration     # respx-mocked HTTP, fake MQTT, real tmp files
YOTO_LIVE=1 uv run pytest -m live   # real API (needs creds; optional YOTO_LIVE_DEVICE)
```

Tests never touch the network or your real config except the opt-in `live`
suite. macOS/Linux only (token locking uses `fcntl`).
