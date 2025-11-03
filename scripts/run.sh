#!/usr/bin/env bash
set -e

# --- Detect verbosity flag (-v or --verbose) ---
VERBOSE_FLAG=""
for arg in "$@"; do
  case $arg in
    -v|--verbose)
      VERBOSE_FLAG="--verbose"
      shift
      ;;
  esac
done

# --- Receiver configuration ---
BIND="${BIND:-0.0.0.0}"
PORT="${PORT:-5000}"
LOG_R="${LOG_R:-logs/receiver.csv}"

mkdir -p "$(dirname "$LOG_R")"
echo "[INFO] Starting receiver on $BIND:$PORT"

RECEIVER_ARGS=(--bind "$BIND" --port "$PORT" --log "$LOG_R")
[[ -n "$VERBOSE_FLAG" ]] && RECEIVER_ARGS+=("$VERBOSE_FLAG")

python3 receiver.py "${RECEIVER_ARGS[@]}" &
RECEIVER_PID=$!

sleep 2  # Give receiver time to initialize

# --- Sender configuration ---
HOST="${HOST:-127.0.0.1}"
PPS="${PPS:-20}"
RATIO="${RATIO:-0.5}"
DURATION="${DURATION:-30}"
LOG_S="${LOG_S:-logs/sender.csv}"

mkdir -p "$(dirname "$LOG_S")"
echo "[INFO] Starting sender to $HOST:$PORT"

SENDER_ARGS=(--host "$HOST" --port "$PORT" --pps "$PPS" \
             --reliable-ratio "$RATIO" --duration "$DURATION" --log "$LOG_S" \
             --print-every 10)
[[ -n "$VERBOSE_FLAG" ]] && SENDER_ARGS+=("$VERBOSE_FLAG")

python3 sender.py "${SENDER_ARGS[@]}"

wait $RECEIVER_PID
echo "[INFO] Run completed."
