
"""
CS3103 Group 10 - GameNetAPI

H-UDP facade for reliable/unreliable channels
=========================

Purpose
-------
A small facade around the H-UDP transport:
- One UDP socket with two logical channels (reliable / unreliable)
- Explicit header: ChannelType (1B) | SeqNo (2B) | Timestamp (4B)
- Reliable channel uses Selective-Repeat flavor with retransmissions
  and **skip-after-t** semantics enforced at the receiver
- **Adaptive-t**: t_deadline is computed per packet by the sender
  (SRTT + k*RTTVAR + urgency), kept to [120..300] ms.
- ACKs are sent over a control channel (ChannelType=2) and used to
  update SRTT/RTTVAR for the sender.

Key API
-------
- set_callbacks(onReliable: (bytes)->None, onUnreliable: (bytes)->None)
- start() / stop()
- send(payload: bytes, reliable: bool = True, urgency_ms: int = 0)
- set_peer((host, port))  # optional after construction
- stats() -> dict         # counters to print in demo

Extra Details
-----
- The ACK path echoes the original sender timestamp so the sender can
  take an RTT sample even after retransmissions.
- The receiver enforces "skip-after-t" using a gap-timer: 
  when out-of-order packets exist past the expected seq, we
  skip the missing one if the oldest buffered packet has aged beyond
  a minimal deadline proxy.

"""
import socket
import threading
import time
from typing import Callable, Optional, Tuple

from header import (
    CHAN_RELIABLE, CHAN_UNRELIABLE, CHAN_ACK,
    pack_header, unpack_header, now_ms
)

from logger import Logger
from reliable import (
    ReliableSender,
    ReliableReceiver,
    pack_ack,
    unpack_ack,
    RttEstimator,
)




