#!/usr/bin/env bash

# Defaults; override via env
BIND="${BIND:-0.0.0.0}"
PORT="${PORT:-5000}"
LOG_R="${LOG:-logs/receiver.csv}"

mkdir -p "$(dirname "$LOG")"
python3 receiver.py --bind "$BIND" --port "$PORT" --log "$LOG_R" "$@"

# Defaults; override via env 
HOST="${HOST:-127.0.0.1}"
PPS="${PPS:-20}"
RATIO="${RATIO:-0.5}"
DURATION="${DURATION:-30}"
LOG_S="${LOG:-logs/sender.csv}"

mkdir -p "$(dirname "$LOG")"
python3 sender.py --host "$HOST" --port "$PORT" --pps "$PPS" --reliable-ratio "$RATIO" --duration "$DURATION" --log "$LOG_S" "$@"