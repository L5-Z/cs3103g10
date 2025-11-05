#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-9000}"
DURATION="${DURATION:-10}"
PPS="${PPS:-20}"
REL_RATIO="${REL_RATIO:-0.7}"
LOG="${LOG:-logs/sender.csv}"
VERBOSE="${VERBOSE:-0}"
T_MODE="${T_MODE:-dynamic}"        # static|dynamic
T_STATIC_MS="${T_STATIC_MS:-200}"

mkdir -p "$(dirname "$LOG")"

# CLI overrides
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2;;
    --port) PORT="$2"; shift 2;;
    --duration) DURATION="$2"; shift 2;;
    --pps) PPS="$2"; shift 2;;
    --reliable-ratio) REL_RATIO="$2"; shift 2;;
    --log) LOG="$2"; shift 2;;
    --verbose) VERBOSE=1; shift;;
    --t-mode) T_MODE="$2"; shift 2;;
    --t-static-ms) T_STATIC_MS="$2"; shift 2;;
    *) echo "Unknown arg: $1"; exit 2;;
  esac
done

exec python3 sender.py \
  --host "${HOST}" \
  --port "${PORT}" \
  --duration "${DURATION}" \
  --pps "${PPS}" \
  --reliable-ratio "${REL_RATIO}" \
  --log "${LOG}" \
  $( [[ "${VERBOSE}" == "1" ]] && echo --verbose ) \
  --t-mode "${T_MODE}" \
  --t-static-ms "${T_STATIC_MS}"
