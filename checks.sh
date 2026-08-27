#!/usr/bin/env bash
set -euo pipefail

uv run ty check
uv run ruff check
uv run ruff format
uv run pytest -m "not live" --cov --cov-report=term
