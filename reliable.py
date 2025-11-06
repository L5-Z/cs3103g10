# reliable.py
import struct
import threading
import time
from typing import Callable, Optional, Tuple, Dict

from header import pack_header, now_ms, CHAN_RELIABLE

# 16-bit sequence space (from our 7B H-UDP header: SeqNo is uint16)
MAX_SEQ  = 1 << 16
HALF_SEQ = MAX_SEQ >> 1
MASK16   = MAX_SEQ - 1


class ReliableSender:
    # Tracks in-flight REL packets and retransmits on RTO.
    def __init__(
        self,
        sock,
        peer: Tuple[str, int],
        get_rto_ms: Callable[[], int],
        log_retx_cb: Optional[Callable[[int, int, int, int], None]] = None,
        log_expire_cb: Optional[Callable[[int, int, int, int, Optional[int]], None]] = None,
    ):
        self.sock = sock
        self.peer = peer
        self.rtt = get_rto_ms
        self._seq = 0
        self._inflight: Dict[int, Dict] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thr = threading.Thread(target=self._loop, daemon=True)
        self._log_retx_cb = log_retx_cb
        self._log_expire_cb = log_expire_cb


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
        - else fall back to previous default (e.g. 200ms)
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
                "deadline_ms": int(deadline_ms) if deadline_ms is not None else None,
                "expiry_ts": (ts + int(deadline_ms)) if deadline_ms is not None else None,
            }
            return seq

    def on_ack(self, seq: int, echo_ts_ms: int):
        now32   = now_ms() & 0xFFFFFFFF
        send32  = echo_ts_ms & 0xFFFFFFFF
        sample  = (now32 - send32) & 0xFFFFFFFF

        if sample <= 10_000:
            self.rtt.update(sample)

        with self._lock:
            self._inflight.pop(seq, None)

    def _loop(self):
        while self._running:
            time.sleep(0.01)
            now = now_ms()
            rto = self.rtt()
            with self._lock:
                to_expire = []
                to_retx = []
                for seq, rec in list(self._inflight.items()):
                    # 1) Expiry: stop retrying after per-packet deadline
                    exp = rec.get("expiry_ts")
                    if exp is not None and now >= exp:
                        to_expire.append((seq, rec))
                        continue
                    # 2) RTO-based retransmission (existing behavior, urgency shortens wait)
                    deadline = rec["last_tx"] + max(80, rto - rec["urgency"])
                    if now >= deadline:
                        to_retx.append((seq, rec))

            # Handle expirations outside the lock
            for seq, rec in to_expire:
                try:
                    if self._log_expire_cb:
                        # args: seq, now_ts, retries, payload_len, original_deadline_ms
                        self._log_expire_cb(seq, now, rec.get("retries", 0), len(rec.get("payload", b"")), rec.get("deadline_ms"))
                except Exception:
                    pass
                with self._lock:
                    self._inflight.pop(seq, None)

            # Handle retransmissions outside the lock
            for seq, rec in to_retx:
                try:
                    ts = now_ms()
                    pkt = pack_header(CHAN_RELIABLE, seq, ts) + rec["payload"]
                    self.sock.sendto(pkt, self.peer)
                    with self._lock:
                        rec["last_tx"] = ts
                        rec["retries"] += 1
                    if self._log_retx_cb:
                        try:
                            # args: seq, send_ts_ms, retries, payload_len
                            self._log_retx_cb(seq, ts, rec["retries"], len(rec["payload"]))
                        except Exception:
                            pass
                except Exception:
                    # swallow and continue; next tick will retry/expire
                    pass

