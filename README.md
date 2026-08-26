# yoto-dev-tools

`yoto` — a CLI for the [Yoto API](https://yoto.dev/api/), built for both humans
(tables, prompts, progress) and machines (`--json`, stable exit codes, strict
stdout/stderr discipline).

```console
$ yoto playlist list
$ yoto playlist create-from-dir ./album --title "Road Trip Mix"
$ yoto player "Kitchen Player" status
$ yoto playlist list --json | jq -r '.[].cardId'
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
├── playlist  list | get | create | update | delete | create-from-dir
│             upload FILE...             audio → yoto:# trackUrl (dedup + transcode poll;
│                                        also aliased as bare `yoto upload`)
│             covers upload FILE [--type]
├── icons     list | search QUERY | upload FILE   [--mine]
├── devices   list | config get DEVICE | config set DEVICE KEY=VALUE...
├── player    DEVICE  play|pause|resume|stop|volume|status|watch|ambient|sleep   (MQTT)
├── library   groups  list|get|create|update|delete
└── family    images  list|upload|get
```

- `DEVICE` is a device id or a unique device name (case-insensitive).
- `playlist update` is **merge semantics**: fetched card + your JSON patch →
  upsert. Unknown/undocumented API fields are preserved losslessly.
- `playlist create/update --file -` reads JSON from stdin.
- Player control needs the `family:devices:control` scope on your client.
- There is no API to link a playlist to a physical MYO card — that final step
  happens in the Yoto app/player.

## Machine contract

- **stdout is data, stderr is everything else** (progress, prompts, logs,
  errors). Piping-safe; Rich disables ANSI when not a TTY and honors
  `NO_COLOR`.
- `--json` emits **API-native camelCase JSON** — `yoto playlist get X --json`
  output is valid `yoto playlist update X --file -` input.
- `yoto player DEVICE watch --json` streams **NDJSON** (one event per line,
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
