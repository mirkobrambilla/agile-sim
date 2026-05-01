#!/usr/bin/env bash
# Local dev: build CSS then serve the harness web UI.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
./scripts/build_css.sh
export AGILE_SIM_RUNS_DIR="${AGILE_SIM_RUNS_DIR:-$ROOT/runs}"
exec python -m uvicorn "harness.web.app:create_app" --factory --host 127.0.0.1 --port 8765 "$@"
