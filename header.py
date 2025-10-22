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

def checksum(msg_bytes):
    """Compute 16-bit Internet checksum."""
    s = 0
    # Process 16-bit chunks
    for i in range(0, len(msg_bytes), 2):
        if i + 1 < len(msg_bytes):
            w = (msg_bytes[i] << 8) + msg_bytes[i + 1]
        else:
            w = (msg_bytes[i] << 8)
        s += w

    # Wrap-around carry bits
    s = (s >> 16) + (s & 0xffff)
    s += (s >> 16)
    return ~s & 0xffff

def compute_udp_checksum(src_ip, dest_ip, udp_header, payload):
    """
    Compute UDP checksum including pseudo-header.
    Payload = custom_header + mock_game_data
    """
    # Pseudo header fields
    src_addr = socket.inet_aton(src_ip)
    dest_addr = socket.inet_aton(dest_ip)
    placeholder = 0 # padding byte to ensure pseudo_header is 16 bytes long
    protocol = socket.IPPROTO_UDP
    udp_length = len(udp_header) + len(payload)

    pseudo_header = struct.pack('!4s4sBBH', src_addr, dest_addr, placeholder, protocol, udp_length) # for computing checksum only

    # Combine everything
    checksum_input = pseudo_header + udp_header + payload

    return checksum(checksum_input)

def make_packet(src_ip, dest_ip, src_port, dest_port, payload):
    """
    Returns UDP packet for sending
    Payload = custom_header + mock_game_data
    """
    temporary_checksum = 0 # for computing actual checksum
    udp_length = 8 + len(payload)
    udp_header = struct.pack('!HHHH', src_port, dest_port, udp_length, temporary_checksum)

    # compute checksum
    checksum = compute_udp_checksum(src_ip, dest_ip, udp_header, payload)

    # rebuild final header with real checksum
    udp_header = struct.pack('!HHHH', src_port, dest_port, udp_length, checksum)

    packet = udp_header + payload

    return packet

def make_mock_game_data(i):
    # simple JSON-like payload (independent packets)
    obj = {"i": i, "ts": (int(time.time()*1000) % (2**32)), "x": random.random(), "y": random.random()}
    return json.dumps(obj).encode("utf-8")

def unpack_packet(udp_packet):
    """
    For unpacking ACK packets
    Payload = seq_no
    """
    udp_header = udp_packet[:8] # header is first 8 bytes
    payload = udp_packet[8:]

    src_port, dest_port, udp_length, checksum = struct.unpack('!HHHH', udp_header)

    return {
        'udp_header': udp_header,
        'src_port': src_port,
        'dest_port': dest_port,
        'udp_length': udp_length,
        'checksum': checksum,
        'payload': payload
    }

def unpack_payload(payload): # might need to change later depending on payload structure
    """
    Payload: custom_header + mock_game_data
    custom_header: flags(channel_type 0/1 RMB, latency 0/1 2nd RMB) [1B] | seq_no [2B] | timestamp (time sent) [4B] <total 7B long>
    mock_game_data:
    """
    custom_header = payload[:7]
    mock_game_data = payload[7:]

    flags, seq_no, timestamp = struct.unpack('!BHI', custom_header)

    channel_type = flags & 0b00000001 # 0 for reliable and 1 for unreliable
    latency = (flags & 0b00000010) >> 1 # 0 for low and 1 for high
    

    return {
        'channel_type': channel_type,
        'latency': latency,
        'seq_no': seq_no,
        'timestamp': timestamp,
        'mock_game_data': mock_game_data
    }

def validate_checksum(src_ip, dest_ip, udp_header, payload):
    """
    Return True if checksum valid, else False.
    For validating checksum of ACK packets
    """
    received_checksum = struct.unpack('!HHHH', udp_header)[3] # checksum is 4th field in udp_header

    # Zero the checksum field for recomputation of checksum
    header_zeroed = udp_header[:6] + struct.pack('!H', 0)
    computed = compute_udp_checksum(src_ip, dest_ip, header_zeroed, payload)

    return received_checksum == computed


def make_flags_byte(channel_type, latency):
    """
    channel_type 1 bit e.g. 0b00000001
    latency 1 bit e.g. 0b00000010
    """
    return (latency << 1) | channel_type 

def make_custom_header(flags, seq_no, timestamp):
    """
    flags 1B
    seq_no 2B
    timestamp 4B
    """
    return struct.pack('!BHI', flags, seq_no, timestamp)

def make_payload(custom_header, mock_game_data):
    return custom_header + mock_game_data