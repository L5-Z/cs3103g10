"""
CS3103 Group 10 - Log Script
Simple CSV logger for passing to charts-latency.py.

Logging
-------
Write a CSV with columns:
  ts_recv_ms, dir, channel, seq, send_ts_ms, rtt_ms, retries, event, deadline_t_ms, len_bytes
"""

import csv
import os
import threading

class Logger:

    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._f = open(path, "w", newline="")
        self._w = csv.writer(self._f)
        self._w.writerow([
            "ts_recv_ms","dir","channel","seq","send_ts_ms","rtt_ms","retries","event","deadline_t_ms","len_bytes"
        ])
        self._lock = threading.Lock()

    def write(self, row):
        with self._lock:
            self._w.writerow(row)
            self._f.flush()

    def close(self):
        with self._lock:
            try:
                self._f.close()
            except Exception:
                pass
