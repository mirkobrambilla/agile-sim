#!/usr/bin/env sh
# Entrypoint for the agile-sim web server.
#
# - Seeds the persistent scenarios volume from the image's built-in
#   scenarios on first boot (so a fresh PVC isn't empty), without ever
#   overwriting scenarios a user has already created/edited there.
# - Execs uvicorn (via `agile-harness serve`) as the final process so it
#   receives SIGTERM directly from the container runtime / kubelet and can
#   shut down gracefully (drain in-flight requests, close connections).
set -eu

RUNS_DIR="${AGILE_SIM_RUNS_DIR:-/data/runs}"
SCENARIOS_DIR="${AGILE_SIM_SCENARIOS_DIR:-/data/scenarios}"

mkdir -p "$RUNS_DIR" "$SCENARIOS_DIR"

if [ -z "$(ls -A "$SCENARIOS_DIR" 2>/dev/null)" ]; then
  echo "entrypoint: seeding empty scenarios volume from image defaults"
  cp -r /app/scenarios/. "$SCENARIOS_DIR/"
fi

echo "entrypoint: starting agile-harness serve on ${AGILE_SIM_HOST:-0.0.0.0}:${AGILE_SIM_PORT:-8765}"
exec agile-harness serve \
  --runs-dir "$RUNS_DIR" \
  --scenarios-dir "$SCENARIOS_DIR" \
  --host "${AGILE_SIM_HOST:-0.0.0.0}" \
  --port "${AGILE_SIM_PORT:-8765}"
