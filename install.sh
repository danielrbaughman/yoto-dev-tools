#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Install the `yoto` CLI as a uv tool (isolated env, ~/.local/bin/yoto).
# --reinstall rebuilds from the current sources, so re-running picks up edits.
uv tool install --force --reinstall .

"$(uv tool dir --bin)/yoto" --version
