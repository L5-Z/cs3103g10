#!/usr/bin/env bash
set -euo pipefail

# Defaults; override via env 
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-5000}"
PPS="${PPS:-20}"
RATIO="${RATIO:-0.5}"      # reliable ratio in [0..1]
DURATION="${DURATION:-30}"
LOG="${LOG:-logs/sender.csv}"

# QoL flags: --reliable-only sets RATIO=1.0, --unreliable-only sets RATIO=0.0
ADDITIONAL_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --reliable-only)
      RATIO="1.0"
      ;;
    --unreliable-only)
      RATIO="0.0"
      ;;
    *)
      ADDITIONAL_ARGS+=("$arg")
      ;;
  esac
done

mkdir -p "$(dirname "$LOG")"
python3 sender.py --host "$HOST" --port "$PORT" \
  --pps "$PPS" --reliable-ratio "$RATIO" --duration "$DURATION" \
  --log "$LOG" "${ADDITIONAL_ARGS[@]}"
