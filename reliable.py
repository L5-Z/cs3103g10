# reliable.py
import struct
import threading
import time
from typing import Callable, Optional, Tuple, Dict

from header import pack_header, now_ms, CHAN_RELIABLE

class RttEstimator:
    # Keeps SRTT/RTTVAR; provides bounded RTO in ms.
    def __init__(self):
        self.srtt: Optional[float] = None
        self.rttvar: Optional[float] = None
        self._k = 4.0

    def update(self, sample_ms: float):
        if self.srtt is None:
            self.srtt = float(sample_ms)
            self.rttvar = self.srtt / 2.0
            return
        alpha, beta = 0.125, 0.25
        err = float(sample_ms) - self.srtt
        self.srtt += alpha * err
        self.rttvar = (1 - beta) * self.rttvar + beta * abs(err)

    def rto_ms(self) -> int:
        if self.srtt is None or self.rttvar is None:
            return 200
        rto = self.srtt + self._k * self.rttvar
        return int(max(120, min(600, rto)))

def pack_ack(seq: int, echo_ts_ms: int) -> bytes:
    # ACK payload carries only the echoed send timestamp.
    return struct.pack("!I", echo_ts_ms & 0xFFFFFFFF)

def unpack_ack(b: bytes) -> int:
    (echo_ts_ms,) = struct.unpack("!I", b[:4])
    return echo_ts_ms

class ReliableSender:
    # Tracks in-flight REL packets and retransmits on RTO.
    def __init__(self, sock, peer: Tuple[str, int], rtt: RttEstimator):
        self.sock = sock
        self.peer = peer
        self.rtt = rtt
        self._seq = 0
        self._inflight: Dict[int, Dict] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thr = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._running = True
        if not self._thr.is_alive():
            self._thr = threading.Thread(target=self._loop, daemon=True)
            self._thr.start()

    def stop(self):
        self._running = False
        if self._thr.is_alive():
            self._thr.join(timeout=0.2)

    def send(self, payload: bytes, urgency_ms: int = 0, deadline_ms: Optional[int] = None) -> int:
        """
        - if deadline_ms is provided, attach/store it with this seq in a dict
          and use it as:
            * retransmission cutoff (do not keep retrying past deadline)
            * packet expiry (if deadline passes before ACK, drop and mark skipped)
        - else fall back to previous default (e.g., 200ms) or your own logic.
        """
        # Allocates seq, sends once, stores state for retransmit.
        with self._lock:
            seq = self._seq & 0xFFFF
            self._seq = (self._seq + 1) & 0xFFFF
            ts = now_ms()
            pkt = pack_header(CHAN_RELIABLE, seq, ts) + payload
            self.sock.sendto(pkt, self.peer)
            self._inflight[seq] = {
                "payload": payload,
                "last_tx": ts,
                "retries": 0,
                "first_ts": ts,
                "urgency": max(0, int(urgency_ms)),
            }
            return seq

    def on_ack(self, seq: int, echo_ts_ms: int):
        # Uses echoed timestamp to form an RTT sample.
        sample = now_ms() - echo_ts_ms
        if sample >= 0:
            self.rtt.update(sample)
        with self._lock:
            self._inflight.pop(seq, None)

    def _loop(self):
        while self._running:
            time.sleep(0.01)
            now = now_ms()
            rto = self.rtt.rto_ms()
            with self._lock:
                for seq, rec in list(self._inflight.items()):
                    deadline = rec["last_tx"] + max(80, rto - rec["urgency"])
                    if now >= deadline:
                        ts = now_ms()
                        pkt = pack_header(CHAN_RELIABLE, seq, ts) + rec["payload"]
                        self.sock.sendto(pkt, self.peer)
                        rec["last_tx"] = ts
                        rec["retries"] += 1

class ReliableReceiver:
    # ACKs every REL packet and delivers immediately.
    def __init__(self, deliver_cb: Callable[[bytes], None], send_ack_cb: Callable[[int, int], None]):
        self.deliver_cb = deliver_cb
        self.send_ack_cb = send_ack_cb

    def on_packet(self, seq: int, send_ts_ms: int, payload: bytes):
        self.send_ack_cb(seq, send_ts_ms)
        self.deliver_cb(payload)
