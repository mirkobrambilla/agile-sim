#!/usr/bin/env bash
# Build harness/web/static/css/app.css from Tailwind + tokens + components.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BIN="${ROOT}/tools/tailwindcss"
INPUT="${ROOT}/harness/web/static/css/_input.css"
OUT="${ROOT}/harness/web/static/css/app.css"
CFG="${ROOT}/tailwind.config.js"
mkdir -p "$(dirname "$OUT")" "${ROOT}/tools"

VER="v3.4.17"

if [[ ! -x "$BIN" ]]; then
  echo "Downloading Tailwind v3 standalone CLI into tools/ …"
  OS=$(uname -s | tr '[:upper:]' '[:lower:]')
  ARCH=$(uname -m)
  case "$OS-$ARCH" in
    darwin-arm64|darwin-aarch64)
      URL="https://github.com/tailwindlabs/tailwindcss/releases/download/${VER}/tailwindcss-macos-arm64"
      ;;
    darwin-x86_64)
      URL="https://github.com/tailwindlabs/tailwindcss/releases/download/${VER}/tailwindcss-macos-x64"
      ;;
    linux-x86_64|linux-amd64)
      URL="https://github.com/tailwindlabs/tailwindcss/releases/download/${VER}/tailwindcss-linux-x64"
      ;;
    linux-aarch64|linux-arm64)
      URL="https://github.com/tailwindlabs/tailwindcss/releases/download/${VER}/tailwindcss-linux-arm64"
      ;;
    *)
      echo "Unsupported OS/ARCH: $OS $ARCH — place tailwindcss binary at $BIN"
      exit 1
      ;;
  esac
  curl -fsSL "$URL" -o "$BIN"
  chmod +x "$BIN"
fi

if [[ "${1:-}" == "--watch" ]]; then
  exec "$BIN" -c "$CFG" -i "$INPUT" -o "$OUT" --watch
fi

"$BIN" -c "$CFG" -i "$INPUT" -o "$OUT" --minify
