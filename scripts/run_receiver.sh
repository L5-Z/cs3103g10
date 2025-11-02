#!/usr/bin/env bash
set -euo pipefail

# Defaults; override via env
BIND="${BIND:-127.0.0.1}"      # bind to loopback by default for netem on lo
PORT="${PORT:-5000}"
LOG="${LOG:-logs/receiver.csv}"

mkdir -p "$(dirname "$LOG")"
python3 receiver.py --bind "$BIND" --port "$PORT" --log "$LOG" "$@"