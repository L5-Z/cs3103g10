"""
CS3103 Group 10 - Header Module
H-UDP Header Packing/Unpacking

Header format (7 bytes total):
  - ChannelType (1 byte): 0=reliable, 1=unreliable, 2=ack (control)
  - SeqNo       (2 bytes, unsigned short; wraps at 65535)
  - Timestamp   (4 bytes, unsigned int; milliseconds since epoch)

Layout (network byte order, big-endian):

    0        7 8      15 16                       47
    +----------+----------+------------------------+
    | ChanType |   SeqNo  |     Timestamp (ms)     |
    +----------+----------+------------------------+
    |                 Payload ...                  |
    +----------------------------------------------+
"""
from typing import Tuple
import struct
import time

# struct format: unsigned char (B), unsigned short (H), unsigned int (I)
HEADER_FMT = "!BHI"
HEADER_SIZE = struct.calcsize(HEADER_FMT)

# Logical channels
CHAN_RELIABLE   = 0
CHAN_UNRELIABLE = 1
CHAN_ACK        = 2  # internal acks for reliable

MAX_SEQ = 0x10000  # 65536 (wrap modulus)

def now_ms() -> int:
    # Return current time in milliseconds since epoch
    return int(time.time() * 1000)

def pack_header(channel: int, seq: int, ts_ms: int) -> bytes:
    """Pack the H-UDP header and return bytes.

    Args:
        channel: either CHAN_RELIABLE / CHAN_UNRELIABLE / CHAN_ACK
        seq:     0 - 65535 (will be masked to 16 bits)
        ts_ms:   0 - 2^32-1 (will be masked to 32 bits)

    Returns:
        The 7-byte header ready to be prepended to the payload.
    """
    if channel not in (CHAN_RELIABLE, CHAN_UNRELIABLE, CHAN_ACK):
        raise ValueError(f"Invalid channel: {channel}")
    return struct.pack(HEADER_FMT, channel & 0xFF, seq & 0xFFFF, ts_ms & 0xFFFFFFFF)

def unpack_header(packet: bytes) -> Tuple[int, int, int, bytes]:
    """Unpack the H-UDP header from the packet.

    Returns:
        (channel, seq, ts_ms, payload_bytes)

    Raises:
        ValueError if the packet is shorter than the header.
    """
    if len(packet) < HEADER_SIZE:
        raise ValueError("Packet too short for H-UDP header")
    channel, seq, ts = struct.unpack(HEADER_FMT, packet[:HEADER_SIZE])
    payload = packet[HEADER_SIZE:]
    return channel, seq, ts, payload
