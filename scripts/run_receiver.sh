#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-9000}"
LOG="${LOG:-logs/receiver.csv}"
VERBOSE="${VERBOSE:-0}"
T_MODE="${T_MODE:-dynamic}"        # static|dynamic
T_STATIC_MS="${T_STATIC_MS:-200}"
BIND="${BIND:-127.0.0.1}"          # if your receiver supports --bind

mkdir -p "$(dirname "$LOG")"

cleanup_port() {
  # best-effort: kill holders of UDP port
  if command -v fuser >/dev/null 2>&1; then
    fuser -k -n udp "${PORT}" 2>/dev/null || true
  fi
  if command -v lsof >/dev/null 2>&1; then
    pids=$(lsof -t -iUDP:"${PORT}" || true)
    [[ -n "${pids}" ]] && kill ${pids} 2>/dev/null || true
  fi
  # fallback: pattern kill (broad but helpful for dev runs)
  pkill -f "receiver.py.*--port ${PORT}" 2>/dev/null || true
}

# CLI overrides
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2;;
    --log) LOG="$2"; shift 2;;
    --verbose) VERBOSE=1; shift;;
    --t-mode) T_MODE="$2"; shift 2;;
    --t-static-ms) T_STATIC_MS="$2"; shift 2;;
    --bind) BIND="$2"; shift 2;;
    *) echo "Unknown arg: $1"; exit 2;;
  esac
done

cleanup_port
sleep 0.1

# run receiver; rely on its own cleanup on exit
exec python3 receiver.py \
  --port "${PORT}" \
  --log "${LOG}" \
  $( [[ "${VERBOSE}" == "1" ]] && echo --verbose ) \
  --t-mode "${T_MODE}" \
  --t-static-ms "${T_STATIC_MS}" \
  $( [[ -n "${BIND}" ]] && echo --bind "${BIND}" )
