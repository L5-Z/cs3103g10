#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-9000}"

pick_free_udp_port() {
  python3 - <<'PY'
import socket
s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("127.0.0.1",0))
print(s.getsockname()[1])
s.close()
PY
}

if ss -lun | awk '{print $5}' | grep -q ":${PORT}$"; then
  PORT="$(pick_free_udp_port)"
fi

mkdir -p logs

"${SCRIPT_DIR}/run_receiver.sh" --port "${PORT}" --t-mode dynamic --log "${RLOG:-logs/receiver.csv}" &
RX_PID=$!

cleanup() { kill "$RX_PID" 2>/dev/null || true; wait "$RX_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

sleep 0.3

"${SCRIPT_DIR}/run_sender.sh" --port "${PORT}" --t-mode dynamic --log "${SLOG:-logs/sender.csv}" "$@"
