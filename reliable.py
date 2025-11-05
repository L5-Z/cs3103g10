# reliable.py
import struct
import threading
import time
from typing import Callable, Optional, Tuple, Dict
from tools.demologger import DemoLogger

from header import pack_header, now_ms, CHAN_RELIABLE

# 16-bit sequence space (from our 7B H-UDP header: SeqNo is uint16)
MAX_SEQ  = 1 << 16
HALF_SEQ = MAX_SEQ >> 1
MASK16   = MAX_SEQ - 1

srtt = None
rttvar = None
_k = 3.0

def update(sample_ms: float):
    if srtt is None:
        srtt = float(sample_ms)
        rttvar = srtt / 2.0
        return
    alpha, beta = 0.125, 0.25
    err = float(sample_ms) - srtt
    srtt += alpha * err
    rttvar = (1 - beta) * rttvar + beta * abs(err)

def rto_ms() -> int:
    if srtt is None or rttvar is None:
        return 200
    rto = srtt + _k * rttvar
    return int(max(120, min(600, rto)))

class ReliableSender:
    # Tracks in-flight REL packets and retransmits on RTO.
    def __init__(self, sock, peer: Tuple[str, int], sender_logger:Optional[DemoLogger]=None):
        self.sock = sock
        self.peer = peer
        self.sender_logger = sender_logger
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
                "deadline": deadline_ms,
            }
            if self.sender_logger is not None:
                self.sender_logger.api_log_sent_packet_info(seq, CHAN_RELIABLE, ts)
                self.sender_logger.api_track_sent_packet(seq)
            return seq

    def on_ack(self, seq: int, echo_ts_ms: int):
        now32   = now_ms() & 0xFFFFFFFF
        send32  = echo_ts_ms & 0xFFFFFFFF
        sample  = (now32 - send32) & 0xFFFFFFFF

        if self.sender_logger is not None:
            self.sender_logger.api_log_ack_received(seq, now32, send32, sample)

        if sample <= 10_000:
            self.rtt.update(sample)

        with self._lock:
            self._inflight.pop(seq, None)

    def _loop(self):
        while self._running:
            time.sleep(0.01)
            now = now_ms()
            rto = rto_ms()
            with self._lock:
                for seq, rec in list(self._inflight.items()):
                    deadline = rec["last_tx"] + max(80, rto - rec["urgency"]) 
                    if now >= deadline:
                        ts = now_ms()
                        pkt = pack_header(CHAN_RELIABLE, seq, ts) + rec["payload"]
                        self.sock.sendto(pkt, self.peer)
                        if self.sender_logger is not None:
                            self.sender_logger.api_log_sent_packet_info(seq, CHAN_RELIABLE, ts)
                        rec["last_tx"] = ts
                        rec["retries"] += 1

class ReliableReceiver:
    # ACKs every REL packet; delivers in-order with a small reordering buffer.
    def __init__(self, deliver_cb: Callable[[bytes], None], send_ack_cb: Callable[[int, int], None], log_cb: Optional[Callable[[str, int], None]] = None, receiver_logger:Optional[DemoLogger]= None):
        self.deliver_cb = deliver_cb
        self.send_ack_cb = send_ack_cb
        self.receiver_logger = receiver_logger
        self.expected_seq: Optional[int] = None
        self.buf: Dict[int, Tuple[bytes, int, int]] = {}            # Reordering buffer: seq -> (payload, send_ts_ms, arrival_ms)
        self.max_buf = 1024                                         # Adjustable Buffer
        self._lock = threading.Lock()                               # RX thread safety (GameNetAPI runs on a background thread)
        self.log_cb = log_cb

    def _log(self, ev: str, seq: int) -> None:
        if self.log_cb:
            self.log_cb(ev, seq)

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
        if self.receiver_logger is not None:
            self.receiver_logger.api_log_ack_sent(seq)
            self.receiver_logger.api_log_received_packet_info(seq, CHAN_RELIABLE, send_ts_ms, arrival)

        with self._lock:
            # First packet: initialize expected_seq, deliver, then drain.
            if self.expected_seq is None:
                self.expected_seq = seq
                self.deliver_cb(payload)
                self._log("deliver", seq)
                self._advance_expected()
                self._drain_in_order()
                return

            # In-order arrival → deliver and drain.
            if self.seq_eq(seq, self.expected_seq):
                self.deliver_cb(payload)
                self._log("deliver", seq)
                self._advance_expected()
                self._drain_in_order()
                return

            # Ahead-of-gap arrival → buffer if within window and not already buffered.
            if self.seq_less(self.expected_seq, seq):
                if seq not in self.buf and self.in_window(self.expected_seq, seq, self.max_buf):
                    self.buf[seq] = (payload, send_ts_ms, arrival)
                    self._log("buffer", seq)
                # else: too far ahead or duplicate in buffer then drop silently
                return

            # Behind/duplicate arrival already delivered; drop.
            self._log("dup", seq)
            return
