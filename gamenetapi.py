
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
import struct
from typing import Callable, Optional, Tuple

from header import (
    CHAN_RELIABLE, CHAN_UNRELIABLE, CHAN_ACK,
    pack_header, unpack_header, now_ms
)

from logger import Logger
from reliable import (
    ReliableSender,
    ReliableReceiver,
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
        verbose: bool = False,
        t_mode: str = "dynamic",
        t_static_ms: int = 200, 
        k_rttvar: float = 3.0,                 # weight for RTTVAR in adaptive-t
        t_min_ms: int = 120,                   # clamp low
        t_max_ms: int = 300,                   # clamp high
        max_urgency_ms: int = 50,             # cap for urgency hint
    ):
        self.t_mode = str(t_mode)
        self.t_static_ms = int(t_static_ms)
        self.verbose = verbose  
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

        self.srtt: Optional[float] = None
        self.rttvar: Optional[float] = None

        # store adaptive-t config
        self.k_rttvar = float(k_rttvar)
        self.t_min_ms = int(t_min_ms)
        self.t_max_ms = int(t_max_ms)
        self.max_urgency_ms = int(max_urgency_ms)
        
        # channels (defer ReliableSender until peer is known)
        self.reliable_sender = None
        # receiver is fine to construct now
        self.reliable_receiver = ReliableReceiver(
            self._deliver_reliable, self._send_ack, log_cb=self._log_transport_event
        )

        # once we expose a setter in ReliableReceiver, hook it up safely:
        if hasattr(self.reliable_receiver, "set_gap_deadline_fn"):
            try:
                # Respect current timer mode for the receiver's gap timer.
                if getattr(self, "t_mode", "dynamic") == "static":
                    def _static_gap_t(_urg=0, _self=self):
                        return int(getattr(_self, "t_static_ms", 200))
                    self.reliable_receiver.set_gap_deadline_fn(_static_gap_t)
                else:
                    # dynamic uses the same EWMA-based function as the sender
                    self.reliable_receiver.set_gap_deadline_fn(self._compute_dynamic_t)
            except Exception:
                pass  # stay compatible even if method exists but signature differs


        # control
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._running = False

        # counters
        self._rx_rel = 0
        self._rx_unrel = 0
        self._tx_rel = 0
        self._tx_unrel = 0
        self._rx_ack = 0
    
    # ---------------- RTT update (single source) ----------------
    def update(self, sample_ms: float) -> None:
        x = float(sample_ms)
        if self.srtt is None:
            self.srtt = x
            self.rttvar = x / 2.0
        else:
            alpha, beta = 0.125, 0.25
            err = x - self.srtt
            self.srtt += alpha * err
            self.rttvar = (1.0 - beta) * self.rttvar + beta * abs(err)  
            
        # Keep the original estimator in sync (don’t break callers that still read it)
        try:
            self.rtt.update(x)
        except Exception:
            pass

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
        if self.peer and self.reliable_sender is None:
            self.reliable_sender = ReliableSender(
                self.sock, self.peer, self.rtt,
                log_retx_cb=self._log_tx_retransmit,
                log_expire_cb=self._log_tx_expire
            )

    def start(self) -> None:
        # Start background RX thread (and reliable sender if we have a peer).
        if self.peer and self.reliable_sender is None:
            self.reliable_sender = ReliableSender(
                self.sock, self.peer, self.rtt,
                log_retx_cb=self._log_tx_retransmit,
                log_expire_cb=self._log_tx_expire
            )
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
        urgency_ms: small positive hint to increase deadline (0-50ms typical)
        """
        assert self.peer is not None, "Peer not set. Call set_peer((host,port)) or pass peer in GameNetAPI()."
        if reliable:
            if self.reliable_sender is None:
                self.reliable_sender = ReliableSender(
                    self.sock, self.peer, self.rtt,
                    log_retx_cb=self._log_tx_retransmit,
                    log_expire_cb=self._log_tx_expire
                )
                self.reliable_sender.start()
        
            # compute per-packet deadline 't' based on mode (for EVERY send)
            mode = getattr(self, "t_mode", "dynamic")
            try:
                if mode == "static":
                    t = int(getattr(self, "t_static_ms", 200))
                else:
                    t = int(self._compute_dynamic_t(urgency_ms))
            except Exception:
                t = int(self._compute_dynamic_t(urgency_ms))
            # defensive clamp
            t = max(self.t_min_ms, min(self.t_max_ms, t))
            deadline_t_ms = t

            # Pass deadline to sender
            seq = self.reliable_sender.send(
                payload,
                urgency_ms=urgency_ms,
                deadline_ms=deadline_t_ms
            )

            if self.verbose:
                # Default when no sample
                srtt_disp = f"{self.srtt:.1f}" if self.srtt is not None else "NA"
                rttv_disp = f"{self.rttvar:.1f}" if self.rttvar is not None else "NA"
                try:
                    print(f"[REL/send] seq={seq} mode={self.t_mode} t={deadline_t_ms}ms srtt={srtt_disp} rttvar={rttv_disp}")
                except Exception:
                    pass


            self._tx_rel += 1
            if self.logger:
                self.logger.write([now_ms(), "TX", "REL", seq, now_ms(), "", 0, "send", deadline_t_ms, len(payload)])
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
            "srtt_ms": (self.srtt if self.srtt is not None else 0.0),
            "rttvar_ms": (self.rttvar if self.rttvar is not None else 0.0),
            "t_min_ms": self.t_min_ms, # expose for debugging
            "t_max_ms": self.t_max_ms, # expose for debugging
            "k_rttvar": self.k_rttvar,
        }

    # ---------------- Internal ----------------

    # adaptive dynamic t deadline
    def _compute_dynamic_t(self, urgency_ms: int = 0) -> int:
        """
        Adaptive 't' (skip-after-t / retransmit deadline proxy) per packet.

        Formula: t = clamp( self.srtt + k*self.rttvar + urgency, [t_min, t_max] )
        - SRTT/RTTVAR come from self.rtt (updated using ACK samples).
        - urgency is a small non-negative hint capped to self.max_urgency_ms.
        - Fallback when we don't have SRTT yet: assume the default base (200ms) and rttvar ~ base/2.
        """
        # Pull current estimates
        srtt = self.srtt
        rttvar = self.rttvar

        if srtt is None or rttvar is None:
            srtt, rttvar = 200.0, 100.0 # use defaults at the start

        k = self.k_rttvar
        u = max(0, min(int(urgency_ms), self.max_urgency_ms))

        # from formula 
        est = float(srtt) + k * float(rttvar) + float(u)
        est = max(self.t_min_ms, min(est, self.t_max_ms))
        return int(est)

    def _deliver_reliable(self, app_payload: bytes) -> None:
        if self.onReliable:
            self.onReliable(app_payload)

    def unpack_ack(self, b: bytes) -> int:
        (echo_ts_ms,) = struct.unpack("!I", b[:4])
        return echo_ts_ms
    
    def pack_ack(self, seq: int, echo_ts_ms: int) -> bytes:
    # ACK payload carries only the echoed send timestamp.
        return struct.pack("!I", echo_ts_ms & 0xFFFFFFFF)

    def _send_ack(self, seq: int, echo_ts_ms: int) -> None:
        # Ack is ChannelType=2 with payload=echo_ts (uint32)
        assert self.peer is not None, "Peer not set, cannot send ACK"
        pkt = pack_header(CHAN_ACK, seq, now_ms()) + self.pack_ack(seq, echo_ts_ms)
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
                    # Payload carries echoed original send timestamp (uint32)
                    echo_ts = self.unpack_ack(payload)
                    now32 = now_ms() & 0xFFFFFFFF
                    rtt_ms = float((now32 - (echo_ts & 0xFFFFFFFF)) & 0xFFFFFFFF)
                    # single-source update
                    try:
                        self.update(rtt_ms)
                    except Exception:
                        pass

                    self.reliable_sender.on_ack(seq, echo_ts)
                    if self.logger:
                        self.logger.write([
                            now_ms(), "RX", "ACK", seq,
                            echo_ts, rtt_ms, "", "ack", "", len(payload)
                        ])
                    if self.onAck:
                        self.onAck(seq, rtt_ms)
            # else: ignore unknown channel

    def _log_transport_event(self, ev: str, seq: int) -> None:
        # Always write to CSV if present
        if self.logger:
            now = now_ms()
            self.logger.write([now, "RX", "REL", seq, "", "", "", ev, "", 0])
        # Optionally mirror to console
        if self.verbose:
            print(f"[REL/{ev}] seq={seq}")

    def _log_tx_retransmit(self, seq: int, send_ts_ms: int, retries: int, payload_len: int) -> None:
        """
        Called from ReliableSender._loop() on every retransmission.
        Writes a single CSV row to sender log.
        """
        if self.logger:
            now = now_ms()
            # CSV: ts, dir, channel, seq, send_ts_ms, rtt_ms, retries, event, deadline_t_ms, len_bytes
            self.logger.write([now, "TX", "REL", seq, send_ts_ms, "", retries, "retransmit", "", payload_len])
        if self.verbose:
            print(f"[REL/retransmit] seq={seq} retries={retries}")
        
    def _log_tx_expire(self, seq: int, now_ts_ms: int, retries: int, payload_len: int, deadline_ms: Optional[int]) -> None:
        if self.logger:
            # ts, dir, channel, seq, send_ts_ms, rtt_ms, retries, event, deadline_t_ms, len_bytes
            self.logger.write([now_ts_ms, "TX", "REL", seq, now_ts_ms, "", retries, "expire", (deadline_ms or ""), payload_len])
        if self.verbose:
            print(f"[REL/expire] seq={seq} retries={retries} deadline={deadline_ms}")



