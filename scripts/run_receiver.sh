#!/usr/bin/env bash

# Defaults; override via env
BIND="${BIND:-0.0.0.0}"
PORT="${PORT:-5000}"
LOG="${LOG:-logs/receiver.csv}"

mkdir -p "$(dirname "$LOG")"
python3 receiver.py --bind "$BIND" --port "$PORT" --log "$LOG" "$@"