class ReliableReceiver:
    # ACKs every REL packet; delivers in-order with a small reordering buffer.
    def __init__(self, deliver_cb: Callable[[bytes], None], send_ack_cb: Callable[[int, int], None], log_cb: Optional[Callable[[str, int], None]] = None):
        self.deliver_cb = deliver_cb
        self.send_ack_cb = send_ack_cb
        self.expected_seq: Optional[int] = None
        self.buf: Dict[int, Tuple[bytes, int, int]] = {}            # Reordering buffer: seq -> (payload, send_ts_ms, arrival_ms)
        self.max_buf = 1024                                         # Adjustable Buffer
        self._lock = threading.Lock()                               # RX thread safety (GameNetAPI runs on a background thread)
        self.log_cb = log_cb
        # --- gap timer state (skip-after-t) ---
        self._gap_start_ms: Optional[int] = None
        self._gap_deadline_ms: Optional[int] = None
        self._gap_t_fn: Callable[[int], int] = lambda urgency_ms=0: 200

    def _log(self, ev: str, seq: int) -> None:
        if self.log_cb:
            self.log_cb(ev, seq)
            
    def set_gap_deadline_fn(self, fn: Callable[[int], int]) -> None:
        self._gap_t_fn = fn

    def _advance_expected(self) -> None:
        # Move to next sequence number (modulo 2^16)
        self.expected_seq = (self.expected_seq + 1) & MASK16  # type: ignore[operator]

    def _drain_in_order(self) -> None:
        # Deliver any buffered packets that have become contiguous.
        while self.expected_seq in self.buf:
            self._log("deliver", self.expected_seq)   
            payload, _send_ts, _arr = self.buf.pop(self.expected_seq)
            self.deliver_cb(payload)
            self._advance_expected()
            if self.expected_seq is not None:
                ahead = [s for s in self.buf.keys() if self.in_window(self.expected_seq, s, self.max_buf)]
                if ahead:
                    now = now_ms()
                    self._gap_start_ms = now
                    self._gap_deadline_ms = now + int(self._gap_t_fn(0))
                else:
                    self._gap_start_ms = None
                    self._gap_deadline_ms = None
    
    def seq_eq(self, a: int, b: int) -> bool:
        return ((a ^ b) & MASK16) == 0

    def seq_less(self, a: int, b: int) -> bool:
        #True iff a comes before b in modulo-2^16 order.
        return ((b - a) & MASK16) < HALF_SEQ and not self.seq_eq(a, b)

    def seq_dist_fwd(self, a: int, b: int) -> int:
        # Forward distance a->b in modulo-2^16.
        return (b - a) & MASK16

    def in_window(self, base: int, s: int, win: int) -> bool:
        # Is s within (base, base+win] ahead (mod 2^16)?
        d = self.seq_dist_fwd(base, s)
        return 0 < d <= win

    def on_packet(self, seq: int, send_ts_ms: int, payload: bytes) -> None:
        # Always ACK immediately so sender RTT/RTO keeps working.
        self.send_ack_cb(seq, send_ts_ms)
        arrival = now_ms()

        with self._lock:

            if self._gap_deadline_ms is not None and arrival >= self._gap_deadline_ms and self.expected_seq is not None:
                have_ahead = any(self.in_window(self.expected_seq, s, self.max_buf) for s in self.buf.keys())
                if have_ahead:
                    self._log("skip", self.expected_seq)
                    self._advance_expected()
                    self._drain_in_order()

            if self.expected_seq is None:
                self.expected_seq = seq
                self.deliver_cb(payload)
                self._log("deliver", seq)
                self._advance_expected()
                self._drain_in_order()
                return

            if self.seq_eq(seq, self.expected_seq):
                self.deliver_cb(payload)
                self._log("deliver", seq)
                self._advance_expected()
                self._drain_in_order()
                return

            if self.seq_less(self.expected_seq, seq):
                if seq not in self.buf and self.in_window(self.expected_seq, seq, self.max_buf):
                    self.buf[seq] = (payload, send_ts_ms, arrival)
                    self._log("buffer", seq)
                    if self._gap_start_ms is None:
                        self._gap_start_ms = arrival
                        self._gap_deadline_ms = arrival + int(self._gap_t_fn(0))
                return

            # Behind/duplicate arrival already delivered; drop.
            self._log("dup", seq)
            return
