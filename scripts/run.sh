#!/usr/bin/env bash

# Receiver config
BIND="${BIND:-0.0.0.0}"
PORT="${PORT:-5000}"
LOG_R="${LOG_R:-logs/receiver.csv}"

mkdir -p "$(dirname "$LOG_R")"
echo "[INFO] Starting receiver on $BIND:$PORT"
python3 receiver.py --bind "$BIND" --port "$PORT" --log "$LOG_R" "$@" &
RECEIVER_PID=$!

# Give receiver time to start
sleep 2

# Sender config
HOST="${HOST:-127.0.0.1}"
PPS="${PPS:-20}"
RATIO="${RATIO:-0.5}"
DURATION="${DURATION:-30}"
LOG_S="${LOG_S:-logs/sender.csv}"

mkdir -p "$(dirname "$LOG_S")"
echo "[INFO] Starting sender to $HOST:$PORT"
python3 sender.py --host "$HOST" --port "$PORT" --pps "$PPS" --reliable-ratio "$RATIO" --duration "$DURATION" --log "$LOG_S" "$@"

# Wait for receiver to finish when sender completes
wait $RECEIVER_PID