class GameNetAPI:
    # Reliable/unreliable send, demux, and logging 

    def __init__(
        self,
        sock: socket.socket,
        peer: Optional[Tuple[str,int]] = None,
        log_path: Optional[str] = None,
        max_recv_size: int = 4096,
        k_rttvar: float = 3.0,                 # weight for RTTVAR in adaptive-t
        t_min_ms: int = 120,                   # clamp low
        t_max_ms: int = 300,                   # clamp high
        max_urgency_ms: int = 50,             # cap for urgency hint
    ):
        self.sock = sock
        self.peer = peer  # must be set for sending & ACKs
        self.max_recv_size = max_recv_size

        # callbacks
        self.onReliable: Optional[Callable[[bytes], None]] = None
        self.onUnreliable: Optional[Callable[[bytes], None]] = None
        self.onAck: Optional[Callable[[int, int], None]] = None  # (seq, rtt_ms)

        # logging
        self.logger = Logger(log_path) if log_path else None

        # RTT estimation (shared with reliable sender)
        self.rtt = RttEstimator()

        # channels
        self.reliable_sender: Optional[ReliableSender] = None
        
        # optionally pass deadline function down to receiver)
        self.reliable_receiver = ReliableReceiver(
            self._deliver_reliable,
            self._send_ack,
            gap_deadline_fn=self._compute_deadline_ms
        )

        # control
        import threading
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._running = False

        # counters
        self._rx_rel = 0
        self._rx_unrel = 0
        self._tx_rel = 0
        self._tx_unrel = 0
        self._rx_ack = 0

    # ---------------- Public Facing API ----------------

    def set_callbacks(
        self,
        reliable_cb: Optional[Callable[[bytes], None]],
        unreliable_cb: Optional[Callable[[bytes], None]],
        ack_cb: Optional[Callable[[int,int], None]] = None
    ) -> None:
        self.onReliable = reliable_cb
        self.onUnreliable = unreliable_cb
        self.onAck = ack_cb

    def set_peer(self, peer: Tuple[str,int]) -> None:
        # Explicitly set the remote peer (used for send & ACK).
        self.peer = peer
        if self.reliable_sender is None:
            self.reliable_sender = ReliableSender(self.sock, self.peer, self.rtt)

    def start(self) -> None:
        # Start background RX thread (and reliable sender if we have a peer).
        if self.peer and self.reliable_sender is None:
            self.reliable_sender = ReliableSender(self.sock, self.peer, self.rtt)
        if self.reliable_sender:
            self.reliable_sender.start()
        self._running = True
        self._rx_thread.start()

    def stop(self) -> None:
        self._running = False
        if self.reliable_sender:
            self.reliable_sender.stop()
        if self.logger:
            self.logger.close()

    def send(self, payload: bytes, reliable: bool = True, urgency_ms: int = 0) -> None:
        """
        Send a payload on the chosen channel. Peer must be set first.

        payload: application bytes (independent packet)
        reliable: True for reliable channel; False for unreliable
        urgency_ms: small positive hint to increase deadline (0..50ms typical)
        """
        assert self.peer is not None, "Peer not set. Call set_peer((host,port)) or pass peer in GameNetAPI()."
        if reliable:
            if self.reliable_sender is None:
                self.reliable_sender = ReliableSender(self.sock, self.peer, self.rtt)
                self.reliable_sender.start()
            # compute adaptive per-packet deadline
            deadline_ms = self._compute_deadline_ms(urgency_ms)

            # Pass deadline to sender
            seq = self.reliable_sender.send(payload, urgency_ms=urgency_ms, deadline_ms=deadline_ms)

            self._tx_rel += 1
            if self.logger:
                self.logger.write([
                    now_ms(), "TX", "REL", seq, now_ms(), "", deadline_ms, "send", "", len(payload)
                ])
        else:
            pkt = pack_header(CHAN_UNRELIABLE, 0, now_ms()) + payload
            self.sock.sendto(pkt, self.peer)
            self._tx_unrel += 1
            if self.logger:
                self.logger.write([now_ms(), "TX", "UNREL", "", now_ms(), "", 0, "send", "", len(payload)])

    def stats(self) -> dict:
        return {
            "tx_rel": self._tx_rel,
            "tx_unrel": self._tx_unrel,
            "rx_rel": self._rx_rel,
            "rx_unrel": self._rx_unrel,
            "rx_ack": self._rx_ack,
            "srtt_ms": (self.rtt.srtt if self.rtt.srtt is not None else 0.0),
            "rttvar_ms": (self.rtt.rttvar if self.rtt.rttvar is not None else 0.0),
            "t_min_ms": self.t_min_ms, # expose for debugging
            "t_max_ms": self.t_max_ms, # expose for debugging
            "k_rttvar": self.k_rttvar,
        }

    # ---------------- Internal ----------------

    # adaptive deadline function
    def _compute_deadline_ms(self, urgency_ms: int = 0) -> int:
        """
        Adaptive 't' (skip-after-t / retransmit deadline proxy) per packet.

        Formula: t = clamp( SRTT + k*RTTVAR + urgency, [t_min, t_max] )
        - SRTT/RTTVAR come from self.rtt (updated using ACK samples).
        - urgency is a small non-negative hint capped to self.max_urgency_ms.
        - Fallback when we don't have SRTT yet: assume the default base (200ms) and rttvar ~ base/2.
        """
        # Pull current estimates
        srtt = self.rtt.srtt
        rttvar = self.rtt.rttvar

        if srtt is None or rttvar is None:
            # cold start: use conservative defaults
            srtt = 200.0
            rttvar = 100.0

        k = self.k_rttvar
        u = max(0, min(int(urgency_ms), self.max_urgency_ms))

        # from formula 
        est = float(srtt) + k * float(rttvar) + float(u)
        est = max(self.t_min_ms, min(est, self.t_max_ms))
        return int(est)

    def _deliver_reliable(self, app_payload: bytes) -> None:
        if self.onReliable:
            self.onReliable(app_payload)

    def _send_ack(self, seq: int, echo_ts_ms: int) -> None:
        # Ack is ChannelType=2 with payload=echo_ts (uint32)
        assert self.peer is not None, "Peer not set, cannot send ACK"
        pkt = pack_header(CHAN_ACK, seq, now_ms()) + pack_ack(seq, echo_ts_ms)
        self.sock.sendto(pkt, self.peer)

    def _rx_loop(self) -> None:
        self.sock.settimeout(0.2)
        while self._running:
            try:
                data, _addr = self.sock.recvfrom(self.max_recv_size)
                if self.peer is None:
                    # learn peer lazily on first packet (receiver side)
                    self.peer = _addr
            except socket.timeout:
                continue
            except OSError:
                break  # socket closed during stop()

            # Parse header
            try:
                chan, seq, ts, payload = unpack_header(data)
            except Exception:
                continue

            now = now_ms()

            if chan == CHAN_RELIABLE:
                self._rx_rel += 1
                if self.logger:
                    self.logger.write([now, "RX", "REL", seq, ts, "", "", "recv", "", len(payload)])
                # Demux to reliable receiver (handles reorder + skip-after-t)
                self.reliable_receiver.on_packet(seq, ts, payload)
                # The receiver will enforce skip-after-t using its own gap timer. If added gap_deadline_fn in ReliableReceiver, 
                # it calls _compute_deadline_ms() internally but otherwise it uses default.

            elif chan == CHAN_UNRELIABLE:
                self._rx_unrel += 1
                if self.logger:
                    self.logger.write([now, "RX", "UNREL", "", ts, "", "", "recv", "", len(payload)])
                if self.onUnreliable:
                    self.onUnreliable(payload)

            elif chan == CHAN_ACK:
                self._rx_ack += 1

                # Only meaningful for the sender side
                if self.reliable_sender is not None:
                    try:
                        echo_ts = unpack_ack(payload)
                    except Exception:
                        continue
                    rtt_ms = now - echo_ts if now >= echo_ts else 0
                    self.reliable_sender.on_ack(seq, echo_ts)
                    if self.logger:
                        self.logger.write([now, "RX", "ACK", seq, echo_ts, rtt_ms, "", "ack", "", len(payload)])
                    if self.onAck:
                        self.onAck(seq, rtt_ms)
            # else: ignore unknown channel

