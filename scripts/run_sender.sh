#!/usr/bin/env bash

# Defaults; override via env 
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-5000}"
PPS="${PPS:-20}"
RATIO="${RATIO:-0.5}"
DURATION="${DURATION:-30}"
LOG="${LOG:-logs/sender.csv}"

mkdir -p "$(dirname "$LOG")"
python3 sender.py --host "$HOST" --port "$PORT" --pps "$PPS" --reliable-ratio "$RATIO" --duration "$DURATION" --log "$LOG" "$@"
